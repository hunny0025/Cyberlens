"""
CyberLens — Mistral OCR Client
=================================
Best-in-class OCR using Mistral's vision API.
Handles: complex layouts, scam posters, Hindi/Hinglish, tables.

Falls back gracefully when MISTRAL_API_KEY is not set.

Author: CyberLens Team — GPCSSI Internship
"""

import base64
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger("cyberlens.ocr.mistral")

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_OCR_MODEL = "mistral-ocr-latest"


@dataclass
class OCRTextBlock:
    """A detected text block with position info."""
    text: str
    confidence: float = 1.0
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    language: str = "en"


@dataclass
class OCRResult:
    """Unified OCR result from any engine."""
    raw_text: str
    text_blocks: List[OCRTextBlock] = field(default_factory=list)
    confidence: float = 0.0
    language: str = "en"
    engine_used: str = "unknown"
    processing_time_ms: int = 0
    error: str = ""

    @property
    def success(self) -> bool:
        return bool(self.raw_text) and not self.error


class MistralOCR:
    """OCR engine using Mistral's vision API (mistral-ocr-latest).

    Best for: complex scam poster layouts, multi-column text,
    Hindi+English mixed content, tables, structured forms.

    Requires: MISTRAL_API_KEY in .env
    """

    def __init__(self):
        self.api_key = os.getenv("MISTRAL_API_KEY", "")
        self.available = bool(self.api_key)
        if not self.available:
            logger.info("MistralOCR: MISTRAL_API_KEY not set — engine disabled")

    def extract_text(self, image_path: str) -> OCRResult:
        """Extract text from image using Mistral vision API.

        Args:
            image_path: Path to the image file.

        Returns:
            OCRResult with extracted text.
        """
        import time
        if not self.available:
            return OCRResult(raw_text="", error="MISTRAL_API_KEY not configured",
                             engine_used="mistral")

        t0 = time.time()
        try:
            image_b64 = self._encode_image(image_path)
            if not image_b64:
                return OCRResult(raw_text="", error="Failed to encode image",
                                 engine_used="mistral")

            prompt = (
                "You are an expert OCR system for the Indian police. "
                "Extract ALL visible text from this image, including:\n"
                "- Phone numbers (including disguised: +91, 0XX, spaced digits)\n"
                "- UPI IDs (xxx@bank format)\n"
                "- URLs and Telegram links\n"
                "- Hindi and English text\n"
                "- Prices and amounts (₹, Rs)\n"
                "- Investment claims and guarantees\n"
                "Return ONLY the extracted text, nothing else."
            )

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": MISTRAL_OCR_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                    ],
                }],
                "max_tokens": 2048,
            }

            response = requests.post(
                MISTRAL_API_URL, json=payload, headers=headers, timeout=30
            )
            response.raise_for_status()
            data = response.json()

            text = data["choices"][0]["message"]["content"].strip()
            elapsed = int((time.time() - t0) * 1000)

            return OCRResult(
                raw_text=text,
                confidence=0.92,
                language=self._detect_language(text),
                engine_used="mistral",
                processing_time_ms=elapsed,
            )

        except requests.HTTPError as e:
            logger.error("Mistral API HTTP error: %s", e)
            return OCRResult(raw_text="", error=str(e), engine_used="mistral")
        except Exception as e:
            logger.error("MistralOCR failed: %s", e)
            return OCRResult(raw_text="", error=str(e), engine_used="mistral")

    @staticmethod
    def _encode_image(image_path: str) -> str:
        """Encode image to base64."""
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.error("Image encoding failed: %s", e)
            return ""

    @staticmethod
    def _detect_language(text: str) -> str:
        """Detect primary language from text."""
        devanagari = sum(1 for c in text if "\u0900" <= c <= "\u097F")
        if devanagari > len(text) * 0.3:
            return "hi"
        if devanagari > 0:
            return "hi-en"
        return "en"
