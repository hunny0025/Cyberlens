"""
CyberLens — Actions API Routes
==================================
Operational actions: FIR generation, NPCI freeze, OSINT enrichment,
evidence custody, §65B certification.

Author: CyberLens Team — GPCSSI India
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth.jwt_auth import OfficerInfo, Role, get_current_officer, require_role

logger = logging.getLogger("cyberlens.api.actions")
router = APIRouter(prefix="/api/actions", tags=["Operational Actions"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class FIRRequest(BaseModel):
    campaign_id: str
    campaign_name: str
    scam_type: str
    accused_details: List[Dict[str, str]]
    evidence_items: List[Dict[str, str]] = []
    victim_statements: List[Dict[str, str]]
    police_station: str = "Cyber Crime Cell"


class BulkFIRRequest(FIRRequest):
    pass  # Same structure, generates one FIR per victim


class FreezeUPIRequest(BaseModel):
    upi_id: str
    campaign_id: str
    campaign_name: str
    reason: str = "Scam UPI ID detected in active cybercrime campaign"
    fir_numbers: List[str] = []
    evidence_hashes: List[str] = []


class OSINTRequest(BaseModel):
    value: str
    entity_type: str  # PHONE / DOMAIN / URL / UPI


class EvidenceCollectRequest(BaseModel):
    file_path: str
    campaign_id: str
    source_url: str = ""
    platform: str = ""
    notes: str = ""


# ---------------------------------------------------------------------------
# FIR Generation
# ---------------------------------------------------------------------------

@router.post("/generate-fir")
async def generate_fir(
    req: FIRRequest,
    officer: OfficerInfo = Depends(get_current_officer),
):
    """Generate a single FIR PDF with IT Act sections."""
    from src.reports.fir_generator import FIRGenerator
    from src.auth.audit_logger import get_audit_logger

    gen = FIRGenerator()
    result = gen.generate_fir(
        campaign_id=req.campaign_id,
        campaign_name=req.campaign_name,
        scam_type=req.scam_type,
        accused_details=req.accused_details,
        evidence_items=req.evidence_items,
        victim_statements=req.victim_statements,
        investigating_officer=officer.full_name or officer.username,
        officer_badge=officer.badge_number,
        police_station=req.police_station,
        district=officer.district,
    )

    # Audit
    get_audit_logger().log(
        officer_id=officer.officer_id, username=officer.username,
        badge_number=officer.badge_number, district=officer.district,
        action="GENERATE_FIR", resource="fir",
        resource_id=result.get("fir_number", ""),
        outcome="SUCCESS", ip_address="api",
        campaign_id=req.campaign_id,
    )

    return result


@router.post("/generate-bulk-firs")
async def generate_bulk_firs(
    req: BulkFIRRequest,
    officer: OfficerInfo = Depends(get_current_officer),
):
    """Generate one FIR per victim in a campaign batch."""
    from src.reports.fir_generator import FIRGenerator
    from src.auth.audit_logger import get_audit_logger

    gen = FIRGenerator()
    result = gen.generate_bulk_firs(
        campaign_id=req.campaign_id,
        campaign_name=req.campaign_name,
        scam_type=req.scam_type,
        accused_details=req.accused_details,
        evidence_items=req.evidence_items,
        victim_statements=req.victim_statements,
        investigating_officer=officer.full_name or officer.username,
        officer_badge=officer.badge_number,
        police_station=req.police_station,
        district=officer.district,
    )

    get_audit_logger().log(
        officer_id=officer.officer_id, username=officer.username,
        badge_number=officer.badge_number, district=officer.district,
        action="GENERATE_BULK_FIRS", resource="fir",
        resource_id=req.campaign_id,
        outcome="SUCCESS", ip_address="api",
        total_firs=result["total_firs"],
    )

    return result


# ---------------------------------------------------------------------------
# NPCI UPI Freeze
# ---------------------------------------------------------------------------

@router.post("/freeze-upi")
async def freeze_upi(
    req: FreezeUPIRequest,
    officer: OfficerInfo = Depends(get_current_officer),
):
    """Create and submit a UPI freeze request to NPCI."""
    from src.reports.npci_freeze import NPCIFreezeManager
    from src.auth.audit_logger import get_audit_logger

    mgr = NPCIFreezeManager()
    freeze_req = mgr.create_freeze_request(
        upi_id=req.upi_id,
        campaign_id=req.campaign_id,
        campaign_name=req.campaign_name,
        officer_id=officer.officer_id,
        officer_badge=officer.badge_number,
        district=officer.district,
        reason=req.reason,
        fir_numbers=req.fir_numbers,
        evidence_hashes=req.evidence_hashes,
    )

    # Auto-submit
    submit_result = mgr.submit_freeze(freeze_req.request_id)

    get_audit_logger().log(
        officer_id=officer.officer_id, username=officer.username,
        badge_number=officer.badge_number, district=officer.district,
        action="FREEZE_UPI", resource="npci",
        resource_id=freeze_req.request_id,
        outcome=submit_result.get("status", "UNKNOWN"), ip_address="api",
        upi_id=req.upi_id, campaign_id=req.campaign_id,
    )

    return {
        "freeze_request": freeze_req.__dict__,
        "submission": submit_result,
    }


@router.get("/freeze-upi")
async def list_freeze_requests(
    campaign_id: Optional[str] = None,
    officer: OfficerInfo = Depends(get_current_officer),
):
    """List all UPI freeze requests."""
    from src.reports.npci_freeze import NPCIFreezeManager
    mgr = NPCIFreezeManager()
    return {"requests": mgr.list_requests(campaign_id)}


# ---------------------------------------------------------------------------
# OSINT Enrichment
# ---------------------------------------------------------------------------

@router.post("/osint-enrich")
async def osint_enrich(
    req: OSINTRequest,
    officer: OfficerInfo = Depends(get_current_officer),
):
    """Enrich an entity with OSINT data (WHOIS, Safe Browsing, carrier)."""
    from src.osint.osint_module import OSINTModule

    osint = OSINTModule()
    result = osint.enrich_entity(req.value, req.entity_type)

    from src.auth.audit_logger import get_audit_logger
    get_audit_logger().log(
        officer_id=officer.officer_id, username=officer.username,
        badge_number=officer.badge_number, district=officer.district,
        action="OSINT_ENRICH", resource="osint",
        resource_id=req.value, outcome="SUCCESS", ip_address="api",
        entity_type=req.entity_type,
    )

    return result


# ---------------------------------------------------------------------------
# Evidence Custody
# ---------------------------------------------------------------------------

@router.post("/collect-evidence")
async def collect_evidence(
    req: EvidenceCollectRequest,
    officer: OfficerInfo = Depends(get_current_officer),
):
    """Collect a file as evidence with §65B chain of custody."""
    from src.auth.custody_chain import get_custody_chain

    chain = get_custody_chain()
    record = chain.collect_evidence(
        file_path=req.file_path,
        campaign_id=req.campaign_id,
        officer_id=officer.officer_id,
        officer_badge=officer.badge_number,
        officer_name=officer.full_name or officer.username,
        district=officer.district,
        source_url=req.source_url,
        platform=req.platform,
        notes=req.notes,
    )

    return {
        "evidence_id": record.evidence_id,
        "file_hash": record.file_hash_sha256,
        "status": "COLLECTED",
        "custody_record_id": record.record_id,
    }


@router.post("/certify-evidence/{campaign_id}")
async def certify_evidence(
    campaign_id: str,
    officer: OfficerInfo = Depends(get_current_officer),
):
    """Generate IT Act §65B certificate for all evidence in a campaign."""
    from src.auth.custody_chain import get_custody_chain
    from src.reports.fir_generator import get_sections_for_scam

    chain = get_custody_chain()
    cert = chain.generate_section_65b_certificate(
        campaign_id=campaign_id,
        campaign_name=f"Campaign {campaign_id}",
        officer_id=officer.officer_id,
        officer_badge=officer.badge_number,
        officer_name=officer.full_name or officer.username,
        district=officer.district,
        it_act_sections=["66D", "66C", "66"],
    )

    return {
        "certificate_id": cert.certificate_id,
        "campaign_id": cert.campaign_id,
        "total_evidence_items": cert.total_items,
        "overall_hash": cert.overall_hash,
        "issue_date": cert.issue_date,
    }


@router.get("/verify-evidence/{campaign_id}/{evidence_id}")
async def verify_evidence(
    campaign_id: str, evidence_id: str,
    officer: OfficerInfo = Depends(get_current_officer),
):
    """Verify integrity of a specific evidence item."""
    from src.auth.custody_chain import get_custody_chain
    chain = get_custody_chain()
    return chain.verify_evidence_integrity(evidence_id, campaign_id)
