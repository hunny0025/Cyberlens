"""
CyberLens — Upgraded OCR Manager (v2 — Full Pipeline)
=======================================================
10-step image intelligence pipeline:

  1. Detect image type (ScamImagePreprocessor)
  2. Run Mistral OCR (primary)
  3. Run PaddleOCR (fallback if Mistral fails)
  4. Extract QR codes (QRExtractor)
  5. Generate CLIP fingerprint (ImageFingerprinter)
  6. Check vector DB for similar images (template reuse)
  7. Parse all entities (EntityParser)
  8. Cross-reference threat intel (PhishTank / URLHaus)
  9. Store fingerprint in Qdrant
 10. Return FullOCRResult with everything

Author: CyberLens Team — GPCSSI Internship
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cyberlens.ocr.manager")


# ---------------------------------------------------------------------------
# Full result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ThreatIntelResult:
    """Cross-referenced threat intel for extracted entities."""
    flagged_urls: List[str] = field(default_factory=list)
    flagged_domains: List[str] = field(default_factory=list)
    flagged_ips: List[str] = field(default_factory=list)
    phishtank_matches: List[str] = field(default_factory=list)
    urlhaus_matches: List[str] = field(default_factory=list)
    total_flags: int = 0


@dataclass
class FullOCRResult:
    """Complete OCR analysis result from all pipeline stages."""
    # Stage 1 — image classification
    image_type: str = "UNKNOWN"

    # Stage 2/3 — text extraction
    raw_text: str = ""
    cleaned_text: str = ""
    translated_text: str = ""
    confidence: float = 0.0
    language: str = "en"
    engine_used: str = "none"
    processing_time_ms: int = 0
    regions_found: int = 0
    corrections_applied: int = 0

    # Stage 4 — QR codes
    qr_codes: List[Dict] = field(default_factory=list)

    # Stage 5/6 — fingerprinting & template match
    image_hash: str = ""
    phash: str = ""
    template_match: Optional[Dict] = None

    # Stage 7 — entities
    entities: Dict[str, Any] = field(default_factory=dict)

    # Stage 8 — threat intel
    threat_intel: Optional[Dict] = None

    # Errors
    errors: List[str] = field(default_factory=list)


class OCRManager:
    """Full 10-step image intelligence pipeline.

    Components are loaded lazily and degrade gracefully when
    optional dependencies (paddleocr, qdrant-client, etc.) are missing.
    """

    def __init__(self, enable_vision_fallback: bool = True):
        self.enable_vision_fallback = enable_vision_fallback
        self._preprocessor = None
        self._mistral = None
        self._paddle = None
        self._qr_extractor = None
        self._fingerprinter = None
        self._vector_store = None
        self._entity_parser = None
        self._hindi_cleaner = None
        self._translator = None
        self._init_components()

    def _init_components(self) -> None:
        """Initialize all pipeline components."""
        # Preprocessor
        try:
            from src.ocr.preprocessor import ScamImagePreprocessor
            self._preprocessor = ScamImagePreprocessor()
        except Exception as e:
            logger.warning("Preprocessor unavailable: %s", e)

        # OCR engines
        try:
            from src.ocr.mistral_ocr import MistralOCR
            self._mistral = MistralOCR()
        except Exception as e:
            logger.warning("MistralOCR unavailable: %s", e)

        try:
            from src.ocr.paddle_ocr import PaddleOCREngine
            self._paddle = PaddleOCREngine()
        except Exception as e:
            logger.warning("PaddleOCR unavailable: %s", e)

        # QR extractor
        try:
            from src.ocr.qr_extractor import QRExtractor
            self._qr_extractor = QRExtractor()
        except Exception as e:
            logger.warning("QRExtractor unavailable: %s", e)

        # Fingerprinter
        try:
            from src.ocr.image_fingerprinter import ImageFingerprinter
            self._fingerprinter = ImageFingerprinter()
        except Exception as e:
            logger.warning("ImageFingerprinter unavailable: %s", e)

        # Vector store
        try:
            from src.ocr.vector_store import VectorStore
            self._vector_store = VectorStore()
        except Exception as e:
            logger.warning("VectorStore unavailable: %s", e)

        # Entity parser
        try:
            from src.ocr.entity_parser import EntityParser
            self._entity_parser = EntityParser()
        except Exception as e:
            logger.warning("EntityParser unavailable: %s", e)

        # Hindi cleaner
        try:
            from src.ocr.hindi_text_cleaner import HindiTextCleaner
            self._hindi_cleaner = HindiTextCleaner()
        except Exception as e:
            logger.warning("HindiTextCleaner unavailable: %s", e)

        # Translator
        try:
            from src.ocr.translator import IndicTranslator
            self._translator = IndicTranslator()
        except Exception as e:
            logger.warning("Translator unavailable: %s", e)

        logger.info("OCRManager initialized (mistral=%s, paddle=%s, qr=%s, clip=%s)",
                    bool(self._mistral and self._mistral.available),
                    bool(self._paddle),
                    bool(self._qr_extractor),
                    bool(self._fingerprinter))

    @property
    def is_loaded(self) -> bool:
        return bool(self._paddle or self._mistral)

    # ── Main pipeline ─────────────────────────────────────────────────

    def process_image(self, image_path: str) -> FullOCRResult:
        """Run full 10-step image intelligence pipeline.

        Args:
            image_path: Absolute path to image file.

        Returns:
            FullOCRResult with all analysis results.
        """
        t0 = time.time()
        result = FullOCRResult()
        path = Path(image_path)

        if not path.exists():
            result.errors.append(f"File not found: {image_path}")
            return result

        # ── Stage 1: Detect image type ────────────────────────────────
        if self._preprocessor:
            try:
                from PIL import Image as PILImage
                img = PILImage.open(image_path)
                result.image_type = self._preprocessor.detect_image_type(img)
                logger.debug("Image type: %s", result.image_type)
            except Exception as e:
                result.errors.append(f"Image type detection failed: {e}")
                result.image_type = "SCREENSHOT"  # safe default

        # ── Stage 2: Mistral OCR (primary) ───────────────────────────
        ocr_result = None
        if self._mistral and self._mistral.available:
            try:
                ocr_result = self._mistral.extract_text(image_path)
                if ocr_result.success:
                    logger.debug("Mistral OCR: %d chars", len(ocr_result.raw_text))
            except Exception as e:
                result.errors.append(f"Mistral OCR error: {e}")
                ocr_result = None

        # ── Stage 3: PaddleOCR (fallback) ────────────────────────────
        if (not ocr_result or not ocr_result.success) and self._paddle:
            try:
                ocr_result = self._paddle.extract_text(image_path)
                logger.debug("PaddleOCR: %d chars", len(ocr_result.raw_text))
            except Exception as e:
                result.errors.append(f"PaddleOCR error: {e}")

        if ocr_result and ocr_result.success:
            result.raw_text = ocr_result.raw_text
            result.confidence = ocr_result.confidence
            result.language = ocr_result.language
            result.engine_used = ocr_result.engine_used
            result.processing_time_ms = ocr_result.processing_time_ms
            result.regions_found = len(getattr(ocr_result, "text_blocks", []))

            # Clean Hindi text
            if self._hindi_cleaner:
                cleaned, corrections = self._hindi_cleaner.clean(result.raw_text)
                result.cleaned_text = cleaned
                result.corrections_applied = corrections
            else:
                result.cleaned_text = result.raw_text

            # Translate if Hindi-heavy
            if self._translator and result.language in ("hi", "hi-en"):
                result.translated_text = self._translator.translate_if_hindi(result.cleaned_text)
            else:
                result.translated_text = result.cleaned_text

        # ── Stage 4: QR Code extraction ───────────────────────────────
        if self._qr_extractor:
            try:
                qr_results = self._qr_extractor.extract_qr(image_path)
                result.qr_codes = [
                    {
                        "raw_value": q.raw_value,
                        "qr_type": q.qr_type,
                        "decoded_data": q.decoded_data,
                        "risk_score": q.risk_score,
                    }
                    for q in qr_results
                ]
            except Exception as e:
                result.errors.append(f"QR extraction error: {e}")

        # ── Stage 5: Generate CLIP fingerprint ────────────────────────
        fingerprint = None
        if self._fingerprinter:
            try:
                fingerprint = self._fingerprinter.fingerprint(image_path)
                result.image_hash = fingerprint.image_hash
                result.phash = fingerprint.phash
            except Exception as e:
                result.errors.append(f"Fingerprint error: {e}")

        # ── Stage 6: Template matching ────────────────────────────────
        if fingerprint and fingerprint.clip_embedding is not None:
            try:
                template_match = self._fingerprinter.detect_template_reuse(image_path)
                if template_match.matched:
                    result.template_match = {
                        "matched": True,
                        "similarity": template_match.similarity,
                        "match_type": template_match.match_type,
                        "campaign_id": template_match.campaign_id,
                        "campaign_name": template_match.campaign_name,
                        "diff_highlights": template_match.diff_highlights,
                    }
            except Exception as e:
                result.errors.append(f"Template match error: {e}")

        # ── Stage 7: Entity parsing ───────────────────────────────────
        text_to_parse = result.translated_text or result.cleaned_text or result.raw_text
        if self._entity_parser and text_to_parse:
            try:
                entities = self._entity_parser.extract_all(text_to_parse)
                result.entities = entities

                # Merge QR-decoded entities
                for qr in result.qr_codes:
                    dd = qr.get("decoded_data", {})
                    if qr["qr_type"] == "UPI_PAYMENT" and dd.get("upi_id"):
                        result.entities.setdefault("upi_ids", [])
                        if dd["upi_id"] not in result.entities["upi_ids"]:
                            result.entities["upi_ids"].append(dd["upi_id"])
                    if qr["qr_type"] == "PHONE" and dd.get("phone"):
                        result.entities.setdefault("phones", [])
                        if dd["phone"] not in result.entities["phones"]:
                            result.entities["phones"].append(dd["phone"])
                    if qr["qr_type"] == "TELEGRAM" and dd.get("link"):
                        result.entities.setdefault("telegram_links", [])
                        if dd["link"] not in result.entities["telegram_links"]:
                            result.entities["telegram_links"].append(dd["link"])
            except Exception as e:
                result.errors.append(f"Entity parsing error: {e}")

        # ── Stage 8: Threat intel cross-reference ─────────────────────
        urls = result.entities.get("urls", [])
        if urls:
            result.threat_intel = self._cross_reference_threat_intel(urls)

        # ── Stage 9: Store fingerprint in Qdrant ──────────────────────
        if fingerprint and fingerprint.clip_embedding is not None and self._vector_store:
            try:
                self._vector_store.store_embedding(
                    image_hash=fingerprint.image_hash,
                    embedding=fingerprint.clip_embedding,
                    metadata={
                        "phash": fingerprint.phash,
                        "scam_type": result.entities.get("categories", [""])[0] if result.entities.get("categories") else "",
                        "first_seen": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "usage_count": 1,
                    },
                )
            except Exception as e:
                logger.debug("Qdrant store error: %s", e)

        # ── Stage 10: Finalize ────────────────────────────────────────
        elapsed = int((time.time() - t0) * 1000)
        if not result.processing_time_ms:
            result.processing_time_ms = elapsed

        logger.info(
            "OCR pipeline complete: type=%s engine=%s entities=%s qr=%d time=%dms",
            result.image_type, result.engine_used,
            list(result.entities.keys()),
            len(result.qr_codes), elapsed,
        )
        return result

    def _cross_reference_threat_intel(self, urls: List[str]) -> Dict[str, Any]:
        """Cross-reference URLs against PhishTank and URLHaus APIs.

        Gracefully fails if network unavailable.
        """
        flagged = []
        for url in urls[:5]:   # limit to 5 to avoid rate limits
            try:
                import requests
                # URLHaus lookup
                r = requests.post(
                    "https://urlhaus-api.abuse.ch/v1/url/",
                    data={"url": url},
                    timeout=5,
                )
                if r.ok:
                    data = r.json()
                    if data.get("query_status") == "is_listed":
                        flagged.append(url)
            except Exception:
                pass  # offline — skip

        return {
            "flagged_urls": flagged,
            "total_flags": len(flagged),
            "source": "URLHaus",
        }

    # ── Legacy compatibility ──────────────────────────────────────────

    def process(self, image_path: str) -> dict:
        """Legacy single-call wrapper that returns a simple dict.

        For backward compatibility with existing API routes.
        """
        result = self.process_image(image_path)
        return {
            "raw_text": result.raw_text,
            "cleaned_text": result.cleaned_text,
            "confidence": result.confidence,
            "language": result.language,
            "engine_used": result.engine_used,
            "image_type": result.image_type,
            "processing_time_ms": result.processing_time_ms,
            "regions_found": result.regions_found,
            "corrections_applied": result.corrections_applied,
            "entities": result.entities,
            "qr_codes": result.qr_codes,
            "image_hash": result.image_hash,
            "template_match": result.template_match,
        }
