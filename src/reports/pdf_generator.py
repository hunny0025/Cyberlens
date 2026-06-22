"""
CyberLens — PDF Report Generator
====================================
Professional case report generation using ReportLab.
Includes header, metadata, OCR text, classification, deepfake analysis,
legal sections, entities, and CONFIDENTIAL watermark.
"""

import io
import logging
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfgen import canvas

logger = logging.getLogger("cyberlens.reports")


class WatermarkCanvas(canvas.Canvas):
    """Custom canvas that adds CONFIDENTIAL watermark to every page."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        for page in self.pages:
            self.__dict__.update(page)
            self._draw_watermark()
            self._draw_footer()
            super().showPage()
        super().save()

    def _draw_watermark(self):
        """Draw CONFIDENTIAL diagonal watermark."""
        self.saveState()
        self.setFont("Helvetica-Bold", 60)
        self.setFillColor(colors.Color(0.9, 0.9, 0.9, alpha=0.3))
        self.translate(A4[0] / 2, A4[1] / 2)
        self.rotate(45)
        self.drawCentredString(0, 0, "CONFIDENTIAL")
        self.restoreState()

    def _draw_footer(self):
        """Draw page footer."""
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.grey)
        page_num = len(self.pages)
        self.drawString(
            2 * cm, 1 * cm,
            f"CyberLens Report | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Page {page_num}",
        )
        self.drawRightString(
            A4[0] - 2 * cm, 1 * cm,
            "Gurugram Police Cyber Cell — CONFIDENTIAL",
        )
        self.restoreState()


def generate_report(case) -> bytes:
    """Generate a professional PDF report for a case.

    Args:
        case: SQLAlchemy Case object.

    Returns:
        PDF file as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "CyberTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#1a237e"),
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "CyberSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.grey,
        alignment=TA_CENTER,
        spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "CyberSection",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#0d47a1"),
        spaceBefore=12,
        spaceAfter=6,
        borderWidth=1,
        borderColor=colors.HexColor("#0d47a1"),
        borderPadding=4,
    )
    body_style = ParagraphStyle(
        "CyberBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
    )
    highlight_style = ParagraphStyle(
        "CyberHighlight",
        parent=styles["Normal"],
        fontSize=10,
        backColor=colors.HexColor("#fff9c4"),
        borderWidth=1,
        borderColor=colors.HexColor("#f9a825"),
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=4,
    )

    elements = []

    # ── Header ────────────────────────────────────────────────────────────
    elements.append(Paragraph("CYBERLENS", title_style))
    elements.append(Paragraph(
        "GURUGRAM POLICE CYBER CELL | AI-POWERED CASE REPORT",
        subtitle_style,
    ))
    elements.append(Paragraph(
        f"Case Number: <b>{case.case_number}</b>",
        ParagraphStyle("CaseNum", parent=styles["Normal"],
                        fontSize=12, alignment=TA_CENTER,
                        textColor=colors.HexColor("#d32f2f")),
    ))
    elements.append(Spacer(1, 12))

    # ── Case Metadata Table ───────────────────────────────────────────────
    elements.append(Paragraph("Case Details", section_style))

    meta_data = [
        ["Case Number", str(case.case_number or "N/A")],
        ["Status", str(case.status or "PENDING")],
        ["Source Type", str(case.source_type or "UPLOAD")],
        ["Category", str(case.scam_category or "N/A")],
        ["Severity", str(case.severity or "MEDIUM")],
        ["Created At", str(case.created_at or "N/A")],
        ["Classification Confidence", f"{(case.scam_confidence or 0)*100:.1f}%"],
        ["Deepfake Probability", f"{(case.deepfake_probability or 0)*100:.1f}%"],
        ["Deepfake Suspected", "YES" if case.deepfake_suspected else "NO"],
        ["Intent", str(case.intent_label or "N/A")],
    ]

    meta_table = Table(meta_data, colWidths=[5 * cm, 12 * cm])
    meta_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e3f2fd")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 12))

    # ── OCR Extracted Text ────────────────────────────────────────────────
    if case.ocr_text:
        elements.append(Paragraph("OCR Extracted Text", section_style))
        # Truncate very long text
        display_text = case.ocr_text[:2000]
        if len(case.ocr_text) > 2000:
            display_text += "... [TRUNCATED]"
        # Escape HTML special chars
        display_text = (
            display_text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        elements.append(Paragraph(display_text, body_style))
        elements.append(Spacer(1, 8))

    # ── Classification Result ─────────────────────────────────────────────
    elements.append(Paragraph("Classification Result", section_style))
    clf_text = (
        f"<b>Category:</b> {case.scam_category or 'N/A'}<br/>"
        f"<b>Confidence:</b> {(case.scam_confidence or 0)*100:.1f}%<br/>"
        f"<b>Label:</b> {case.scam_label}"
    )
    elements.append(Paragraph(clf_text, body_style))
    elements.append(Spacer(1, 8))

    # Confidence bar (simple text representation)
    conf_pct = int((case.scam_confidence or 0) * 100)
    bar_filled = "█" * (conf_pct // 5)
    bar_empty = "░" * (20 - conf_pct // 5)
    elements.append(Paragraph(
        f"Confidence: [{bar_filled}{bar_empty}] {conf_pct}%",
        ParagraphStyle("ConfBar", parent=styles["Normal"],
                        fontName="Courier", fontSize=10),
    ))
    elements.append(Spacer(1, 8))

    # ── Deepfake Analysis ─────────────────────────────────────────────────
    elements.append(Paragraph("Deepfake Analysis", section_style))
    df_prob = (case.deepfake_probability or 0) * 100
    df_text = (
        f"<b>Probability:</b> {df_prob:.1f}%<br/>"
        f"<b>Suspected:</b> {'YES — INVESTIGATION RECOMMENDED' if case.deepfake_suspected else 'No significant indicators'}<br/>"
        f"<b>Faces Detected:</b> {case.face_count or 0}"
    )
    elements.append(Paragraph(df_text, body_style))
    elements.append(Spacer(1, 8))

    # ── Legal Sections ────────────────────────────────────────────────────
    if case.it_act_section:
        elements.append(Paragraph("Applicable Legal Sections", section_style))
        elements.append(Paragraph(
            str(case.it_act_section),
            highlight_style,
        ))
        elements.append(Spacer(1, 8))

    # ── Entities ──────────────────────────────────────────────────────────
    if case.entities:
        elements.append(Paragraph("Extracted Entities", section_style))

        entity_data = [["Type", "Value", "Flag Count"]]
        for entity in case.entities:
            entity_data.append([
                entity.entity_type,
                entity.value,
                str(entity.flag_count),
            ])

        entity_table = Table(entity_data, colWidths=[3 * cm, 10 * cm, 3 * cm])
        entity_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d47a1")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ]))
        elements.append(entity_table)

    # Build PDF
    doc.build(elements, canvasmaker=WatermarkCanvas)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    logger.info("PDF report generated for case %s (%d bytes)",
                case.case_number, len(pdf_bytes))
    return pdf_bytes
