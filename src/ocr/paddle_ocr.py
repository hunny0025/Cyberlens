"""
CyberLens — PaddleOCR Client (Local Fallback)
===============================================
Free, local OCR using PaddleOCR. No API key required.
Supports: English + Hindi (Devanagari).

Install: pip install paddleocr paddlepaddle

Author: CyberLens Team — GPCSSI Internship
"""

import logging
import time
from pathlib import Path
from typing import List

from src.ocr.mistral_ocr import OCRResult, OCRTextBlock

logger = logging.getLogger("cyberlens.ocr.paddle")


class PaddleOCREngine:
    """Local OCR engine using PaddleOCR.

    Falls back gracefully to pytesseract if paddleocr is not installed.
    """

    def __init__(self):
        self._paddle = None
        self._tesseract = None
        self._load()

    def _load(self) -> None:
        """Lazy-load PaddleOCR or pytesseract as fallback."""
        try:
            from paddleocr import PaddleOCR
            # use_angle_cls=True handles rotated text (common in scam screenshots)
            self._paddle = PaddleOCR(
                use_angle_cls=True,
                lang="en",        # English
                use_gpu=True,     # use CUDA if available
                show_log=False,
            )
            logger.info("PaddleOCR loaded (GPU=%s)", self._check_gpu())
        except ImportError:
            logger.info("paddleocr not installed — using pytesseract fallback")
            try:
                import pytesseract
                self._tesseract = pytesseract
                logger.info("pytesseract fallback ready")
            except ImportError:
                logger.warning("Neither paddleocr nor pytesseract available")

    def extract_text(self, image_path: str) -> OCRResult:
        """Extract text from image.

        Args:
            image_path: Path to image file.

        Returns:
            OCRResult with extracted text.
        """
        t0 = time.time()

        if self._paddle:
            return self._run_paddle(image_path, t0)
        elif self._tesseract:
            return self._run_tesseract(image_path, t0)
        else:
            return OCRResult(
                raw_text="", error="No OCR engine available (install paddleocr or pytesseract)",
                engine_used="none",
            )

    def _run_paddle(self, image_path: str, t0: float) -> OCRResult:
        """Run PaddleOCR extraction."""
        try:
            results = self._paddle.ocr(image_path, cls=True)
            if not results or not results[0]:
                return OCRResult(raw_text="", engine_used="paddle",
                                 processing_time_ms=int((time.time() - t0) * 1000))

            blocks = []
            lines = []
            total_conf = 0.0

            for line in results[0]:
                if not line or len(line) < 2:
                    continue
                bbox, (text, conf) = line[0], line[1]
                lines.append(text)
                total_conf += conf
                # Bounding box: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
                x = min(p[0] for p in bbox)
                y = min(p[1] for p in bbox)
                w = max(p[0] for p in bbox) - x
                h = max(p[1] for p in bbox) - y
                blocks.append(OCRTextBlock(text=text, confidence=conf, x=x, y=y, width=w, height=h))

            avg_conf = total_conf / max(len(blocks), 1)
            raw_text = "\n".join(lines)
            elapsed = int((time.time() - t0) * 1000)

            return OCRResult(
                raw_text=raw_text,
                text_blocks=blocks,
                confidence=avg_conf,
                language="en",
                engine_used="paddle",
                processing_time_ms=elapsed,
            )
        except Exception as e:
            logger.error("PaddleOCR failed: %s", e)
            return OCRResult(raw_text="", error=str(e), engine_used="paddle")

    def _run_tesseract(self, image_path: str, t0: float) -> OCRResult:
        """Run pytesseract fallback."""
        try:
            from PIL import Image
            img = Image.open(image_path)
            # Try Hindi + English
            text = self._tesseract.image_to_string(img, lang="eng+hin")
            elapsed = int((time.time() - t0) * 1000)
            return OCRResult(
                raw_text=text.strip(),
                confidence=0.70,
                language="en",
                engine_used="tesseract",
                processing_time_ms=elapsed,
            )
        except Exception as e:
            # Try English only
            try:
                from PIL import Image
                img = Image.open(image_path)
                text = self._tesseract.image_to_string(img, lang="eng")
                elapsed = int((time.time() - t0) * 1000)
                return OCRResult(
                    raw_text=text.strip(), confidence=0.65,
                    engine_used="tesseract", processing_time_ms=elapsed,
                )
            except Exception as e2:
                logger.error("Tesseract failed: %s", e2)
                return OCRResult(raw_text="", error=str(e2), engine_used="tesseract")

    @staticmethod
    def _check_gpu() -> bool:
        """Check if GPU is available."""
        try:
            import paddle
            return paddle.device.is_compiled_with_cuda()
        except Exception:
            return False
