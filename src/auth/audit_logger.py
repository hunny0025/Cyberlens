"""
CyberLens — Audit Logger
============================
Immutable append-only audit trail.
Every action logged with: officer_id, action, timestamp, IP, resource, outcome.

Mandatory for:
  - Court-admissible evidence (IT Act §65B)
  - CERT-In compliance
  - Govt security audit trail

Format: JSONL (one JSON object per line — append only, never delete)

Author: CyberLens Team — GPCSSI India
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("cyberlens.auth.audit")

AUDIT_LOG_PATH = Path(os.getenv("AUDIT_LOG_DIR", "logs/audit")) / "audit.jsonl"


@dataclass
class AuditEvent:
    """A single immutable audit event."""
    event_id: str          # unique event ID
    timestamp: str         # ISO 8601 UTC
    officer_id: str
    username: str
    badge_number: str
    district: str
    action: str            # LOGIN / LOGOUT / VIEW_EVIDENCE / SUBMIT_I4C / etc.
    resource: str          # what was accessed
    resource_id: str       # e.g. campaign ID, case ID
    outcome: str           # SUCCESS / DENIED / ERROR
    ip_address: str
    user_agent: str
    extra: Dict[str, Any] = field(default_factory=dict)
    prev_hash: str = ""    # hash of previous event (chain integrity)
    this_hash: str = ""    # hash of this event


class AuditLogger:
    """Append-only audit log with hash chain for tamper detection.

    Each event includes the SHA256 of the previous event,
    forming a chain. Any tampering breaks the chain.
    """

    _last_hash: str = "GENESIS"

    def __init__(self):
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._load_last_hash()

    def _load_last_hash(self) -> None:
        """Load the hash of the last recorded event."""
        if not AUDIT_LOG_PATH.exists():
            return
        try:
            with open(AUDIT_LOG_PATH, "rb") as f:
                # Seek to last non-empty line
                f.seek(0, 2)  # end
                pos = f.tell()
                last_line = b""
                while pos > 0:
                    pos -= 1
                    f.seek(pos)
                    char = f.read(1)
                    if char == b"\n" and last_line:
                        break
                    last_line = char + last_line
                if last_line:
                    event = json.loads(last_line)
                    AuditLogger._last_hash = event.get("this_hash", "GENESIS")
        except Exception:
            pass

    def log(
        self,
        officer_id: str,
        username: str,
        badge_number: str,
        district: str,
        action: str,
        resource: str,
        resource_id: str = "",
        outcome: str = "SUCCESS",
        ip_address: str = "unknown",
        user_agent: str = "",
        **extra,
    ) -> str:
        """Log an audit event.

        Args:
            officer_id: Officer's unique ID.
            action: Action performed (LOGIN, VIEW_EVIDENCE, SUBMIT_I4C, etc.)
            resource: Resource type accessed.
            resource_id: Specific resource ID.
            outcome: SUCCESS / DENIED / ERROR.
            ip_address: Officer's IP address.

        Returns:
            Event ID for reference.
        """
        import secrets
        event_id = secrets.token_hex(12)
        ts = datetime.now(timezone.utc).isoformat()

        event = AuditEvent(
            event_id=event_id,
            timestamp=ts,
            officer_id=officer_id,
            username=username,
            badge_number=badge_number,
            district=district,
            action=action,
            resource=resource,
            resource_id=resource_id,
            outcome=outcome,
            ip_address=ip_address,
            user_agent=user_agent,
            extra=extra,
            prev_hash=AuditLogger._last_hash,
        )

        # Compute hash of this event (without this_hash field)
        event_dict = asdict(event)
        del event_dict["this_hash"]
        event_json = json.dumps(event_dict, sort_keys=True)
        event.this_hash = hashlib.sha256(event_json.encode()).hexdigest()

        # Append to log (atomic write)
        try:
            with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(event)) + "\n")
            AuditLogger._last_hash = event.this_hash
        except Exception as e:
            logger.error("AUDIT LOG WRITE FAILED: %s — %s", event_id, e)

        logger.info("AUDIT|%s|%s|%s|%s|%s", action, username, resource, resource_id, outcome)
        return event_id

    def verify_chain(self) -> Dict[str, Any]:
        """Verify the hash chain for tamper detection.

        Returns:
            Dict with 'valid', 'total_events', 'first_broken_at' if tampered.
        """
        if not AUDIT_LOG_PATH.exists():
            return {"valid": True, "total_events": 0}

        prev_hash = "GENESIS"
        total = 0
        first_broken = None

        try:
            with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    event = json.loads(line)

                    # Recompute hash
                    event_copy = dict(event)
                    stored_hash = event_copy.pop("this_hash", "")
                    expected_hash = hashlib.sha256(
                        json.dumps(event_copy, sort_keys=True).encode()
                    ).hexdigest()

                    if event.get("prev_hash") != prev_hash:
                        if not first_broken:
                            first_broken = {"line": line_num, "event_id": event.get("event_id")}
                    if expected_hash != stored_hash:
                        if not first_broken:
                            first_broken = {"line": line_num, "event_id": event.get("event_id"), "reason": "hash_mismatch"}

                    prev_hash = stored_hash
                    total += 1

        except Exception as e:
            return {"valid": False, "error": str(e), "total_events": total}

        return {
            "valid": first_broken is None,
            "total_events": total,
            "first_broken_at": first_broken,
            "last_hash": prev_hash,
        }

    def query(
        self,
        officer_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """Query recent audit events."""
        if not AUDIT_LOG_PATH.exists():
            return []

        events = []
        try:
            with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    event = json.loads(line)
                    if officer_id and event.get("officer_id") != officer_id:
                        continue
                    if action and event.get("action") != action:
                        continue
                    events.append(event)
        except Exception:
            pass

        return events[-limit:][::-1]  # most recent first


# ── Singleton ─────────────────────────────────────────────────
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
