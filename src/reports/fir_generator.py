"""
CyberLens — Bulk FIR PDF Generator
======================================
Generate court-ready FIR PDFs with IT Act sections,
evidence hashes, accused details, and victim statements.

Outputs CCPWC-format PDFs for batch filing.

Author: CyberLens Team — GPCSSI India
"""

import hashlib
import io
import logging
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cyberlens.reports.fir")

FIR_OUTPUT_DIR = Path(os.getenv("FIR_OUTPUT_DIR", "data/reports/fir"))


# ---------------------------------------------------------------------------
# IT Act Section Mapping (comprehensive)
# ---------------------------------------------------------------------------

SCAM_TO_SECTIONS = {
    "Real Money Betting": {
        "it_act": ["66D (Cheating by personation)", "66 (Computer-related offences)"],
        "bns": ["318 (Cheating)", "319 (Cheating by personation)"],
        "other": ["Public Gambling Act, 1867 - Section 4, 5"],
    },
    "Investment Scam": {
        "it_act": ["66D (Cheating by personation)", "66C (Identity theft)", "43 (Unauthorized access)"],
        "bns": ["318 (Cheating)", "316 (Criminal breach of trust)", "319 (Cheating by personation)"],
        "other": ["SEBI Act - Section 12A, 15G"],
    },
    "Digital Arrest": {
        "it_act": ["66D (Cheating by personation)", "66 (Computer-related offences)"],
        "bns": ["308 (Extortion)", "319 (Cheating by personation)", "351 (Criminal intimidation)"],
        "other": [],
    },
    "Customer Care Fraud": {
        "it_act": ["66D (Cheating by personation)", "66C (Identity theft)"],
        "bns": ["318 (Cheating)", "319 (Cheating by personation)"],
        "other": [],
    },
    "Job Scam": {
        "it_act": ["66D (Cheating by personation)"],
        "bns": ["318 (Cheating)", "316 (Criminal breach of trust)"],
        "other": [],
    },
    "Sextortion": {
        "it_act": ["66E (Privacy violation)", "67 (Publishing obscene material)",
                    "67A (Publishing sexually explicit material)"],
        "bns": ["308 (Extortion)", "351 (Criminal intimidation)", "79 (Insult modesty)"],
        "other": ["POCSO Act (if minor involved)"],
    },
}


def get_sections_for_scam(scam_type: str) -> Dict[str, List[str]]:
    """Get applicable legal sections for a scam type."""
    return SCAM_TO_SECTIONS.get(scam_type, {
        "it_act": ["66 (Computer-related offences)"],
        "bns": ["318 (Cheating)"],
        "other": [],
    })


# ---------------------------------------------------------------------------
# FIR Generator
# ---------------------------------------------------------------------------

