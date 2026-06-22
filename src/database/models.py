"""
CyberLens — SQLAlchemy ORM Models
====================================
Database models for case management, entity tracking,
officer records, and crawler logs.
"""

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def _generate_case_number() -> str:
    """Generate a unique case number: CL-2025-XXXX."""
    short_id = uuid.uuid4().hex[:6].upper()
    year = datetime.datetime.now().year
    return f"CL-{year}-{short_id}"


class Case(Base):
    """Cybercrime case record."""

    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_number = Column(String(20), unique=True, nullable=False, default=_generate_case_number)
    source_type = Column(String(20), default="UPLOAD")  # UPLOAD, CRAWLER
    source_url = Column(Text, nullable=True)
    image_path = Column(Text, nullable=True)

    # OCR
    ocr_text = Column(Text, nullable=True)
    ocr_confidence = Column(Float, default=0.0)
    ocr_language = Column(String(20), nullable=True)

    # Classification
    scam_category = Column(String(50), nullable=True)
    scam_label = Column(Integer, nullable=True)
    scam_confidence = Column(Float, default=0.0)
    it_act_section = Column(Text, nullable=True)

    # Deepfake
    deepfake_probability = Column(Float, default=0.0)
    deepfake_suspected = Column(Boolean, default=False)
    face_count = Column(Integer, default=0)

    # Intent
    intent_label = Column(String(50), nullable=True)
    intent_confidence = Column(Float, default=0.0)

    # Severity & status
    severity = Column(String(20), default="MEDIUM")  # CRITICAL, HIGH, MEDIUM, LOW
    status = Column(String(20), default="PENDING")  # PENDING, REVIEWED, APPROVED, SUBMITTED, REJECTED

    # Officer
    officer_id = Column(Integer, ForeignKey("officers.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now())
    reviewed_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)

    # I4C
    i4c_reference_number = Column(String(50), nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Relationships
    entities = relationship("Entity", back_populates="case", cascade="all, delete-orphan")
    officer = relationship("Officer", back_populates="cases")

    def __repr__(self) -> str:
        return f"<Case {self.case_number} [{self.status}] {self.scam_category}>"


class Entity(Base):
    """Extracted entity (phone, UPI, URL, etc.) linked to a case."""

    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    entity_type = Column(String(20), nullable=False)  # PHONE, UPI, URL, BANK, IFSC, AMOUNT
    value = Column(String(500), nullable=False)
    flag_count = Column(Integer, default=1)
    first_seen = Column(DateTime, default=func.now())
    last_seen = Column(DateTime, default=func.now(), onupdate=func.now())
    is_blocked = Column(Boolean, default=False)

    # Relationships
    case = relationship("Case", back_populates="entities")

    def __repr__(self) -> str:
        return f"<Entity {self.entity_type}:{self.value} (flags={self.flag_count})>"


class Officer(Base):
    """Police officer record."""

    __tablename__ = "officers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    badge_number = Column(String(20), unique=True, nullable=False)
    station = Column(String(100), default="Gurugram Cyber Cell")
    rank = Column(String(50), default="Sub-Inspector")
    created_at = Column(DateTime, default=func.now())

    # Relationships
    cases = relationship("Case", back_populates="officer")

    def __repr__(self) -> str:
        return f"<Officer {self.name} ({self.badge_number})>"


class CrawlerLog(Base):
    """Log entry for crawler operations."""

    __tablename__ = "crawler_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(100), nullable=False)
    query = Column(String(200), nullable=True)
    items_found = Column(Integer, default=0)
    items_flagged = Column(Integer, default=0)
    timestamp = Column(DateTime, default=func.now())
    status = Column(String(20), default="COMPLETED")  # COMPLETED, FAILED, PARTIAL

    def __repr__(self) -> str:
        return f"<CrawlerLog {self.source} found={self.items_found} flagged={self.items_flagged}>"
