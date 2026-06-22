"""
CyberLens — Scam Image Preprocessor (Upgraded)
==================================================
Multi-strategy preprocessor that detects image type and applies
optimized pipelines for each scam image category:
  SCREENSHOT, WHATSAPP_FORWARD, DESIGNED_GRAPHIC, PHOTO, HANDWRITTEN

Author: CyberLens Team — GPCSSI Internship
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("cyberlens.ocr.preprocessor")


# ---------------------------------------------------------------------------
# Image type classification
# ---------------------------------------------------------------------------

class ScamImagePreprocessor:
    """Detects scam image type and routes to specialized preprocessor.

    Image types:
        SCREENSHOT: WhatsApp/Telegram app screenshots with UI chrome
        WHATSAPP_FORWARD: Heavily compressed, forwarded many times
        DESIGNED_GRAPHIC: Canva-style scam ads with colored backgrounds
        PHOTO: Camera photo of a screen or paper
        HANDWRITTEN: Handwritten phone numbers or notes
    """

    def detect_image_type(self, image: np.ndarray) -> str:
        """Classify the scam image type using visual heuristics.

        Uses aspect ratio, color profile, compression artifacts,
        and structural features to determine the type.

        Args:
            image: BGR image as numpy array.

        Returns:
            One of: SCREENSHOT, WHATSAPP_FORWARD, DESIGNED_GRAPHIC,
                    PHOTO, HANDWRITTEN
        """
        h, w = image.shape[:2]
        aspect = h / max(w, 1)

        # Color profile analysis
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        saturation_mean = np.mean(hsv[:, :, 1])
        value_mean = np.mean(hsv[:, :, 2])
        gray_std = np.std(gray)

        # Compression artifact detection (DCT blocking)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        # Edge density
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size

        # UI chrome detection (status bar, nav bar patterns)
        top_strip = gray[:int(h * 0.05), :]
        bottom_strip = gray[int(h * 0.95):, :]
        top_uniformity = np.std(top_strip) if top_strip.size > 0 else 50
        bottom_uniformity = np.std(bottom_strip) if bottom_strip.size > 0 else 50

        # Handwritten detection: high contrast strokes on white
        white_ratio = np.sum(gray > 220) / gray.size
        dark_ratio = np.sum(gray < 50) / gray.size

        # ── Classification logic ──────────────────────────────────────

        # Screenshot: tall aspect, UI chrome (uniform top/bottom bars)
        if aspect > 1.5 and top_uniformity < 25 and bottom_uniformity < 30:
            return "SCREENSHOT"

        # WhatsApp forward: heavy JPEG artifacts (low laplacian), tall
        if laplacian_var < 80 and aspect > 1.2:
            return "WHATSAPP_FORWARD"

        # Designed graphic: high saturation, moderate aspect
        if saturation_mean > 80 and value_mean > 100:
            return "DESIGNED_GRAPHIC"

        # Handwritten: mostly white with dark strokes
        if white_ratio > 0.6 and dark_ratio > 0.02 and gray_std < 80:
            return "HANDWRITTEN"

        # Default: photo
        return "PHOTO"

    def preprocess_for_type(self, image: np.ndarray, image_type: str) -> np.ndarray:
        """Route to the correct preprocessor based on type.

        Args:
            image: BGR image.
            image_type: Detected image type string.

        Returns:
            Preprocessed grayscale image ready for OCR.
        """
        router = {
            "SCREENSHOT": self.preprocess_screenshot,
            "WHATSAPP_FORWARD": self.preprocess_whatsapp_forward,
            "DESIGNED_GRAPHIC": self.preprocess_designed_graphic,
            "PHOTO": self.preprocess_photo,
            "HANDWRITTEN": self.preprocess_handwritten_number,
        }
        fn = router.get(image_type, self.preprocess_photo)
        logger.info("Preprocessing as %s", image_type)
        return fn(image)

    # ── Type-specific preprocessors ───────────────────────────────────

    def preprocess_screenshot(self, image: np.ndarray) -> np.ndarray:
        """Optimized for WhatsApp/Telegram app screenshots.

        High-contrast text extraction, crop UI chrome, enhance chat text.
        """
        h, w = image.shape[:2]

        # Crop out status bar (top 5%) and nav bar (bottom 5%)
        crop_top = int(h * 0.05)
        crop_bottom = int(h * 0.95)
        cropped = image[crop_top:crop_bottom, :]

        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)

        # Light denoise (screenshots are usually clean)
        gray = cv2.fastNlMeansDenoising(gray, None, 5, 7, 21)

        # High-contrast CLAHE
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # Otsu threshold (works well for clean screenshots)
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        return binary

    def preprocess_designed_graphic(self, image: np.ndarray) -> np.ndarray:
        """For Canva-style scam ads with colorful backgrounds.

        Handles white text on dark background, colored overlays,
        gradient backgrounds with text.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)

        # Invert if dark background (white text on dark)
        if mean_brightness < 128:
            gray = cv2.bitwise_not(gray)
            logger.debug("Inverted dark-background graphic")

        # Aggressive CLAHE for high-contrast text recovery
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(6, 6))
        gray = clahe.apply(gray)

        # Denoise
        gray = cv2.fastNlMeansDenoising(gray, None, 12, 7, 21)

        # Adaptive threshold with larger block for varied backgrounds
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=21,
            C=5,
        )

        # Dilate slightly to connect broken characters
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
        binary = cv2.dilate(binary, kernel, iterations=1)

        return binary

    def preprocess_whatsapp_forward(self, image: np.ndarray) -> np.ndarray:
        """For JPEG-compressed images forwarded multiple times.

        Aggressive denoising to remove compression blocking artifacts,
        then sharpen text edges.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Heavy bilateral filter (preserves edges while removing JPEG blocks)
        gray = cv2.bilateralFilter(gray, 9, 75, 75)

        # Additional NLM denoise
        gray = cv2.fastNlMeansDenoising(gray, None, 15, 7, 21)

        # Unsharp mask to recover text edges after heavy denoise
        blurred = cv2.GaussianBlur(gray, (0, 0), 3)
        gray = cv2.addWeighted(gray, 1.5, blurred, -0.5, 0)

        # CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # Adaptive threshold
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=15,
            C=3,
        )

        # Morphological close to fill broken characters
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        return binary

    def preprocess_handwritten_number(self, image: np.ndarray) -> np.ndarray:
        """For photographs of handwritten phone numbers/notes.

        Morphological operations to enhance pen/pencil strokes.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Denoise
        gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)

        # Otsu threshold
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        # Morphological operations to enhance strokes
        # Close: fill gaps in strokes
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_close)

        # Dilate slightly to thicken thin pen strokes
        kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        binary = cv2.dilate(binary, kernel_dilate, iterations=1)

        # Erode back to original-ish stroke width (sharpens)
        kernel_erode = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
        binary = cv2.erode(binary, kernel_erode, iterations=1)

        # Re-invert to white background, dark text
        binary = cv2.bitwise_not(binary)

        return binary

    def preprocess_photo(self, image: np.ndarray) -> np.ndarray:
        """Generic photo preprocessor (camera photo of screen/paper).

        Standard pipeline: resize, denoise, deskew, CLAHE, threshold.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Denoise
        gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)

        # Deskew
        gray = _deskew(gray)

        # CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # Adaptive threshold
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=11,
            C=2,
        )

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        return binary


# ---------------------------------------------------------------------------
# Legacy ImagePreprocessor (kept for backward compatibility)
# ---------------------------------------------------------------------------

class ImagePreprocessor:
    """Multi-step image preprocessor optimized for OCR on scam images.

    Now delegates to ScamImagePreprocessor for type-aware processing.
    """

    def __init__(
        self,
        target_width: int = 1200,
        denoise_strength: int = 10,
        clahe_clip: float = 2.0,
        clahe_grid: Tuple[int, int] = (8, 8),
    ):
        self.target_width = target_width
        self.denoise_strength = denoise_strength
        self.clahe_clip = clahe_clip
        self.clahe_grid = clahe_grid
        self.scam_preprocessor = ScamImagePreprocessor()

    def preprocess(self, image_path: str) -> np.ndarray:
        """Run type-aware preprocessing pipeline on an image.

        Args:
            image_path: Path to input image file.

        Returns:
            Enhanced grayscale image ready for OCR.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        img = cv2.imread(str(path))
        if img is None:
            raise ValueError(f"Failed to load image: {image_path}")
        logger.debug("Loaded image: %s (%dx%d)", path.name, img.shape[1], img.shape[0])

        # Resize
        img = self._resize(img)

        # Detect type and preprocess accordingly
        image_type = self.scam_preprocessor.detect_image_type(img)
        logger.info("Detected image type: %s for %s", image_type, path.name)

        binary = self.scam_preprocessor.preprocess_for_type(img, image_type)

        logger.debug("Preprocessing complete: %dx%d", binary.shape[1], binary.shape[0])
        return binary

    def preprocess_color(self, image_path: str) -> np.ndarray:
        """Preprocess image but keep color (for region detection)."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        img = cv2.imread(str(path))
        if img is None:
            raise ValueError(f"Failed to load image: {image_path}")
        return self._resize(img)

    def get_image_type(self, image_path: str) -> str:
        """Detect the image type without full preprocessing.

        Args:
            image_path: Path to image file.

        Returns:
            Image type string.
        """
        img = cv2.imread(str(image_path))
        if img is None:
            return "PHOTO"
        img = self._resize(img)
        return self.scam_preprocessor.detect_image_type(img)

    def extract_regions(self, image: np.ndarray) -> List[np.ndarray]:
        """Detect and extract text region crops from image using MSER."""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        mser = cv2.MSER_create()
        mser.setMinArea(100)
        mser.setMaxArea(10000)

        regions, _ = mser.detectRegions(gray)
        bboxes = [cv2.boundingRect(r.reshape(-1, 1, 2)) for r in regions]
        bboxes = _merge_boxes(bboxes)

        crops = []
        for x, y, w, h in bboxes:
            if w > 20 and h > 10 and w / h > 0.5:
                pad = 5
                x1 = max(0, x - pad)
                y1 = max(0, y - pad)
                x2 = min(gray.shape[1], x + w + pad)
                y2 = min(gray.shape[0], y + h + pad)
                crops.append(gray[y1:y2, x1:x2])

        logger.debug("Extracted %d text regions", len(crops))
        return crops

    def _resize(self, img: np.ndarray) -> np.ndarray:
        """Resize image to target width maintaining aspect ratio."""
        h, w = img.shape[:2]
        if w < self.target_width:
            scale = self.target_width / w
            new_w = self.target_width
            new_h = int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        elif w > self.target_width * 2:
            scale = self.target_width / w
            new_w = self.target_width
            new_h = int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return img


# ---------------------------------------------------------------------------
# Shared utility functions
# ---------------------------------------------------------------------------

def _deskew(gray: np.ndarray) -> np.ndarray:
    """Deskew image using Hough line transform."""
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180,
        threshold=100,
        minLineLength=gray.shape[1] // 4,
        maxLineGap=20,
    )
    if lines is None or len(lines) == 0:
        return gray

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(angle) < 15:
            angles.append(angle)

    if not angles:
        return gray

    median_angle = np.median(angles)
    if abs(median_angle) < 0.5:
        return gray

    h, w = gray.shape
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(
        gray, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    logger.debug("Deskewed by %.2f degrees", median_angle)
    return rotated


def _merge_boxes(
    boxes: List[Tuple[int, int, int, int]],
    overlap_thresh: float = 0.3,
) -> List[Tuple[int, int, int, int]]:
    """Merge overlapping bounding boxes using NMS-like approach."""
    if not boxes:
        return []

    boxes_arr = np.array(boxes, dtype=np.float32)
    x1 = boxes_arr[:, 0]
    y1 = boxes_arr[:, 1]
    x2 = x1 + boxes_arr[:, 2]
    y2 = y1 + boxes_arr[:, 3]
    areas = boxes_arr[:, 2] * boxes_arr[:, 3]

    idxs = np.argsort(areas)[::-1]
    merged = []

    while len(idxs) > 0:
        i = idxs[0]
        merged.append(boxes[i])

        xx1 = np.maximum(x1[i], x1[idxs[1:]])
        yy1 = np.maximum(y1[i], y1[idxs[1:]])
        xx2 = np.minimum(x2[i], x2[idxs[1:]])
        yy2 = np.minimum(y2[i], y2[idxs[1:]])

        w = np.maximum(0, xx2 - xx1)
        h = np.maximum(0, yy2 - yy1)
        overlap = (w * h) / areas[idxs[1:]]

        remove = np.where(overlap > overlap_thresh)[0]
        idxs = np.delete(idxs, np.concatenate(([0], remove + 1)))

    return merged
