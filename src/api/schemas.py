"""
CyberLens — Pydantic v2 API Schemas
=======================================
Request/response models for all API endpoints.
"""

import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Entity schemas
# ---------------------------------------------------------------------------

class EntityResponse(BaseModel):
    """Single entity in a case."""
    id: int = 0
    entity_type: str = ""
    value: str = ""
    flag_count: int = 1
    is_blocked: bool = False


# ---------------------------------------------------------------------------
# Classification schemas
# ---------------------------------------------------------------------------

class ClassificationResponse(BaseModel):
    """Scam classification result."""
    category: str = ""
    label: int = 0
    confidence: float = 0.0
    it_act_section: str = ""
    it_act_description: str = ""
    recommended_action: str = ""
    probabilities: Dict[str, float] = {}


# ---------------------------------------------------------------------------
# OCR schemas
# ---------------------------------------------------------------------------

class OCRResponse(BaseModel):
    """OCR extraction result."""
    raw_text: str = ""
    confidence: float = 0.0
    language: str = ""
    engine_used: str = ""
    entities: Dict[str, List[str]] = {}


# ---------------------------------------------------------------------------
# Deepfake schemas
# ---------------------------------------------------------------------------

class DeepfakeResponse(BaseModel):
    """Deepfake analysis result."""
    deepfake_probability: float = 0.0
    is_suspected: bool = False
    manipulation_indicators: List[str] = []
    face_count: int = 0
    analysis_confidence: float = 0.0


# ---------------------------------------------------------------------------
# Intent / Legal schemas
# ---------------------------------------------------------------------------

class IntentResponse(BaseModel):
    """Intent analysis result."""
    intent_category: str = ""
    confidence: float = 0.0
    reasoning: List[str] = []
    urgency_level: str = ""


class LegalResponse(BaseModel):
    """Legal mapping result."""
    primary_section: str = ""
    all_sections: List[str] = []
    description: str = ""
    fir_recommended: bool = False
    urgency: str = ""
    action_steps: List[str] = []


# ---------------------------------------------------------------------------
# Analysis result (combined)
# ---------------------------------------------------------------------------

class AnalysisResult(BaseModel):
    """Full analysis result from image or text analysis."""
    case_id: int = 0
    case_number: str = ""
    ocr: OCRResponse = OCRResponse()
    classification: ClassificationResponse = ClassificationResponse()
    deepfake: DeepfakeResponse = DeepfakeResponse()
    intent: IntentResponse = IntentResponse()
    legal: LegalResponse = LegalResponse()
    entities: List[EntityResponse] = []
    severity: str = "MEDIUM"
    processing_time_ms: float = 0.0


class TextAnalysisRequest(BaseModel):
    """Request body for text-only analysis."""
    text: str = Field(..., min_length=1, description="Text to analyze")


# ---------------------------------------------------------------------------
# Case schemas
# ---------------------------------------------------------------------------

class CaseResponse(BaseModel):
    """Single case detail."""
    id: int
    case_number: str
    source_type: str = "UPLOAD"
    source_url: Optional[str] = None
    ocr_text: Optional[str] = None
    ocr_confidence: float = 0.0
    scam_category: Optional[str] = None
    scam_label: Optional[int] = None
    scam_confidence: float = 0.0
    it_act_section: Optional[str] = None
    deepfake_probability: float = 0.0
    deepfake_suspected: bool = False
    face_count: int = 0
    intent_label: Optional[str] = None
    intent_confidence: float = 0.0
    severity: str = "MEDIUM"
    status: str = "PENDING"
    officer_id: Optional[int] = None
    created_at: Optional[datetime.datetime] = None
    reviewed_at: Optional[datetime.datetime] = None
    submitted_at: Optional[datetime.datetime] = None
    i4c_reference_number: Optional[str] = None
    notes: Optional[str] = None
    entities: List[EntityResponse] = []

    class Config:
        from_attributes = True


class CaseListResponse(BaseModel):
    """Paginated list of cases."""
    cases: List[CaseResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CaseStatusUpdate(BaseModel):
    """Request body for case status update."""
    status: str = Field(..., description="New status: PENDING, REVIEWED, APPROVED, SUBMITTED, REJECTED")
    officer_id: Optional[int] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Statistics schemas
# ---------------------------------------------------------------------------

class StatsResponse(BaseModel):
    """Dashboard statistics."""
    total_cases: int = 0
    pending: int = 0
    reviewed: int = 0
    approved: int = 0
    submitted: int = 0
    rejected: int = 0
    deepfakes_detected: int = 0
    by_category: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    top_flagged_phones: List[Dict[str, Any]] = []
    top_flagged_urls: List[Dict[str, Any]] = []
    weekly_trend: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# I4C schemas
# ---------------------------------------------------------------------------

class I4CSubmission(BaseModel):
    """Formatted I4C submission."""
    content_url: str = ""
    content_type: str = ""
    violation_category: str = ""
    it_act_section: str = ""
    description: str = ""
    evidence_summary: str = ""
    reporting_officer: str = ""
    station: str = ""
    timestamp: str = ""
    reference_number: str = ""
    case_number: str = ""

class SubmitI4CResponse(BaseModel):
    """Response from I4C submission."""
    success: bool = True
    reference_number: str = ""
    case_number: str = ""
    status: str = "SUBMITTED"
    submission: I4CSubmission = I4CSubmission()


# ---------------------------------------------------------------------------
# Crawler schemas
# ---------------------------------------------------------------------------

class CrawlerItemResponse(BaseModel):
    """Single crawler feed item."""
    source_url: str
    raw_text: str
    image_text: str
    category_hint: str
    timestamp: str
    record_id: str


class CrawlerFeedResponse(BaseModel):
    """Crawler feed response."""
    items: List[CrawlerItemResponse]
    total_ingested: int
    total_available: int


# ---------------------------------------------------------------------------
# Case filter (query params)
# ---------------------------------------------------------------------------

class CaseFilterParams(BaseModel):
    """Query parameters for case filtering."""
    status: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    search: Optional[str] = None
    page: int = 1
    page_size: int = 20
