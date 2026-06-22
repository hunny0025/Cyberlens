"""
CyberLens — Tesseract OCR Engine (Primary, Fully Local)
=========================================================
Wraps pytesseract for Hindi + English text extraction with
confidence scoring and post-processing for common OCR errors.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("cyberlens.ocr.tesseract")


@dataclass
class WordResult:
    """OCR result for a single word."""
    text: str
    confidence: float
    bbox: Tuple[int, int, int, int] = (0, 0, 0, 0)  # x, y, w, h


@dataclass
class OCRResult:
    """Complete OCR extraction result."""
    text: str
    confidence: float
    language_detected: str
    words: List[WordResult] = field(default_factory=list)
    bounding_boxes: List[Tuple[int, int, int, int]] = field(default_factory=list)
    engine: str = "tesseract"


class TesseractEngine:
    """Primary OCR engine using Tesseract (fully local, no API).

    Configured for Hindi + English multilingual extraction with
    sparse text mode (PSM 11) optimized for scam images.

    Attributes:
        lang: Tesseract language string.
        psm: Page segmentation mode.
        oem: OCR engine mode.
    """

    # Common OCR errors and corrections
    CORRECTIONS: Dict[str, str] = {
        "l<": "k",
        "|": "l",
        "0": "O",  # context-dependent
        "rn": "m",  # common misread
        "vv": "w",
        "Rs ": "Rs.",
        "Rs,": "Rs.",
        "INFt": "INR",
    }

    def __init__(
        self,
        lang: str = "hin+eng",
        psm: int = 11,
        oem: int = 3,
    ):
        """Initialize Tesseract engine.

        Args:
            lang: Language codes (e.g., 'hin+eng' for Hindi + English).
            psm: Page segmentation mode (11 = sparse text).
            oem: OCR engine mode (3 = default, LSTM).
        """
        self.lang = lang
        self.psm = psm
        self.oem = oem

        # Verify tesseract is available
        try:
            import pytesseract
            version = pytesseract.get_tesseract_version()
            logger.info("Tesseract %s initialized (lang=%s, psm=%d)",
                        version, lang, psm)
        except Exception as e:
            logger.error(
                "Tesseract not found! Install with: "
                "sudo apt install tesseract-ocr tesseract-ocr-hin. Error: %s", e
            )

    def extract_text(self, image: np.ndarray) -> OCRResult:
        """Extract text from a preprocessed image.

        Args:
            image: Preprocessed grayscale/binary image (numpy array).

        Returns:
            OCRResult with extracted text, confidence, and word details.
        """
        import pytesseract

        custom_config = f"--psm {self.psm} --oem {self.oem}"

        # Get detailed word-level data
        try:
            data = pytesseract.image_to_data(
                image,
                lang=self.lang,
                config=custom_config,
                output_type=pytesseract.Output.DICT,
            )
        except Exception as e:
            logger.error("Tesseract extraction failed: %s", e)
            return OCRResult(text="", confidence=0.0, language_detected="unknown")

        # Process word-level results
        words: List[WordResult] = []
        bboxes: List[Tuple[int, int, int, int]] = []
        confidences: List[float] = []

        n_items = len(data.get("text", []))
        for i in range(n_items):
            text = str(data["text"][i]).strip()
            conf = float(data["conf"][i])

            if text and conf > 0:
                bbox = (
                    data["left"][i],
                    data["top"][i],
                    data["width"][i],
                    data["height"][i],
                )
                words.append(WordResult(text=text, confidence=conf, bbox=bbox))
                bboxes.append(bbox)
                confidences.append(conf)

        # Build full text
        raw_text = " ".join(w.text for w in words)

        # Post-process
        cleaned_text = self._postprocess(raw_text)

        # Average confidence
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        avg_conf = avg_conf / 100.0  # Normalize to 0-1

        # Detect language
        language = self._detect_language(cleaned_text)

        result = OCRResult(
            text=cleaned_text,
            confidence=avg_conf,
            language_detected=language,
            words=words,
            bounding_boxes=bboxes,
        )
        logger.info(
            "Tesseract extracted %d words (confidence=%.2f, lang=%s)",
            len(words), avg_conf, language,
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

    def _postprocess(self, text: str) -> str:
        """Clean and fix common OCR errors.

        Args:
            text: Raw OCR output text.

        Returns:
            Cleaned text.
        """
        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Remove isolated single characters (noise)
        text = re.sub(r"\b[^a-zA-Z0-9₹@./:+-]\b", " ", text)

        # Fix common patterns
        for wrong, right in self.CORRECTIONS.items():
            text = text.replace(wrong, right)

        # Fix phone number formatting
        text = re.sub(r"(\+91)\s*[-.]?\s*(\d)", r"\1-\2", text)

        # Fix UPI ID formatting
        text = re.sub(r"(\w+)\s*@\s*(\w+)", r"\1@\2", text)

        # Fix URL formatting
        text = re.sub(r"https?\s*:\s*/\s*/", "https://", text)

        # Clean up remaining whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text

    @staticmethod
    def _detect_language(text: str) -> str:
        """Simple language detection based on character ranges.

        Args:
            text: Input text.

        Returns:
            'Hindi', 'English', or 'Hinglish'.
        """
        # Count Devanagari characters
        devanagari_count = len(re.findall(r"[\u0900-\u097F]", text))
        # Count Latin characters
        latin_count = len(re.findall(r"[a-zA-Z]", text))

        total = devanagari_count + latin_count
        if total == 0:
            return "Unknown"

        hindi_ratio = devanagari_count / total

        if hindi_ratio > 0.7:
            return "Hindi"
        elif hindi_ratio < 0.1:
            return "English"
        else:
            return "Hinglish"
