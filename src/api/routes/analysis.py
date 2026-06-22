"""
CyberLens — Analysis API Routes
==================================
POST /api/analyze/image — full image analysis pipeline
POST /api/analyze/text  — text-only analysis
"""

import logging
import shutil
import tempfile
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from src.api.schemas import (
    AnalysisResult,
    ClassificationResponse,
    DeepfakeResponse,
    EntityResponse,
    IntentResponse,
    LegalResponse,
    OCRResponse,
    TextAnalysisRequest,
)
from src.database import crud, db

logger = logging.getLogger("cyberlens.api.analysis")

router = APIRouter(prefix="/api/analyze", tags=["Analysis"])

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/image", response_model=AnalysisResult)
async def analyze_image(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(db.get_db),
):
    """Analyze an uploaded image through the full CyberLens pipeline.

    Pipeline: save → OCR → classify → deepfake → intent → legal → save case
    """
    start_time = time.time()

    # Validate file
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(400, "Only JPEG, PNG, and WebP images are accepted")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)")

    # Save uploaded file
    file_ext = Path(file.filename or "upload.jpg").suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = UPLOAD_DIR / filename
    with open(file_path, "wb") as f:
        f.write(content)

    logger.info("Uploaded file saved: %s (%d bytes)", filename, len(content))

    # Get ML models from app state
    ocr_manager = getattr(request.app.state, "ocr_manager", None)
    classifier = getattr(request.app.state, "classifier", None)
    deepfake_detector = getattr(request.app.state, "deepfake_detector", None)
    intent_analyzer = getattr(request.app.state, "intent_analyzer", None)
    legal_mapper = getattr(request.app.state, "legal_mapper", None)

    # Step 1: OCR
    ocr_result = None
    ocr_response = OCRResponse()
    if ocr_manager:
        try:
            ocr_result = ocr_manager.process_image(str(file_path))
            ocr_response = OCRResponse(
                raw_text=ocr_result.raw_text,
                confidence=ocr_result.confidence,
                language=ocr_result.language,
                engine_used=ocr_result.engine_used,
                entities={
                    "phones": ocr_result.entities.phones,
                    "upi_ids": ocr_result.entities.upi_ids,
                    "urls": ocr_result.entities.urls,
                    "bank_accounts": ocr_result.entities.bank_accounts,
                    "ifsc_codes": ocr_result.entities.ifsc_codes,
                    "amounts": ocr_result.entities.amounts,
                },
            )
        except Exception as e:
            logger.error("OCR failed: %s", e)

    # Step 2: Classify
    classification_response = ClassificationResponse()
    classify_result = None
    text_for_classification = ocr_response.raw_text or ""
    if classifier and text_for_classification:
        try:
            classify_result = classifier.predict(text_for_classification)
            classification_response = ClassificationResponse(
                category=classify_result.category,
                label=classify_result.label,
                confidence=classify_result.confidence,
                it_act_section=classify_result.it_act_section,
                it_act_description=classify_result.it_act_description,
                recommended_action=classify_result.recommended_action,
                probabilities=classify_result.probabilities,
            )
        except Exception as e:
            logger.error("Classification failed: %s", e)

    # Step 3: Deepfake
    deepfake_response = DeepfakeResponse()
    deepfake_result = None
    if deepfake_detector:
        try:
            deepfake_result = deepfake_detector.analyze(str(file_path))
            deepfake_response = DeepfakeResponse(
                deepfake_probability=deepfake_result.deepfake_probability,
                is_suspected=deepfake_result.is_suspected,
                manipulation_indicators=deepfake_result.manipulation_indicators,
                face_count=deepfake_result.face_count,
                analysis_confidence=deepfake_result.analysis_confidence,
            )
        except Exception as e:
            logger.error("Deepfake analysis failed: %s", e)

    # Step 4: Intent
    intent_response = IntentResponse()
    intent_result = None
    if intent_analyzer:
        try:
            intent_result = intent_analyzer.analyze_intent(
                deepfake_result=deepfake_result,
                ocr_text=ocr_response.raw_text,
                context_text=text_for_classification,
            )
            intent_response = IntentResponse(
                intent_category=intent_result.intent_category,
                confidence=intent_result.confidence,
                reasoning=intent_result.reasoning,
                urgency_level=intent_result.urgency_level,
            )
        except Exception as e:
            logger.error("Intent analysis failed: %s", e)

    # Step 5: Legal mapping
    legal_response = LegalResponse()
    if legal_mapper and intent_result:
        try:
            legal_result = legal_mapper.map_to_law(deepfake_result, intent_result)
            legal_response = LegalResponse(
                primary_section=legal_result.primary_section,
                all_sections=legal_result.all_sections,
                description=legal_result.description,
                fir_recommended=legal_result.fir_recommended,
                urgency=legal_result.urgency,
                action_steps=legal_result.action_steps,
            )
        except Exception as e:
            logger.error("Legal mapping failed: %s", e)

    # Determine severity
    severity = _determine_severity(
        classification_response.confidence,
        deepfake_response.deepfake_probability,
        intent_response.urgency_level,
    )

    # Save case to database
    case_data = {
        "source_type": "UPLOAD",
        "image_path": str(file_path),
        "ocr_text": ocr_response.raw_text,
        "ocr_confidence": ocr_response.confidence,
        "ocr_language": ocr_response.language,
        "scam_category": classification_response.category,
        "scam_label": classification_response.label,
        "scam_confidence": classification_response.confidence,
        "it_act_section": classification_response.it_act_section
                          or legal_response.primary_section,
        "deepfake_probability": deepfake_response.deepfake_probability,
        "deepfake_suspected": deepfake_response.is_suspected,
        "face_count": deepfake_response.face_count,
        "intent_label": intent_response.intent_category,
        "intent_confidence": intent_response.confidence,
        "severity": severity,
        "status": "PENDING",
    }
    case = crud.create_case(session, case_data)

    # Save entities
    entity_responses = []
    if ocr_result:
        for phone in ocr_result.entities.phones:
            e = crud.get_or_create_entity(session, case.id, phone, "PHONE")
            entity_responses.append(EntityResponse(
                id=e.id, entity_type="PHONE", value=phone, flag_count=e.flag_count,
            ))
        for upi in ocr_result.entities.upi_ids:
            e = crud.get_or_create_entity(session, case.id, upi, "UPI")
            entity_responses.append(EntityResponse(
                id=e.id, entity_type="UPI", value=upi, flag_count=e.flag_count,
            ))
        for url in ocr_result.entities.urls:
            e = crud.get_or_create_entity(session, case.id, url, "URL")
            entity_responses.append(EntityResponse(
                id=e.id, entity_type="URL", value=url, flag_count=e.flag_count,
            ))

    session.commit()

    elapsed = (time.time() - start_time) * 1000

    return AnalysisResult(
        case_id=case.id,
        case_number=case.case_number,
        ocr=ocr_response,
        classification=classification_response,
        deepfake=deepfake_response,
        intent=intent_response,
        legal=legal_response,
        entities=entity_responses,
        severity=severity,
        processing_time_ms=round(elapsed, 2),
    )


