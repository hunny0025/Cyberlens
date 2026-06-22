"""
CyberLens — Victim Complaint Intake API
===========================================
Digital complaint form → auto-extract entities → cross-link campaigns.

Provides instant feedback: "Your complaint matches 47 others linked to campaign X"

Author: CyberLens Team — GPCSSI India
"""

import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("cyberlens.api.complaints")
router = APIRouter(prefix="/api/complaints", tags=["Victim Complaints"])


class ComplaintSubmission(BaseModel):
    victim_name: str
    victim_phone: str
    victim_email: str = ""
    victim_district: str
    scam_type: str           # Investment / Betting / Digital Arrest / etc.
    description: str         # Free text description of what happened
    amount_lost: float = 0.0
    currency: str = "INR"
    accused_phone: str = ""
    accused_upi: str = ""
    accused_url: str = ""
    accused_social: str = ""  # @username or t.me/channel
    date_of_incident: str = ""
    attachments: List[str] = []  # file paths for uploaded screenshots


# In-memory complaints store (replace with DB in production)
_COMPLAINTS: List[Dict[str, Any]] = []


@router.post("/submit")
async def submit_complaint(complaint: ComplaintSubmission):
    """Submit a new victim complaint.

    Auto-extracts entities, cross-links to active campaigns,
    and returns instant intelligence feedback.
    """
    complaint_id = "CMP-" + secrets.token_hex(6).upper()
    now = datetime.now(timezone.utc).isoformat()

    # Extract entities from description
    entities = _extract_entities(complaint.description)
    # Add explicitly provided entities
    if complaint.accused_phone:
        entities.append({"value": complaint.accused_phone, "type": "PHONE"})
    if complaint.accused_upi:
        entities.append({"value": complaint.accused_upi, "type": "UPI"})
    if complaint.accused_url:
        entities.append({"value": complaint.accused_url, "type": "URL"})
    if complaint.accused_social:
        entities.append({"value": complaint.accused_social, "type": "SOCIAL"})

    # Cross-link to active campaigns
    matches = _cross_link_campaigns(entities)

    # Store complaint
    record = {
        "complaint_id": complaint_id,
        "victim_name": complaint.victim_name,
        "victim_phone": complaint.victim_phone,
        "victim_district": complaint.victim_district,
        "scam_type": complaint.scam_type,
        "description": complaint.description[:500],
        "amount_lost": complaint.amount_lost,
        "accused_entities": entities,
        "date_of_incident": complaint.date_of_incident,
        "submitted_at": now,
        "status": "RECEIVED",
        "linked_campaigns": [m["campaign_id"] for m in matches],
    }
    _COMPLAINTS.append(record)

    # Build response
    response = {
        "complaint_id": complaint_id,
        "status": "RECEIVED",
        "submitted_at": now,
        "entities_extracted": len(entities),
        "entities": entities,
    }

    if matches:
        response["campaign_matches"] = matches
        response["intelligence_message"] = (
            f"⚠️ Your complaint matches {sum(m['total_linked_complaints'] for m in matches)} "
            f"other complaints linked to {len(matches)} active campaign(s). "
            f"Investigation is already underway."
        )
    else:
        response["campaign_matches"] = []
        response["intelligence_message"] = (
            "Your complaint has been recorded. Our AI system will monitor "
            "for similar patterns and link to campaigns as they are detected."
        )

    # Applicable legal sections
    from src.reports.fir_generator import get_sections_for_scam
    response["applicable_sections"] = get_sections_for_scam(complaint.scam_type)

    logger.info(
        "Complaint %s submitted: type=%s loss=₹%.0f matches=%d",
        complaint_id, complaint.scam_type, complaint.amount_lost, len(matches),
    )

    return response


@router.get("/")
async def list_complaints(
    district: Optional[str] = None,
    scam_type: Optional[str] = None,
    limit: int = 50,
):
    """List submitted complaints."""
    results = list(_COMPLAINTS)
    if district:
        results = [c for c in results if c["victim_district"] == district]
    if scam_type:
        results = [c for c in results if c["scam_type"] == scam_type]
    return {
        "complaints": results[-limit:][::-1],
        "total": len(results),
    }


