"""
CyberLens — JWT Authentication + RBAC
==========================================
Roles:
  ADMIN          — Full system access, manage officers
  SP_OFFICER     — Senior superintendent, cross-district view
  INVESTIGATOR   — File cases, submit evidence, run analysis
  SUPERVISOR     — Review and approve evidence packages
  READ_ONLY      — Dashboard view only (auditors)

Every API call is scoped to officer's district unless SP_OFFICER/ADMIN.

Author: CyberLens Team — GPCSSI India
"""

import hashlib
import hmac
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger("cyberlens.auth")

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production-min-32-chars!!")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))  # 8 hours
REFRESH_TOKEN_EXPIRE_DAYS = 7


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

class Role(str, Enum):
    ADMIN = "ADMIN"
    SP_OFFICER = "SP_OFFICER"
    SUPERVISOR = "SUPERVISOR"
    INVESTIGATOR = "INVESTIGATOR"
    READ_ONLY = "READ_ONLY"


ROLE_PERMISSIONS: Dict[Role, List[str]] = {
    Role.ADMIN: ["*"],
    Role.SP_OFFICER: ["read:*", "write:*", "delete:cases", "cross_district"],
    Role.SUPERVISOR: ["read:*", "write:cases", "write:evidence", "approve:evidence"],
    Role.INVESTIGATOR: ["read:cases", "read:campaigns", "write:cases", "write:analysis",
                        "submit:i4c", "read:graph"],
    Role.READ_ONLY: ["read:dashboard", "read:campaigns", "read:heatmap"],
}


# ---------------------------------------------------------------------------
# Token dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TokenPayload:
    officer_id: str
    username: str
    role: str
    district: str
    badge_number: str
    exp: float
    iat: float = field(default_factory=lambda: time.time())
    jti: str = field(default_factory=lambda: secrets.token_hex(16))  # JWT ID


@dataclass
class OfficerInfo:
    officer_id: str
    username: str
    role: Role
    district: str
    badge_number: str
    full_name: str = ""
    email: str = ""
    phone: str = ""


# ---------------------------------------------------------------------------
# JWT helpers (pure Python — no PyJWT dependency needed)
# ---------------------------------------------------------------------------

import base64
import json


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * padding)


def create_access_token(payload: TokenPayload) -> str:
    """Create a signed JWT access token."""
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header).encode())

    claims = {
        "sub": payload.officer_id,
        "username": payload.username,
        "role": payload.role,
        "district": payload.district,
        "badge": payload.badge_number,
        "exp": payload.exp,
        "iat": payload.iat,
        "jti": payload.jti,
    }
    payload_b64 = _b64url_encode(json.dumps(claims).encode())

    signing_input = f"{header_b64}.{payload_b64}"
    sig = hmac.new(
        SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    sig_b64 = _b64url_encode(sig)

    return f"{signing_input}.{sig_b64}"


def verify_token(token: str) -> Optional[TokenPayload]:
    """Verify and decode a JWT token. Returns None if invalid."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}"

        expected_sig = hmac.new(
            SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256
        ).digest()
        actual_sig = _b64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            logger.warning("JWT signature verification failed")
            return None

        claims = json.loads(_b64url_decode(payload_b64))

        # Check expiry
        if claims.get("exp", 0) < time.time():
            logger.info("JWT token expired for officer: %s", claims.get("username"))
            return None

        return TokenPayload(
            officer_id=claims["sub"],
            username=claims["username"],
            role=claims["role"],
            district=claims["district"],
            badge_number=claims.get("badge", ""),
            exp=claims["exp"],
            iat=claims.get("iat", 0),
            jti=claims.get("jti", ""),
        )

    except Exception as e:
        logger.warning("JWT decode failed: %s", e)
        return None


def create_token_for_officer(
    officer_id: str, username: str, role: str,
    district: str, badge_number: str,
) -> Dict[str, str]:
    """Create access + refresh token pair for an officer."""
    now = time.time()
    access_payload = TokenPayload(
        officer_id=officer_id, username=username, role=role,
        district=district, badge_number=badge_number,
        exp=now + ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        iat=now,
    )
    refresh_payload = TokenPayload(
        officer_id=officer_id, username=username, role=role,
        district=district, badge_number=badge_number,
        exp=now + REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        iat=now,
    )
    return {
        "access_token": create_access_token(access_payload),
        "refresh_token": create_access_token(refresh_payload),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "role": role,
        "district": district,
    }


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)


def get_current_officer(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    request: Request = None,
) -> OfficerInfo:
    """FastAPI dependency: extract and verify JWT from Authorization header.

    Falls back to a demo officer if AUTH_DISABLED=true in .env (dev mode).
    """
    # Dev mode bypass
    if os.getenv("AUTH_DISABLED", "false").lower() == "true":
        return OfficerInfo(
            officer_id="dev-001",
            username="dev_officer",
            role=Role.ADMIN,
            district="ALL",
            badge_number="DEV-000",
            full_name="Development Officer",
        )

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return OfficerInfo(
        officer_id=payload.officer_id,
        username=payload.username,
        role=Role(payload.role),
        district=payload.district,
        badge_number=payload.badge_number,
    )


def require_role(*allowed_roles: Role):
    """FastAPI dependency factory: enforce role-based access."""
    def check_role(officer: OfficerInfo = Depends(get_current_officer)) -> OfficerInfo:
        if officer.role not in allowed_roles and officer.role != Role.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}",
            )
        return officer
    return check_role


def require_permission(permission: str):
    """FastAPI dependency factory: enforce specific permission."""
    def check_perm(officer: OfficerInfo = Depends(get_current_officer)) -> OfficerInfo:
        perms = ROLE_PERMISSIONS.get(officer.role, [])
        if "*" not in perms and permission not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}",
            )
        return officer
    return check_perm


def district_filter(
    officer: OfficerInfo = Depends(get_current_officer),
) -> Optional[str]:
    """Return the officer's district filter, or None if cross-district access allowed."""
    if officer.role in (Role.ADMIN, Role.SP_OFFICER):
        return None  # no filter — can see all districts
    return officer.district


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256."""
    salt = secrets.token_hex(32)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 260000
    )
    return f"pbkdf2:sha256:260000:{salt}:{dk.hex()}"


def verify_password(stored: str, provided: str) -> bool:
    """Verify a password against stored PBKDF2 hash."""
    try:
        _, algo, iterations, salt, stored_hash = stored.split(":")
        dk = hashlib.pbkdf2_hmac(
            algo, provided.encode(), salt.encode(), int(iterations)
        )
        return hmac.compare_digest(dk.hex(), stored_hash)
    except Exception:
        return False
