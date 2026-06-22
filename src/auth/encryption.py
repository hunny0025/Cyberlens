"""
CyberLens — PII Encryption at Rest
=====================================
Encrypts sensitive PII (phone numbers, UPI IDs, names) stored in DB.
Prevents data leakage if SQLite file is exfiltrated.

Algorithm: AES-256-GCM (authenticated encryption)
Key: derived from SECRET_KEY using PBKDF2

Also: PII masking for log files (prevents sensitive data in logs)

Author: CyberLens Team — GPCSSI India
"""

import base64
import hashlib
import logging
import os
import re
from functools import lru_cache
from typing import Optional

logger = logging.getLogger("cyberlens.auth.encryption")

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production-min-32-chars!!")
SALT = b"CyberLens_GPCSSI_v3_salt_2025"


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _derive_key() -> bytes:
    """Derive 32-byte AES key from SECRET_KEY using PBKDF2."""
    return hashlib.pbkdf2_hmac(
        "sha256", SECRET_KEY.encode(), SALT, 100000, dklen=32
    )


# ---------------------------------------------------------------------------
# AES-256-GCM encryption (via cryptography library, or fallback XOR)
# ---------------------------------------------------------------------------

def encrypt_pii(plaintext: str) -> str:
    """Encrypt a PII value for storage.

    Args:
        plaintext: Raw PII (phone number, UPI ID, etc.)

    Returns:
        Base64-encoded ciphertext string with IV prepended.
        Returns original if encryption unavailable.
    """
    if not plaintext:
        return plaintext

    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import os as _os

        key = _derive_key()
        nonce = _os.urandom(12)  # 96-bit nonce for GCM
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

        # Pack nonce + ciphertext, base64 encode
        combined = nonce + ciphertext
        return "ENC:" + base64.b64encode(combined).decode()

    except ImportError:
        # Fallback: XOR with key stream (not secure — warn admin)
        logger.warning(
            "cryptography package not installed — using weak XOR cipher. "
            "Install: pip install cryptography"
        )
        return _xor_encrypt(plaintext)
    except Exception as e:
        logger.error("Encryption failed: %s", e)
        return plaintext


def decrypt_pii(ciphertext: str) -> str:
    """Decrypt an encrypted PII value.

    Args:
        ciphertext: Base64-encoded ciphertext with 'ENC:' prefix.

    Returns:
        Decrypted plaintext string.
    """
    if not ciphertext or not ciphertext.startswith("ENC:"):
        return ciphertext  # not encrypted

    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        key = _derive_key()
        combined = base64.b64decode(ciphertext[4:])
        nonce = combined[:12]
        enc_data = combined[12:]

        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, enc_data, None)
        return plaintext.decode("utf-8")

    except ImportError:
        return _xor_decrypt(ciphertext)
    except Exception as e:
        logger.error("Decryption failed: %s", e)
        return "[DECRYPTION_ERROR]"


def is_encrypted(value: str) -> bool:
    """Check if a value is encrypted."""
    return bool(value and value.startswith("ENC:"))


# ---------------------------------------------------------------------------
# PII masking for logs
# ---------------------------------------------------------------------------

# Patterns to mask
_MASK_PATTERNS = [
    # Indian mobile numbers
    (re.compile(r"(\+91[-\s]?)?[6-9]\d{9}"), "***PHONE***"),
    # UPI IDs
    (re.compile(r"\b[a-zA-Z0-9._-]+@[a-zA-Z]{2,10}\b"), "***UPI***"),
    # Email
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "***EMAIL***"),
    # Aadhaar (12 digits)
    (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "***AADHAAR***"),
    # PAN
    (re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"), "***PAN***"),
    # Bank account numbers (9-18 digits)
    (re.compile(r"\b\d{9,18}\b"), "***ACCOUNT***"),
]


def mask_pii(text: str) -> str:
    """Mask all PII in a text string (for log output).

    Args:
        text: Input text that may contain PII.

    Returns:
        Text with PII replaced by masked tokens.
    """
    for pattern, replacement in _MASK_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class PIIMaskingFilter(logging.Filter):
    """Python logging filter that masks PII in all log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Mask the message
        if isinstance(record.msg, str):
            record.msg = mask_pii(record.msg)
        # Mask args
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    mask_pii(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: mask_pii(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
        return True


def install_pii_filter(enable: bool = True) -> None:
    """Install PII masking filter on root logger."""
    root = logging.getLogger()
    if enable:
        f = PIIMaskingFilter()
        root.addFilter(f)
        logger.info("PII masking filter installed on root logger")
    else:
        logger.info("PII masking disabled (dev mode)")


# ---------------------------------------------------------------------------
# Weak XOR fallback (when cryptography not installed)
# ---------------------------------------------------------------------------

def _xor_encrypt(text: str) -> str:
    key = _derive_key()
    text_bytes = text.encode("utf-8")
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(text_bytes))
    return "ENC:" + base64.b64encode(xored).decode()


def _xor_decrypt(ciphertext: str) -> str:
    try:
        key = _derive_key()
        data = base64.b64decode(ciphertext[4:])
        xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return xored.decode("utf-8")
    except Exception:
        return "[DECRYPTION_ERROR]"
