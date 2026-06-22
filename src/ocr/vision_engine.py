"""
CyberLens — Google Cloud Vision OCR Engine (Fallback)
=======================================================
Optional fallback OCR engine using Google Cloud Vision API.
Only used when Tesseract confidence is below threshold.
Requires GOOGLE_VISION_API_KEY environment variable.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from src.ocr.tesseract_engine import OCRResult, WordResult

logger = logging.getLogger("cyberlens.ocr.vision")


class ConfigError(Exception):
    """Raised when required configuration is missing."""
    pass


class GoogleVisionEngine:
    """Google Cloud Vision OCR engine (fallback for low-confidence results).

    Requires the GOOGLE_VISION_API_KEY environment variable to be set.
    Provides higher accuracy for complex images but requires internet.

    Attributes:
        client: Google Vision API client (lazy-loaded).
        api_key: API key from environment.
    """

    def __init__(self):
        """Initialize Google Vision engine.

        Does NOT fail on init — only fails when actually used without config.
        """
        self._client = None
        self._available = False
        self.api_key = os.getenv("GOOGLE_VISION_API_KEY", "")

        if self.api_key and self.api_key != "your_key_here":
            try:
                from google.cloud import vision
                self._client = vision.ImageAnnotatorClient()
                self._available = True
                logger.info("Google Vision engine initialized")
            except ImportError:
                logger.warning(
                    "google-cloud-vision not installed. "
                    "Install with: pip install google-cloud-vision"
                )
            except Exception as e:
                logger.warning("Google Vision init failed: %s", e)
        else:
            logger.info(
                "Google Vision API key not configured. "
                "Set GOOGLE_VISION_API_KEY in .env for fallback OCR."
            )

    @property
    def is_available(self) -> bool:
        """Whether the engine is configured and ready."""
        return self._available

    def extract_text(self, image: np.ndarray) -> OCRResult:
        """Extract text from image using Google Cloud Vision.

        Args:
            image: Input image as numpy array.

        Returns:
            OCRResult with extracted text and confidence.

        Raises:
            ConfigError: If API key is not configured.
        """
        if not self._available:
            raise ConfigError(
                "Google Cloud Vision API is not configured. "
                "To enable: 1) Set GOOGLE_VISION_API_KEY in your .env file, "
                "2) Install google-cloud-vision: pip install google-cloud-vision, "
                "3) Ensure the API key has Vision API enabled in Google Cloud Console."
            )

        from google.cloud import vision
        import cv2

        # Encode image to bytes
        success, buffer = cv2.imencode(".png", image)
        if not success:
            logger.error("Failed to encode image for Vision API")
            return OCRResult(text="", confidence=0.0, language_detected="unknown",
                             engine="google_vision")

        content = buffer.tobytes()
        vision_image = vision.Image(content=content)

        # Call API
        try:
            response = self._client.text_detection(image=vision_image)
            if response.error.message:
                logger.error("Vision API error: %s", response.error.message)
                return OCRResult(text="", confidence=0.0, language_detected="unknown",
                                 engine="google_vision")
        except Exception as e:
            logger.error("Vision API call failed: %s", e)
            return OCRResult(text="", confidence=0.0, language_detected="unknown",
                             engine="google_vision")

        # Process response
        annotations = response.text_annotations
        if not annotations:
            return OCRResult(text="", confidence=0.0, language_detected="unknown",
                             engine="google_vision")

        # First annotation is the full text
        full_text = annotations[0].description.strip()

        # Detect language from response
        language = "Unknown"
        if annotations[0].locale:
            locale = annotations[0].locale
            lang_map = {"hi": "Hindi", "en": "English", "hi-Latn": "Hinglish"}
            language = lang_map.get(locale, locale)

        # Extract word-level results
        words = []
        bboxes = []
        for ann in annotations[1:]:  # Skip first (full text)
            vertices = ann.bounding_poly.vertices
            bbox = (
                vertices[0].x, vertices[0].y,
                vertices[2].x - vertices[0].x,
                vertices[2].y - vertices[0].y,
            )
            words.append(WordResult(
                text=ann.description,
                confidence=0.95,  # Vision API doesn't provide word-level confidence
                bbox=bbox,
            ))
            bboxes.append(bbox)

        # Vision API generally has high confidence
        confidence = 0.95

        result = OCRResult(
            text=full_text,
            confidence=confidence,
            language_detected=language,
            words=words,
            bounding_boxes=bboxes,
            engine="google_vision",
        )
        logger.info(
            "Google Vision extracted %d words (lang=%s)",
            len(words), language,
        )
        return result

    def extract_text_from_file(self, image_path: str) -> OCRResult:
        """Extract text directly from an image file.

        Args:
            image_path: Path to image file.

        Returns:
            OCRResult with extracted text.
        """
        import cv2
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")
        return self.extract_text(img)
