"""
CyberLens — Authentication API Routes
==========================================
Login, logout, token refresh, officer management.

Author: CyberLens Team — GPCSSI India
"""

import logging
import os
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from src.auth.jwt_auth import (
    OfficerInfo, Role, create_token_for_officer, get_current_officer,
    hash_password, require_role, verify_password,
)
from src.auth.audit_logger import get_audit_logger

logger = logging.getLogger("cyberlens.api.auth")
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# In-memory officer store (replace with DB in production)
# ---------------------------------------------------------------------------

# Default officers seeded for dev
_OFFICERS = {
    "admin": {
        "officer_id": "off-001",
        "username": "admin",
        "password_hash": hash_password("cyberlens@2025"),
        "role": Role.ADMIN,
        "district": "ALL",
        "badge_number": "ADMIN-001",
        "full_name": "System Administrator",
        "email": "admin@gpcssi.gov.in",
    },
    "inspector_gurugram": {
        "officer_id": "off-002",
        "username": "inspector_gurugram",
        "password_hash": hash_password("gurugram@123"),
        "role": Role.INVESTIGATOR,
        "district": "Gurugram",
        "badge_number": "GGM-2024-147",
        "full_name": "Inspector Rajesh Kumar",
        "email": "rajesh.kumar@gurugram.police.gov.in",
    },
    "sp_ncr": {
        "officer_id": "off-003",
        "username": "sp_ncr",
        "password_hash": hash_password("sp@secure99"),
        "role": Role.SP_OFFICER,
        "district": "ALL",
        "badge_number": "NCR-SP-042",
        "full_name": "Superintendent of Police (NCR)",
        "email": "sp@haryana.police.gov.in",
    },
}


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class CreateOfficerRequest(BaseModel):
    username: str
    password: str
    role: str
    district: str
    badge_number: str
    full_name: str
    email: str = ""
    phone: str = ""


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login")
async def login(req: LoginRequest, request: Request):
    """Login with badge credentials. Returns JWT token pair."""
    audit = get_audit_logger()
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")

    officer_data = _OFFICERS.get(req.username)
    if not officer_data or not verify_password(officer_data["password_hash"], req.password):
        audit.log(
            officer_id="unknown", username=req.username, badge_number="",
            district="", action="LOGIN", resource="auth", outcome="DENIED",
            ip_address=ip, user_agent=ua, reason="invalid_credentials",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Contact your system administrator.",
        )

    tokens = create_token_for_officer(
        officer_id=officer_data["officer_id"],
        username=officer_data["username"],
        role=officer_data["role"].value,
        district=officer_data["district"],
        badge_number=officer_data["badge_number"],
    )

    audit.log(
        officer_id=officer_data["officer_id"],
        username=officer_data["username"],
        badge_number=officer_data["badge_number"],
        district=officer_data["district"],
        action="LOGIN",
        resource="auth",
        outcome="SUCCESS",
        ip_address=ip,
        user_agent=ua,
    )

    return {
        **tokens,
        "officer_id": officer_data["officer_id"],
        "full_name": officer_data["full_name"],
        "badge_number": officer_data["badge_number"],
        "district": officer_data["district"],
    }


@router.post("/logout")
async def logout(
    request: Request,
    officer: OfficerInfo = Depends(get_current_officer),
):
    """Logout and invalidate token (client-side + audit log)."""
    audit = get_audit_logger()
    audit.log(
        officer_id=officer.officer_id, username=officer.username,
        badge_number=officer.badge_number, district=officer.district,
        action="LOGOUT", resource="auth", outcome="SUCCESS",
        ip_address=request.client.host if request.client else "unknown",
    )
    return {"status": "logged_out", "message": "Token invalidated. Please login again."}


@router.get("/me")
async def get_current_officer_info(officer: OfficerInfo = Depends(get_current_officer)):
    """Get current officer profile."""
    return {
        "officer_id": officer.officer_id,
        "username": officer.username,
        "role": officer.role.value,
        "district": officer.district,
        "badge_number": officer.badge_number,
        "full_name": officer.full_name,
        "permissions": [p for p in _get_role_perms(officer.role)],
    }


@router.post("/officers", dependencies=[Depends(require_role(Role.ADMIN))])
async def create_officer(
    req: CreateOfficerRequest,
    request: Request,
    officer: OfficerInfo = Depends(get_current_officer),
):
    """Create a new officer account (ADMIN only)."""
    import secrets as _s
    if req.username in _OFFICERS:
        raise HTTPException(status_code=400, detail="Username already exists")

    new_id = "off-" + _s.token_hex(4)
    _OFFICERS[req.username] = {
        "officer_id": new_id,
        "username": req.username,
        "password_hash": hash_password(req.password),
        "role": Role(req.role),
        "district": req.district,
        "badge_number": req.badge_number,
        "full_name": req.full_name,
        "email": req.email,
    }

    audit = get_audit_logger()
    audit.log(
        officer_id=officer.officer_id, username=officer.username,
        badge_number=officer.badge_number, district=officer.district,
        action="CREATE_OFFICER", resource="officer", resource_id=new_id,
        outcome="SUCCESS", ip_address=request.client.host if request.client else "unknown",
        created_username=req.username, created_role=req.role, created_district=req.district,
    )

    return {"status": "created", "officer_id": new_id, "username": req.username}


@router.get("/officers", dependencies=[Depends(require_role(Role.ADMIN, Role.SP_OFFICER))])
async def list_officers():
    """List all officers (ADMIN/SP_OFFICER only)."""
    return {
        "officers": [
            {
                "officer_id": d["officer_id"], "username": d["username"],
                "role": d["role"].value, "district": d["district"],
                "badge_number": d["badge_number"], "full_name": d["full_name"],
            }
            for d in _OFFICERS.values()
        ]
    }


@router.get("/audit-log", dependencies=[Depends(require_role(Role.ADMIN, Role.SP_OFFICER))])
async def get_audit_log(action: Optional[str] = None, limit: int = 100):
    """Get audit log entries."""
    audit = get_audit_logger()
    events = audit.query(action=action, limit=limit)
    return {"events": events, "total": len(events)}


@router.get("/audit-log/verify")
async def verify_audit_chain(officer: OfficerInfo = Depends(require_role(Role.ADMIN))):
    """Verify audit log hash chain integrity."""
    audit = get_audit_logger()
    return audit.verify_chain()


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    request: Request,
    officer: OfficerInfo = Depends(get_current_officer),
):
    """Change officer's own password."""
    officer_data = _OFFICERS.get(officer.username)
    if not officer_data or not verify_password(officer_data["password_hash"], req.current_password):
        raise HTTPException(status_code=401, detail="Current password incorrect")

    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    officer_data["password_hash"] = hash_password(req.new_password)
    audit = get_audit_logger()
    audit.log(
        officer_id=officer.officer_id, username=officer.username,
        badge_number=officer.badge_number, district=officer.district,
        action="CHANGE_PASSWORD", resource="auth", outcome="SUCCESS",
        ip_address=request.client.host if request.client else "unknown",
    )
    return {"status": "password_changed"}


def _get_role_perms(role: Role):
    from src.auth.jwt_auth import ROLE_PERMISSIONS
    return ROLE_PERMISSIONS.get(role, [])
