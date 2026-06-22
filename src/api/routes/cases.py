"""
CyberLens — Case Management API Routes
==========================================
GET/PATCH endpoints for case listing, detail, status, PDF, CSV export.
"""

import csv
import io
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.schemas import (
    CaseListResponse,
    CaseResponse,
    CaseStatusUpdate,
    EntityResponse,
)
from src.database import crud, db
from src.database.crud import CaseFilter

logger = logging.getLogger("cyberlens.api.cases")

router = APIRouter(prefix="/api/cases", tags=["Cases"])


def _case_to_response(case) -> CaseResponse:
    """Convert ORM Case to Pydantic CaseResponse."""
    entities = [
        EntityResponse(
            id=e.id,
            entity_type=e.entity_type,
            value=e.value,
            flag_count=e.flag_count,
            is_blocked=e.is_blocked,
        )
        for e in (case.entities or [])
    ]
    return CaseResponse(
        id=case.id,
        case_number=case.case_number,
        source_type=case.source_type or "UPLOAD",
        source_url=case.source_url,
        ocr_text=case.ocr_text,
        ocr_confidence=case.ocr_confidence or 0.0,
        scam_category=case.scam_category,
        scam_label=case.scam_label,
        scam_confidence=case.scam_confidence or 0.0,
        it_act_section=case.it_act_section,
        deepfake_probability=case.deepfake_probability or 0.0,
        deepfake_suspected=case.deepfake_suspected or False,
        face_count=case.face_count or 0,
        intent_label=case.intent_label,
        intent_confidence=case.intent_confidence or 0.0,
        severity=case.severity or "MEDIUM",
        status=case.status or "PENDING",
        officer_id=case.officer_id,
        created_at=case.created_at,
        reviewed_at=case.reviewed_at,
        submitted_at=case.submitted_at,
        i4c_reference_number=case.i4c_reference_number,
        notes=case.notes,
        entities=entities,
    )


@router.get("", response_model=CaseListResponse)
async def list_cases(
    status: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(db.get_db),
):
    """Get paginated, filterable list of cases."""
    filters = CaseFilter(
        status=status,
        category=category,
        severity=severity,
        search=search,
        page=page,
        page_size=page_size,
    )

    if date_from:
        try:
            filters.date_from = datetime.fromisoformat(date_from)
        except ValueError:
            pass
    if date_to:
        try:
            filters.date_to = datetime.fromisoformat(date_to)
        except ValueError:
            pass

    cases, total = crud.get_cases(session, filters)
    total_pages = (total + page_size - 1) // page_size

    return CaseListResponse(
        cases=[_case_to_response(c) for c in cases],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: int,
    session: Session = Depends(db.get_db),
):
    """Get full detail of a single case."""
    case = crud.get_case(session, case_id)
    if not case:
        raise HTTPException(404, f"Case {case_id} not found")
    return _case_to_response(case)


@router.patch("/{case_id}/status", response_model=CaseResponse)
async def update_case_status(
    case_id: int,
    body: CaseStatusUpdate,
    session: Session = Depends(db.get_db),
):
    """Update case status and optionally assign officer."""
    valid_statuses = {"PENDING", "REVIEWED", "APPROVED", "SUBMITTED", "REJECTED"}
    if body.status not in valid_statuses:
        raise HTTPException(400, f"Invalid status. Must be one of: {valid_statuses}")

    case = crud.update_case_status(
        session, case_id, body.status, body.officer_id, body.notes,
    )
    if not case:
        raise HTTPException(404, f"Case {case_id} not found")

    session.commit()
    return _case_to_response(case)


@router.post("/{case_id}/approve", response_model=CaseResponse)
async def approve_case(
    case_id: int,
    session: Session = Depends(db.get_db),
):
    """Approve a case for I4C submission."""
    case = crud.update_case_status(session, case_id, "APPROVED")
    if not case:
        raise HTTPException(404, f"Case {case_id} not found")
    session.commit()
    return _case_to_response(case)


@router.get("/{case_id}/report")
async def download_report(
    case_id: int,
    request: Request,
    session: Session = Depends(db.get_db),
):
    """Generate and download PDF report for a case."""
    case = crud.get_case(session, case_id)
    if not case:
        raise HTTPException(404, f"Case {case_id} not found")

    try:
        from src.reports.pdf_generator import generate_report
        pdf_bytes = generate_report(case)

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=CyberLens_{case.case_number}.pdf"
            },
        )
    except Exception as e:
        logger.error("PDF generation failed: %s", e)
        raise HTTPException(500, f"PDF generation failed: {str(e)}")


@router.get("/export/csv")
async def export_csv(
    status: Optional[str] = None,
    category: Optional[str] = None,
    session: Session = Depends(db.get_db),
):
    """Export filtered cases as CSV."""
    filters = CaseFilter(status=status, category=category, page_size=10000)
    cases, _ = crud.get_cases(session, filters)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Case Number", "Category", "Severity", "Status",
        "Scam Confidence", "Deepfake Probability",
        "IT Act Section", "Created At",
    ])

    for case in cases:
        writer.writerow([
            case.case_number,
            case.scam_category or "",
            case.severity or "",
            case.status or "",
            f"{(case.scam_confidence or 0):.2f}",
            f"{(case.deepfake_probability or 0):.2f}",
            case.it_act_section or "",
            str(case.created_at or ""),
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cyberlens_cases.csv"},
    )