@router.post("/text", response_model=AnalysisResult)
async def analyze_text(
    request: Request,
    body: TextAnalysisRequest,
    session: Session = Depends(db.get_db),
):
    """Analyze raw text input for scam classification.

    For when officers have text content without an image.
    """
    start_time = time.time()
    text = body.text

    classifier = getattr(request.app.state, "classifier", None)
    intent_analyzer = getattr(request.app.state, "intent_analyzer", None)
    legal_mapper = getattr(request.app.state, "legal_mapper", None)
    ocr_manager = getattr(request.app.state, "ocr_manager", None)

    # Classify
    classification_response = ClassificationResponse()
    classify_result = None
    if classifier:
        try:
            classify_result = classifier.predict(text)
            classification_response = ClassificationResponse(
                category=classify_result.category,
                label=classify_result.label,
                confidence=classify_result.confidence,
                it_act_section=classify_result.it_act_section,
                it_act_description=classify_result.it_act_description,
                recommended_action=classify_result.recommended_action,
                probabilities=classify_result.probabilities,
            )
        except Exception as e:
            logger.error("Classification failed: %s", e)

    # Extract entities from text
    ocr_response = OCRResponse(raw_text=text, confidence=1.0, language="Hinglish")
    entity_responses = []
    if ocr_manager:
        try:
            entities = ocr_manager.process_text_only(text)
            ocr_response.entities = {
                "phones": entities.phones,
                "upi_ids": entities.upi_ids,
                "urls": entities.urls,
                "bank_accounts": entities.bank_accounts,
                "ifsc_codes": entities.ifsc_codes,
                "amounts": entities.amounts,
            }
        except Exception as e:
            logger.error("Entity extraction failed: %s", e)

    # Intent
    intent_response = IntentResponse()
    intent_result = None
    if intent_analyzer:
        try:
            intent_result = intent_analyzer.analyze_intent(
                deepfake_result=None,
                ocr_text=text,
                context_text=text,
            )
            intent_response = IntentResponse(
                intent_category=intent_result.intent_category,
                confidence=intent_result.confidence,
                reasoning=intent_result.reasoning,
                urgency_level=intent_result.urgency_level,
            )
        except Exception as e:
            logger.error("Intent analysis failed: %s", e)

    # Legal
    legal_response = LegalResponse()
    if legal_mapper and intent_result:
        try:
            legal_result = legal_mapper.map_to_law(None, intent_result)
            legal_response = LegalResponse(
                primary_section=legal_result.primary_section,
                all_sections=legal_result.all_sections,
                description=legal_result.description,
                fir_recommended=legal_result.fir_recommended,
                urgency=legal_result.urgency,
                action_steps=legal_result.action_steps,
            )
        except Exception as e:
            logger.error("Legal mapping failed: %s", e)

    severity = _determine_severity(
        classification_response.confidence, 0.0, intent_response.urgency_level,
    )

    # Save case
    case_data = {
        "source_type": "UPLOAD",
        "ocr_text": text,
        "scam_category": classification_response.category,
        "scam_label": classification_response.label,
        "scam_confidence": classification_response.confidence,
        "it_act_section": classification_response.it_act_section
                          or legal_response.primary_section,
        "intent_label": intent_response.intent_category,
        "intent_confidence": intent_response.confidence,
        "severity": severity,
        "status": "PENDING",
    }
    case = crud.create_case(session, case_data)
    session.commit()

    elapsed = (time.time() - start_time) * 1000

    return AnalysisResult(
        case_id=case.id,
        case_number=case.case_number,
        ocr=ocr_response,
        classification=classification_response,
        deepfake=DeepfakeResponse(),
        intent=intent_response,
        legal=legal_response,
        entities=entity_responses,
        severity=severity,
        processing_time_ms=round(elapsed, 2),
    )


def _determine_severity(
    scam_confidence: float,
    deepfake_prob: float,
    urgency: str,
) -> str:
    """Determine case severity from analysis results."""
    if urgency == "CRITICAL" or deepfake_prob > 0.8:
        return "CRITICAL"
    if urgency == "HIGH" or scam_confidence > 0.85 or deepfake_prob > 0.65:
        return "HIGH"
    if scam_confidence > 0.5 or deepfake_prob > 0.3:
        return "MEDIUM"
    return "LOW"