class FIRGenerator:
    """Generate bulk FIR PDFs in CCPWC format."""

    def __init__(self):
        FIR_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def generate_fir(
        self,
        campaign_id: str,
        campaign_name: str,
        scam_type: str,
        accused_details: List[Dict[str, str]],
        evidence_items: List[Dict[str, str]],
        victim_statements: List[Dict[str, str]],
        investigating_officer: str,
        officer_badge: str,
        police_station: str,
        district: str,
    ) -> Dict[str, Any]:
        """Generate a single FIR PDF.

        Args:
            campaign_id: Associated campaign.
            scam_type: Category of scam.
            accused_details: List of dicts with name/phone/upi/platform.
            evidence_items: List of dicts with file_path/hash/description.
            victim_statements: List of dicts with name/phone/statement/loss.

        Returns:
            Dict with file path and FIR metadata.
        """
        fir_number = f"FIR-{district[:3].upper()}-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        sections = get_sections_for_scam(scam_type)
        now = datetime.now()

        try:
            pdf_path = self._generate_pdf(
                fir_number=fir_number,
                campaign_id=campaign_id,
                campaign_name=campaign_name,
                scam_type=scam_type,
                sections=sections,
                accused_details=accused_details,
                evidence_items=evidence_items,
                victim_statements=victim_statements,
                investigating_officer=investigating_officer,
                officer_badge=officer_badge,
                police_station=police_station,
                district=district,
                date=now,
            )
        except Exception as e:
            logger.error("FIR PDF generation failed: %s", e)
            pdf_path = None

        return {
            "fir_number": fir_number,
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "scam_type": scam_type,
            "sections": sections,
            "accused_count": len(accused_details),
            "evidence_count": len(evidence_items),
            "victim_count": len(victim_statements),
            "investigating_officer": investigating_officer,
            "officer_badge": officer_badge,
            "police_station": police_station,
            "district": district,
            "generated_at": now.isoformat(),
            "pdf_path": str(pdf_path) if pdf_path else None,
        }

    def generate_bulk_firs(
        self,
        campaign_id: str,
        campaign_name: str,
        scam_type: str,
        accused_details: List[Dict[str, str]],
        evidence_items: List[Dict[str, str]],
        victim_statements: List[Dict[str, str]],
        investigating_officer: str,
        officer_badge: str,
        police_station: str,
        district: str,
    ) -> Dict[str, Any]:
        """Generate one FIR per victim in a batch.

        Returns:
            Dict with list of generated FIRs and summary.
        """
        firs = []
        for victim in victim_statements:
            result = self.generate_fir(
                campaign_id=campaign_id,
                campaign_name=campaign_name,
                scam_type=scam_type,
                accused_details=accused_details,
                evidence_items=evidence_items,
                victim_statements=[victim],
                investigating_officer=investigating_officer,
                officer_badge=officer_badge,
                police_station=police_station,
                district=district,
            )
            firs.append(result)

        return {
            "campaign_id": campaign_id,
            "total_firs": len(firs),
            "firs": firs,
            "total_loss": sum(
                float(v.get("loss", 0)) for v in victim_statements
            ),
            "generated_at": datetime.now().isoformat(),
        }

    def _generate_pdf(self, **kwargs) -> Optional[Path]:
        """Generate the actual PDF using reportlab."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

            fir_number = kwargs["fir_number"]
            pdf_path = FIR_OUTPUT_DIR / f"{fir_number}.pdf"

            doc = SimpleDocTemplate(
                str(pdf_path), pagesize=A4,
                leftMargin=20 * mm, rightMargin=20 * mm,
                topMargin=15 * mm, bottomMargin=15 * mm,
            )

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                "FIRTitle", parent=styles["Title"],
                fontSize=16, textColor=colors.HexColor("#1e3a5f"),
            )
            heading_style = ParagraphStyle(
                "FIRHeading", parent=styles["Heading2"],
                fontSize=12, textColor=colors.HexColor("#1e3a5f"),
                spaceAfter=6,
            )
            body_style = ParagraphStyle(
                "FIRBody", parent=styles["Normal"],
                fontSize=10, leading=14,
            )

            elements = []

            # Header
            elements.append(Paragraph(
                "FIRST INFORMATION REPORT (FIR)", title_style
            ))
            elements.append(Paragraph(
                f"Under Section 154 Cr.P.C. / Section 173 BNSS", body_style
            ))
            elements.append(Spacer(1, 10))

            # Meta table
            meta = [
                ["FIR Number", fir_number, "Date", kwargs["date"].strftime("%d/%m/%Y")],
                ["Police Station", kwargs["police_station"], "District", kwargs["district"]],
                ["Campaign ID", kwargs["campaign_id"], "Scam Type", kwargs["scam_type"]],
                ["IO Name", kwargs["investigating_officer"], "Badge", kwargs["officer_badge"]],
            ]
            t = Table(meta, colWidths=[80, 150, 80, 150])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e2e8f0")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#e2e8f0")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 12))

            # Applicable Sections
            sections = kwargs["sections"]
            elements.append(Paragraph("APPLICABLE SECTIONS", heading_style))
            sec_text = ""
            for category, sec_list in sections.items():
                sec_text += f"<b>{category.upper()}:</b> {'; '.join(sec_list)}<br/>"
            elements.append(Paragraph(sec_text, body_style))
            elements.append(Spacer(1, 10))

            # Accused Details
            elements.append(Paragraph("ACCUSED / SUSPECT DETAILS", heading_style))
            for i, acc in enumerate(kwargs["accused_details"], 1):
                acc_text = f"{i}. "
                for k, v in acc.items():
                    acc_text += f"{k}: <b>{v}</b> | "
                elements.append(Paragraph(acc_text.rstrip(" | "), body_style))
            elements.append(Spacer(1, 10))

            # Evidence
            elements.append(Paragraph("DIGITAL EVIDENCE", heading_style))
            for i, ev in enumerate(kwargs["evidence_items"], 1):
                ev_text = (
                    f"{i}. {ev.get('description', 'Screenshot')} — "
                    f"SHA256: <font size=8>{ev.get('hash', 'N/A')[:32]}...</font>"
                )
                elements.append(Paragraph(ev_text, body_style))
            elements.append(Spacer(1, 10))

            # Victim Statements
            elements.append(Paragraph("VICTIM STATEMENT(S)", heading_style))
            for i, v in enumerate(kwargs["victim_statements"], 1):
                v_text = (
                    f"{i}. Name: <b>{v.get('name', 'Anonymous')}</b> | "
                    f"Loss: ₹{v.get('loss', 'Unknown')} | "
                    f"Statement: {v.get('statement', 'N/A')[:200]}"
                )
                elements.append(Paragraph(v_text, body_style))
            elements.append(Spacer(1, 20))

            # Certificate
            elements.append(Paragraph("§65B CERTIFICATION", heading_style))
            cert_text = (
                "I certify under Section 65B of the Information Technology Act, 2000 "
                "that the electronic records annexed herein were produced during the "
                "ordinary course of monitoring activity by CyberLens v3.0, operated by "
                f"the Cyber Cell, {kwargs['police_station']}, {kwargs['district']}. "
                "The system was operating properly. The information is accurate."
            )
            elements.append(Paragraph(cert_text, body_style))
            elements.append(Spacer(1, 30))

            # Signature
            sig_data = [
                ["Investigating Officer", "", "Signature"],
                [kwargs["investigating_officer"], "", "____________________"],
                [f"Badge: {kwargs['officer_badge']}", "",
                 f"Date: {kwargs['date'].strftime('%d/%m/%Y')}"],
            ]
            sig_table = Table(sig_data, colWidths=[200, 60, 200])
            sig_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ]))
            elements.append(sig_table)

            # Footer
            elements.append(Spacer(1, 20))
            elements.append(Paragraph(
                f"<font size=8 color='#94a3b8'>"
                f"Generated by CyberLens v3.0 — Gurugram Police Cyber Security Cell (GPCSSI) | "
                f"Campaign: {kwargs['campaign_name']} ({kwargs['campaign_id']})</font>",
                body_style,
            ))

            doc.build(elements)
            logger.info("FIR PDF generated: %s", pdf_path)
            return pdf_path

        except ImportError:
            logger.warning("reportlab not installed — FIR PDF generation unavailable. "
                           "Install: pip install reportlab")
            return None
        except Exception as e:
            logger.error("PDF generation error: %s", e)
            return None