@router.get("/{complaint_id}")
async def get_complaint(complaint_id: str):
    """Get complaint details."""
    for c in _COMPLAINTS:
        if c["complaint_id"] == complaint_id:
            return c
    raise HTTPException(status_code=404, detail="Complaint not found")


@router.get("/stats/summary")
async def complaint_stats():
    """Get complaint statistics."""
    total = len(_COMPLAINTS)
    total_loss = sum(c.get("amount_lost", 0) for c in _COMPLAINTS)
    by_type = {}
    for c in _COMPLAINTS:
        t = c.get("scam_type", "Unknown")
        by_type[t] = by_type.get(t, 0) + 1

    return {
        "total_complaints": total,
        "total_loss_inr": total_loss,
        "by_type": by_type,
        "linked_to_campaigns": sum(1 for c in _COMPLAINTS if c.get("linked_campaigns")),
    }


# ---------------------------------------------------------------------------
# Entity extraction from free text
# ---------------------------------------------------------------------------

def _extract_entities(text: str) -> List[Dict[str, str]]:
    """Extract phone numbers, UPI IDs, URLs, and Telegram links from text."""
    entities = []

    # Indian phone numbers
    phones = re.findall(r"(?:\+91[-\s]?)?[6-9]\d{9}", text)
    for p in phones:
        entities.append({"value": p.strip(), "type": "PHONE"})

    # UPI IDs
    upis = re.findall(r"[a-zA-Z0-9._-]+@[a-zA-Z]{2,10}", text)
    for u in upis:
        # Filter out email addresses
        if not u.endswith((".com", ".in", ".org", ".gov", ".net")):
            entities.append({"value": u, "type": "UPI"})

    # URLs
    urls = re.findall(r"https?://[^\s<>\"']+", text)
    for u in urls:
        entities.append({"value": u, "type": "URL"})

    # Telegram links
    tg = re.findall(r"t\.me/[a-zA-Z0-9_]+", text)
    for t in tg:
        entities.append({"value": t, "type": "TELEGRAM"})

    # Instagram handles
    ig = re.findall(r"@[a-zA-Z0-9_.]{3,30}", text)
    for handle in ig:
        entities.append({"value": handle, "type": "SOCIAL"})

    # Deduplicate
    seen = set()
    unique = []
    for e in entities:
        key = f"{e['type']}:{e['value']}"
        if key not in seen:
            seen.add(key)
            unique.append(e)

    return unique


def _cross_link_campaigns(entities: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Match extracted entities against known campaigns.

    In production: queries Neo4j graph for entity matches.
    Here: checks against demo campaign data.
    """
    # Demo campaigns (same as intelligence.py)
    campaigns = [
        {"campaign_id": "cpg-001", "name": "IPL Betting Ring — Gurugram",
         "entities": ["+919876543210", "betting@paytm", "t.me/ipl_vip_tips"],
         "complaints": 47, "risk_level": "CRITICAL"},
        {"campaign_id": "cpg-002", "name": "Fake Zerodha Network",
         "entities": ["+918765432109", "invest@gpay", "t.me/zerodha_official2"],
         "complaints": 28, "risk_level": "HIGH"},
        {"campaign_id": "cpg-003", "name": "Digital Arrest Ring — NCR",
         "entities": ["+917654321098"],
         "complaints": 15, "risk_level": "CRITICAL"},
    ]

    matches = []
    entity_values = {e["value"] for e in entities}

    for camp in campaigns:
        overlap = entity_values.intersection(set(camp["entities"]))
        if overlap:
            matches.append({
                "campaign_id": camp["campaign_id"],
                "campaign_name": camp["name"],
                "risk_level": camp["risk_level"],
                "matching_entities": list(overlap),
                "total_linked_complaints": camp["complaints"],
            })

    return matches
