"""
CyberLens — CRUD Operations
==============================
Full Create/Read/Update operations for cases, entities, and statistics.
"""

import datetime
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from src.database.models import Case, CrawlerLog, Entity, Officer

logger = logging.getLogger("cyberlens.database.crud")


# ---------------------------------------------------------------------------
# Filter & result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CaseFilter:
    """Filter parameters for case queries."""
    status: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    date_from: Optional[datetime.datetime] = None
    date_to: Optional[datetime.datetime] = None
    search: Optional[str] = None
    page: int = 1
    page_size: int = 20


@dataclass
class StatsResult:
    """Aggregated statistics."""
    total_cases: int = 0
    pending: int = 0
    reviewed: int = 0
    approved: int = 0
    submitted: int = 0
    rejected: int = 0
    by_category: Dict[str, int] = field(default_factory=dict)
    by_severity: Dict[str, int] = field(default_factory=dict)
    top_flagged_phones: List[Tuple[str, int]] = field(default_factory=list)
    top_flagged_urls: List[Tuple[str, int]] = field(default_factory=list)
    weekly_trend: List[Dict] = field(default_factory=list)
    deepfakes_detected: int = 0

    def to_dict(self) -> Dict:
        return {
            "total_cases": self.total_cases,
            "pending": self.pending,
            "reviewed": self.reviewed,
            "approved": self.approved,
            "submitted": self.submitted,
            "rejected": self.rejected,
            "by_category": self.by_category,
            "by_severity": self.by_severity,
            "top_flagged_phones": [
                {"value": v, "count": c} for v, c in self.top_flagged_phones
            ],
            "top_flagged_urls": [
                {"value": v, "count": c} for v, c in self.top_flagged_urls
            ],
            "weekly_trend": self.weekly_trend,
            "deepfakes_detected": self.deepfakes_detected,
        }


# ---------------------------------------------------------------------------
# Case CRUD
# ---------------------------------------------------------------------------

def create_case(session: Session, case_data: Dict) -> Case:
    """Create a new case record.

    Args:
        session: Database session.
        case_data: Dict of case field values.

    Returns:
        Created Case instance.
    """
    case = Case(**case_data)
    session.add(case)
    session.flush()
    logger.info("Created case: %s", case.case_number)
    return case


def get_case(session: Session, case_id: int) -> Optional[Case]:
    """Get a case by ID.

    Args:
        session: Database session.
        case_id: Case primary key ID.

    Returns:
        Case instance or None.
    """
    return session.query(Case).filter(Case.id == case_id).first()


def get_case_by_number(session: Session, case_number: str) -> Optional[Case]:
    """Get a case by case number.

    Args:
        session: Database session.
        case_number: Case number string (e.g., 'CL-2025-ABCDEF').

    Returns:
        Case instance or None.
    """
    return session.query(Case).filter(Case.case_number == case_number).first()


def get_cases(
    session: Session,
    filters: CaseFilter = None,
) -> Tuple[List[Case], int]:
    """Get paginated, filtered list of cases.

    Args:
        session: Database session.
        filters: Optional CaseFilter for filtering/pagination.

    Returns:
        Tuple of (list of cases, total count).
    """
    if filters is None:
        filters = CaseFilter()

    query = session.query(Case)

    # Apply filters
    if filters.status:
        query = query.filter(Case.status == filters.status)
    if filters.category:
        query = query.filter(Case.scam_category == filters.category)
    if filters.severity:
        query = query.filter(Case.severity == filters.severity)
    if filters.date_from:
        query = query.filter(Case.created_at >= filters.date_from)
    if filters.date_to:
        query = query.filter(Case.created_at <= filters.date_to)
    if filters.search:
        search_term = f"%{filters.search}%"
        query = query.filter(
            or_(
                Case.case_number.ilike(search_term),
                Case.ocr_text.ilike(search_term),
                Case.scam_category.ilike(search_term),
                Case.it_act_section.ilike(search_term),
                Case.notes.ilike(search_term),
            )
        )

    # Total count before pagination
    total = query.count()

    # Order and paginate
    query = query.order_by(desc(Case.created_at))
    offset = (filters.page - 1) * filters.page_size
    cases = query.offset(offset).limit(filters.page_size).all()

    return cases, total


