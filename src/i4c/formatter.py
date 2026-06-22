"""
CyberLens — I4C Case Formatter
==================================
Formats case data into I4C (Indian Cybercrime Coordination Centre)
standard submission format for cybercrime.gov.in.
"""

import datetime
import logging
from typing import Dict

logger = logging.getLogger("cyberlens.i4c")

# I4C category mapping
I4C_CATEGORIES = {
    "Real Money Betting": "Online Gambling / Betting",
    "Investment Scam": "Online Financial Fraud",
    "Fake Customer Care": "Online Financial Fraud / Phishing",
}

# Content type mapping
CONTENT_TYPES = {
    "UPLOAD": "IMAGE",
    "CRAWLER": "SOCIAL_MEDIA_POST",
}


def format_case(case) -> Dict:
    """Format a CyberLens case into I4C submission format.

    Args:
        case: SQLAlchemy Case object.

    Returns:
        Dict in I4C standard format.
    """
    # Build evidence summary
    evidence_parts = []

    if case.scam_category:
        evidence_parts.append(
            f"Category: {case.scam_category} "
            f"(confidence: {(case.scam_confidence or 0)*100:.1f}%)"
        )

    if case.deepfake_suspected:
        evidence_parts.append(
            f"DEEPFAKE DETECTED: probability {(case.deepfake_probability or 0)*100:.1f}%, "
            f"{case.face_count or 0} face(s) detected"
        )

    if case.ocr_text:
        evidence_parts.append(
            f"Extracted text ({len(case.ocr_text)} chars): "
            f"{case.ocr_text[:300]}..."
        )

    # Entity summary
    if case.entities:
        phones = [e.value for e in case.entities if e.entity_type == "PHONE"]
        upis = [e.value for e in case.entities if e.entity_type == "UPI"]
        urls = [e.value for e in case.entities if e.entity_type == "URL"]

        if phones:
            evidence_parts.append(f"Phone numbers: {', '.join(phones[:5])}")
        if upis:
            evidence_parts.append(f"UPI IDs: {', '.join(upis[:5])}")
        if urls:
            evidence_parts.append(f"URLs: {', '.join(urls[:3])}")

    evidence_summary = "\n".join(evidence_parts)

    # Build description
    description = (
        f"CyberLens AI Detection Report — Case {case.case_number}\n\n"
        f"Category: {case.scam_category or 'Under review'}\n"
        f"Severity: {case.severity or 'MEDIUM'}\n"
        f"AI Confidence: {(case.scam_confidence or 0)*100:.1f}%\n\n"
        f"This case was automatically detected and classified by the "
        f"CyberLens AI system deployed at Gurugram Police Cyber Cell. "
        f"The content has been analyzed using DistilBERT multilingual "
        f"text classification, Tesseract OCR, and EfficientNet deepfake "
        f"detection models.\n\n"
        f"Applicable sections: {case.it_act_section or 'Under review'}"
    )

    # Get officer info
    officer_name = "Gurugram Cyber Cell"
    if case.officer and case.officer.name:
        officer_name = f"{case.officer.rank} {case.officer.name} ({case.officer.badge_number})"

    return {
        "content_url": case.source_url or "Uploaded directly to CyberLens",
        "content_type": CONTENT_TYPES.get(case.source_type, "OTHER"),
        "violation_category": I4C_CATEGORIES.get(
            case.scam_category, "Other Cyber Crime"
        ),
        "it_act_section": case.it_act_section or "Under review",
        "description": description,
        "evidence_summary": evidence_summary,
        "reporting_officer": officer_name,
        "station": "Gurugram Cyber Crime Police Station, Sector 29",
        "timestamp": str(case.created_at or datetime.datetime.now()),
        "case_number": case.case_number,
    }
