"""
CyberLens — Face Extractor using OpenCV Haar Cascade
=======================================================
Detects and extracts face regions from images using OpenCV's
built-in Haar cascade classifier (no extra dependencies).
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("cyberlens.deepfake.face_extractor")


class FaceExtractor:
    """Face detection and extraction using OpenCV Haar cascade.

    Uses haarcascade_frontalface_default for face detection.
    No additional dependencies required beyond OpenCV.

    Attributes:
        cascade: cv2.CascadeClassifier instance.
        min_face_size: Minimum face size in pixels.
        scale_factor: Detection scale factor.
        min_neighbors: Minimum neighbors for detection reliability.
    """

    def __init__(
        self,
        min_face_size: Tuple[int, int] = (60, 60),
        scale_factor: float = 1.1,
        min_neighbors: int = 5,
    ):
        """Initialize face extractor.

        Args:
            min_face_size: Minimum face dimensions (w, h) in pixels.
            scale_factor: Image scale factor for multi-scale detection.
            min_neighbors: Required neighbor detections for confidence.
        """
        self.min_face_size = min_face_size
        self.scale_factor = scale_factor
        self.min_neighbors = min_neighbors

        # Load Haar cascade
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.cascade = cv2.CascadeClassifier(cascade_path)

        if self.cascade.empty():
            raise RuntimeError(
                f"Failed to load Haar cascade from {cascade_path}. "
                "Ensure OpenCV is properly installed."
            )
        logger.info("FaceExtractor initialized (min_size=%s)", min_face_size)

    def extract_faces(
        self,
        image_path: str,
        margin: float = 0.2,
        target_size: Tuple[int, int] = (224, 224),
    ) -> List[np.ndarray]:
        """Detect and extract face regions from image.

        Args:
            image_path: Path to input image.
            margin: Margin around face as fraction of face size.
            target_size: Resize extracted faces to this size.

        Returns:
            List of face crops as numpy arrays (RGB, resized).
        """
        img = cv2.imread(image_path)
        if img is None:
            logger.warning("Cannot read image: %s", image_path)
            return []

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        # Detect faces
        faces = self.cascade.detectMultiScale(
            gray,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=self.min_face_size,
            flags=cv2.CASCADE_SCALE_IMAGE,
        )

        if len(faces) == 0:
            logger.info("No faces detected in %s", Path(image_path).name)
            return []

        logger.info("Detected %d face(s) in %s", len(faces), Path(image_path).name)

        # Extract and resize each face
        crops = []
        h_img, w_img = img.shape[:2]

        for (x, y, w, h) in faces:
            # Add margin
            margin_x = int(w * margin)
            margin_y = int(h * margin)
            x1 = max(0, x - margin_x)
            y1 = max(0, y - margin_y)
            x2 = min(w_img, x + w + margin_x)
            y2 = min(h_img, y + h + margin_y)

            face_crop = img[y1:y2, x1:x2]
            face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
            face_resized = cv2.resize(face_rgb, target_size, interpolation=cv2.INTER_AREA)
            crops.append(face_resized)

        return crops

    def extract_faces_from_array(
        self,
        image: np.ndarray,
        margin: float = 0.2,
        target_size: Tuple[int, int] = (224, 224),
    ) -> List[np.ndarray]:
        """Extract faces from a numpy array image.

        Args:
            image: Input image as numpy array (BGR).
            margin: Margin around face as fraction.
            target_size: Resize faces to this size.

        Returns:
            List of face crops as numpy arrays (RGB, resized).
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        gray = cv2.equalizeHist(gray)

        faces = self.cascade.detectMultiScale(
            gray,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=self.min_face_size,
        )

        if len(faces) == 0:
            return []

        crops = []
        h_img, w_img = image.shape[:2]

        for (x, y, w, h) in faces:
            margin_x = int(w * margin)
            margin_y = int(h * margin)
            x1 = max(0, x - margin_x)
            y1 = max(0, y - margin_y)
            x2 = min(w_img, x + w + margin_x)
            y2 = min(h_img, y + h + margin_y)

            face_crop = image[y1:y2, x1:x2]
            if len(image.shape) == 3:
                face_crop = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
            face_resized = cv2.resize(face_crop, target_size, interpolation=cv2.INTER_AREA)
            crops.append(face_resized)

        return crops

    def draw_faces(
        self,
        image_path: str,
        output_path: Optional[str] = None,
    ) -> np.ndarray:
        """Draw bounding boxes around detected faces.

        Args:
            image_path: Path to input image.
            output_path: Optional path to save annotated image.

        Returns:
            Annotated image with face boxes drawn.
        """
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        faces = self.cascade.detectMultiScale(
            gray,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=self.min_face_size,
        )

        annotated = img.copy()
        for (x, y, w, h) in faces:
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(
                annotated,
                f"Face ({w}x{h})",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )

        if output_path:
            cv2.imwrite(output_path, annotated)
            logger.info("Saved annotated image → %s", output_path)

        return annotated

    def count_faces(self, image_path: str) -> int:
        """Count faces in an image without extracting.

        Args:
            image_path: Path to input image.

        Returns:
            Number of faces detected.
        """
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return 0

        img = cv2.equalizeHist(img)
        faces = self.cascade.detectMultiScale(
            img,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=self.min_face_size,
        )
        return len(faces)