def update_case_status(
    session: Session,
    case_id: int,
    status: str,
    officer_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> Optional[Case]:
    """Update case status and optionally assign officer.

    Args:
        session: Database session.
        case_id: Case primary key ID.
        status: New status string.
        officer_id: Optional officer ID to assign.
        notes: Optional notes to add.

    Returns:
        Updated Case or None if not found.
    """
    case = get_case(session, case_id)
    if not case:
        return None

    case.status = status
    if officer_id:
        case.officer_id = officer_id
    if notes:
        case.notes = (case.notes or "") + f"\n[{datetime.datetime.now()}] {notes}"

    if status == "REVIEWED":
        case.reviewed_at = datetime.datetime.now()
    elif status == "SUBMITTED":
        case.submitted_at = datetime.datetime.now()

    session.flush()
    logger.info("Case %s status updated to %s", case.case_number, status)
    return case


# ---------------------------------------------------------------------------
# Entity CRUD
# ---------------------------------------------------------------------------

def get_or_create_entity(
    session: Session,
    case_id: int,
    value: str,
    entity_type: str,
) -> Entity:
    """Get existing entity or create new one. Increments flag_count.

    Args:
        session: Database session.
        case_id: Case to link entity to.
        value: Entity value (phone, UPI, URL, etc.).
        entity_type: Type string (PHONE, UPI, URL, BANK, IFSC, AMOUNT).

    Returns:
        Entity instance (existing or new).
    """
    # Check if entity value already exists globally
    existing = session.query(Entity).filter(
        Entity.value == value,
        Entity.entity_type == entity_type,
    ).first()

    if existing:
        existing.flag_count += 1
        existing.last_seen = datetime.datetime.now()
        # Create a new entity record linking to this case
        new_entity = Entity(
            case_id=case_id,
            entity_type=entity_type,
            value=value,
            flag_count=existing.flag_count,
        )
        session.add(new_entity)
    else:
        new_entity = Entity(
            case_id=case_id,
            entity_type=entity_type,
            value=value,
            flag_count=1,
        )
        session.add(new_entity)

    session.flush()
    return new_entity


def increment_entity_flag(session: Session, entity_value: str) -> int:
    """Increment flag count for all instances of an entity value.

    Args:
        session: Database session.
        entity_value: The entity value to increment.

    Returns:
        New flag count.
    """
    entities = session.query(Entity).filter(Entity.value == entity_value).all()
    new_count = 0
    for entity in entities:
        entity.flag_count += 1
        new_count = entity.flag_count
    session.flush()
    return new_count


def get_entity_history(session: Session, value: str) -> List[Case]:
    """Get all cases where a specific entity value appears.

    Args:
        session: Database session.
        value: Entity value to search.

    Returns:
        List of Case instances containing this entity.
    """
    entity_ids = (
        session.query(Entity.case_id)
        .filter(Entity.value == value)
        .distinct()
        .all()
    )
    case_ids = [eid[0] for eid in entity_ids]
    if not case_ids:
        return []

    return session.query(Case).filter(Case.id.in_(case_ids)).all()


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def get_statistics(session: Session) -> StatsResult:
    """Get aggregated statistics across all cases.

    Args:
        session: Database session.

    Returns:
        StatsResult with counts, distributions, trends.
    """
    stats = StatsResult()

    # Total and status counts
    stats.total_cases = session.query(Case).count()
    stats.pending = session.query(Case).filter(Case.status == "PENDING").count()
    stats.reviewed = session.query(Case).filter(Case.status == "REVIEWED").count()
    stats.approved = session.query(Case).filter(Case.status == "APPROVED").count()
    stats.submitted = session.query(Case).filter(Case.status == "SUBMITTED").count()
    stats.rejected = session.query(Case).filter(Case.status == "REJECTED").count()
    stats.deepfakes_detected = session.query(Case).filter(
        Case.deepfake_suspected == True
    ).count()

    # Category distribution
    cat_results = (
        session.query(Case.scam_category, func.count(Case.id))
        .group_by(Case.scam_category)
        .all()
    )
    stats.by_category = {cat or "Unknown": count for cat, count in cat_results}

    # Severity distribution
    sev_results = (
        session.query(Case.severity, func.count(Case.id))
        .group_by(Case.severity)
        .all()
    )
    stats.by_severity = {sev or "Unknown": count for sev, count in sev_results}

    # Top flagged phones
    phone_results = (
        session.query(Entity.value, func.max(Entity.flag_count))
        .filter(Entity.entity_type == "PHONE")
        .group_by(Entity.value)
        .order_by(desc(func.max(Entity.flag_count)))
        .limit(10)
        .all()
    )
    stats.top_flagged_phones = [(v, c) for v, c in phone_results]

    # Top flagged URLs
    url_results = (
        session.query(Entity.value, func.max(Entity.flag_count))
        .filter(Entity.entity_type == "URL")
        .group_by(Entity.value)
        .order_by(desc(func.max(Entity.flag_count)))
        .limit(10)
        .all()
    )
    stats.top_flagged_urls = [(v, c) for v, c in url_results]

    # Weekly trend (last 7 days)
    today = datetime.datetime.now().date()
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        next_day = day + datetime.timedelta(days=1)
        count = (
            session.query(Case)
            .filter(
                Case.created_at >= datetime.datetime.combine(day, datetime.time.min),
                Case.created_at < datetime.datetime.combine(next_day, datetime.time.min),
            )
            .count()
        )
        stats.weekly_trend.append({
            "date": day.isoformat(),
            "day": day.strftime("%a"),
            "count": count,
        })

    return stats


def search_cases(session: Session, query: str) -> List[Case]:
    """Full-text search across case fields.

    Args:
        session: Database session.
        query: Search query string.

    Returns:
        List of matching Case instances.
    """
    term = f"%{query}%"
    return (
        session.query(Case)
        .filter(
            or_(
                Case.case_number.ilike(term),
                Case.ocr_text.ilike(term),
                Case.scam_category.ilike(term),
                Case.it_act_section.ilike(term),
                Case.notes.ilike(term),
            )
        )
        .order_by(desc(Case.created_at))
        .limit(50)
        .all()
    )


# ---------------------------------------------------------------------------
# Crawler log
# ---------------------------------------------------------------------------

def create_crawler_log(
    session: Session,
    source: str,
    query: str = "",
    items_found: int = 0,
    items_flagged: int = 0,
    status: str = "COMPLETED",
) -> CrawlerLog:
    """Create a crawler log entry.

    Args:
        session: Database session.
        source: Source name/URL.
        query: Search query used.
        items_found: Number of items found.
        items_flagged: Number flagged for review.
        status: Operation status.

    Returns:
        Created CrawlerLog instance.
    """
    log = CrawlerLog(
        source=source,
        query=query,
        items_found=items_found,
        items_flagged=items_flagged,
        status=status,
    )
    session.add(log)
    session.flush()
    return log
