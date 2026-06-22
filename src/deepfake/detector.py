"""
CyberLens — Deepfake Detector (Upgraded)
============================================
EfficientNet-B4 deepfake detection with type classification:
FACE_SWAP, FACE_REENACTMENT, ENTIRELY_GENERATED, VOICE_CLONE.

Now also classifies target person type and suspected use case
(INVESTMENT_SCAM, SEXTORTION, DIGITAL_ARREST).

Author: CyberLens Team — GPCSSI Internship
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision import models, transforms

from src.deepfake.face_extractor import FaceExtractor

logger = logging.getLogger("cyberlens.deepfake.detector")


class DeepfakeType(Enum):
    """Classification of deepfake manipulation type."""
    FACE_SWAP = "face_swap"
    FACE_REENACTMENT = "reenactment"
    ENTIRELY_GENERATED = "generated"
    VOICE_CLONE = "voice_clone"
    UNKNOWN = "unknown"


class TargetPersonType(Enum):
    """Type of person targeted in the deepfake."""
    CELEBRITY = "celebrity"
    POLITICIAN = "politician"
    GOVT_OFFICIAL = "govt_official"
    PRIVATE = "private"
    UNKNOWN = "unknown"


class SuspectedUseCase(Enum):
    """Suspected scam use case for the deepfake."""
    INVESTMENT_SCAM = "investment_scam"
    SEXTORTION = "sextortion"
    DIGITAL_ARREST = "digital_arrest"
    FAKE_ENDORSEMENT = "fake_endorsement"
    OTHER = "other"


@dataclass
class DeepfakeResult:
    """Result from deepfake analysis of an image."""
    deepfake_probability: float
    is_suspected: bool
    deepfake_type: str = "unknown"
    target_person_type: str = "unknown"
    use_case_suspected: str = "other"
    manipulation_indicators: List[str] = field(default_factory=list)
    face_count: int = 0
    analysis_confidence: float = 0.0
    processing_time_ms: float = 0.0
    model_used: str = "efficientnet-b4"
    celebrities_detected: List[str] = field(default_factory=list)
    it_act_sections: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "deepfake_probability": round(self.deepfake_probability, 4),
            "is_suspected": self.is_suspected,
            "deepfake_type": self.deepfake_type,
            "target_person_type": self.target_person_type,
            "use_case_suspected": self.use_case_suspected,
            "manipulation_indicators": self.manipulation_indicators,
            "face_count": self.face_count,
            "analysis_confidence": round(self.analysis_confidence, 4),
            "processing_time_ms": round(self.processing_time_ms, 2),
            "model_used": self.model_used,
            "celebrities_detected": self.celebrities_detected,
            "it_act_sections": self.it_act_sections,
        }


class DeepfakeDetector:
    """Deepfake detection with type classification and use-case inference.

    Upgraded pipeline:
        1. Extract faces from image
        2. Run EfficientNet-B4 for deepfake probability
        3. Classify deepfake type (swap/reenactment/generated)
        4. Detect target person type (celebrity/politician/govt)
        5. Infer suspected use case (investment/sextortion/digital arrest)
    """

    TRANSFORM = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])

    def __init__(
        self,
        model_dir: str = "models/deepfake_detector",
        device: Optional[str] = None,
        threshold: float = 0.65,
    ):
        self.model_dir = Path(model_dir)
        self.threshold = threshold
        self._loaded = False

        if device:
            self.device = torch.device(device)
        elif torch.cuda.is_available():
            self.device = torch.device("cuda")
        else:
            self.device = torch.device("cpu")

        self.face_extractor = FaceExtractor()

        # Celebrity DB for person identification
        self._celeb_db = None
        try:
            from src.deepfake.celebrity_db import CelebrityDatabase
            self._celeb_db = CelebrityDatabase()
        except Exception as e:
            logger.debug("CelebrityDatabase not available: %s", e)

        try:
            self._load_model()
        except Exception as e:
            logger.warning(
                "Could not load deepfake model from %s: %s. "
                "Using heuristic analysis only.",
                self.model_dir, e,
            )

    def _load_model(self) -> None:
        """Load EfficientNet-B4 model with custom head."""
        weights_path = self.model_dir / "best_model.pth"
        if not weights_path.exists():
            raise FileNotFoundError(f"Model weights not found: {weights_path}")

        model = models.efficientnet_b4(weights=None)
        num_features = model.classifier[1].in_features
        model.classifier = nn.Sequential(
            nn.Dropout(p=0.4, inplace=True),
            nn.Linear(num_features, 2),
        )

        state_dict = torch.load(weights_path, map_location=self.device)
        model.load_state_dict(state_dict)
        model.to(self.device)
        model.eval()

        self._model = model
        self._loaded = True
        logger.info("DeepfakeDetector loaded (device=%s)", self.device)

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def analyze(
        self,
        image_path: str,
        ocr_text: str = "",
    ) -> DeepfakeResult:
        """Analyze an image for deepfake indicators with use-case inference.

        Args:
            image_path: Path to input image.
            ocr_text: OCR text from the image (for context-aware analysis).

        Returns:
            DeepfakeResult with type, target person, and use case.
        """
        start_time = time.time()

        faces = self.face_extractor.extract_faces(image_path)
        face_count = len(faces)

        if face_count == 0:
            elapsed = (time.time() - start_time) * 1000
            return DeepfakeResult(
                deepfake_probability=0.0,
                is_suspected=False,
                manipulation_indicators=["No faces detected in image"],
                face_count=0,
                analysis_confidence=0.0,
                processing_time_ms=elapsed,
            )

        # ML prediction
        if self._loaded:
            probabilities = [self._predict_face(face) for face in faces]
            max_prob = max(probabilities)
        else:
            max_prob = self._heuristic_analysis(image_path)

        # Classify deepfake type
        df_type = self._classify_deepfake_type(image_path, faces, max_prob)

        # Detect celebrities in OCR text
        celebrities = []
        if self._celeb_db and ocr_text:
            matched = self._celeb_db.search(ocr_text)
            celebrities = [m.name for m in matched]

        # Detect target person type
        target_type = self._classify_target_person(celebrities, ocr_text)

        # Infer use case
        use_case = self._infer_use_case(ocr_text, target_type, celebrities)

        # Manipulation indicators
        indicators = self._detect_indicators(image_path, faces, max_prob, df_type)

        # Get applicable IT Act sections
        it_sections = self._get_it_sections(use_case, target_type)

        # Analysis confidence
        if face_count >= 1 and self._loaded:
            analysis_confidence = min(0.95, 0.7 + 0.05 * face_count)
        else:
            analysis_confidence = 0.3

        elapsed = (time.time() - start_time) * 1000

        result = DeepfakeResult(
            deepfake_probability=max_prob,
            is_suspected=max_prob >= self.threshold,
            deepfake_type=df_type.value,
            target_person_type=target_type.value,
            use_case_suspected=use_case.value,
            manipulation_indicators=indicators,
            face_count=face_count,
            analysis_confidence=analysis_confidence,
            processing_time_ms=elapsed,
            model_used="efficientnet-b4" if self._loaded else "heuristic",
            celebrities_detected=celebrities,
            it_act_sections=it_sections,
        )

        logger.info(
            "Deepfake: prob=%.3f, type=%s, target=%s, use=%s, celebs=%s, time=%.0fms",
            max_prob, df_type.value, target_type.value, use_case.value,
            celebrities, elapsed,
        )
        return result

    def analyze_batch(self, paths: List[str]) -> List[DeepfakeResult]:
        """Analyze multiple images."""
        results = []
        for path in paths:
            try:
                result = self.analyze(path)
            except Exception as e:
                logger.error("Analysis failed for %s: %s", path, e)
                result = DeepfakeResult(
                    deepfake_probability=0.0, is_suspected=False,
                    manipulation_indicators=[f"Error: {e}"],
                )
            results.append(result)
        return results

    def _predict_face(self, face: np.ndarray) -> float:
        """Run model inference on a single face crop."""
        tensor = self.TRANSFORM(face).unsqueeze(0).to(self.device)
        with torch.no_grad():
            outputs = self._model(tensor)
            probs = torch.softmax(outputs, dim=1)
            return probs[0][1].item()

    def _classify_deepfake_type(
        self, image_path: str, faces: List[np.ndarray], prob: float
    ) -> DeepfakeType:
        """Classify the type of deepfake manipulation.

        Uses heuristics on face region properties to distinguish
        swap, reenactment, and generated faces.
        """
        if prob < self.threshold:
            return DeepfakeType.UNKNOWN

        if not faces:
            return DeepfakeType.UNKNOWN

        face = faces[0]
        if face.size == 0:
            return DeepfakeType.UNKNOWN

        try:
            gray = cv2.cvtColor(face, cv2.COLOR_RGB2GRAY) if len(face.shape) == 3 else face

            # Edge analysis around face boundary
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size

            # Texture analysis
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

            # Noise analysis (frequency domain)
            f_transform = np.fft.fft2(gray.astype(float))
            f_shift = np.fft.fftshift(f_transform)
            magnitude = np.abs(f_shift)
            high_freq_ratio = np.sum(magnitude > np.mean(magnitude) * 2) / magnitude.size

            # Classification heuristics
            if edge_density > 0.08 and laplacian_var < 200:
                return DeepfakeType.FACE_SWAP
            elif laplacian_var < 50 and high_freq_ratio < 0.05:
                return DeepfakeType.ENTIRELY_GENERATED
            elif edge_density < 0.03:
                return DeepfakeType.FACE_REENACTMENT
            else:
                return DeepfakeType.FACE_SWAP

        except Exception:
            return DeepfakeType.UNKNOWN

    def _classify_target_person(
        self, celebrities: List[str], ocr_text: str
    ) -> TargetPersonType:
        """Classify what type of person is being targeted."""
        if not celebrities and not ocr_text:
            return TargetPersonType.UNKNOWN

        if self._celeb_db and celebrities:
            for celeb_name in celebrities:
                profile = self._celeb_db.get_by_name(celeb_name)
                if profile:
                    cat = profile.category
                    if cat == "POLITICS":
                        return TargetPersonType.POLITICIAN
                    elif cat == "GOVT_OFFICIAL":
                        return TargetPersonType.GOVT_OFFICIAL
                    elif cat in ("ENTERTAINMENT", "SPORTS", "BUSINESS"):
                        return TargetPersonType.CELEBRITY

        text_lower = ocr_text.lower()
        govt_keywords = ["cbi", "ed ", "police", "officer", "inspector",
                         "customs", "income tax", "court", "judge"]
        if any(kw in text_lower for kw in govt_keywords):
            return TargetPersonType.GOVT_OFFICIAL

        return TargetPersonType.PRIVATE

    def _infer_use_case(
        self, ocr_text: str, target_type: TargetPersonType,
        celebrities: List[str],
    ) -> SuspectedUseCase:
        """Infer the suspected scam use case from context."""
        text_lower = ocr_text.lower()

        # Sextortion indicators
        sextortion_kw = [
            "viral", "leak", "nude", "intimate", "blackmail",
            "payment karo", "पैसे भेजो", "वीडियो वायरल",
            "expose", "morphed", "private video",
        ]
        if any(kw in text_lower for kw in sextortion_kw):
            return SuspectedUseCase.SEXTORTION

        # Digital arrest indicators
        arrest_kw = [
            "digital arrest", "arrest warrant", "fir registered",
            "court order", "cbi", "ed notice", "cyber crime branch",
            "डिजिटल अरेस्ट", "गिरफ़्तारी", "FIR",
            "digital custody", "verification pending",
        ]
        if any(kw in text_lower for kw in arrest_kw):
            return SuspectedUseCase.DIGITAL_ARREST

        # Investment scam with celebrity
        invest_kw = [
            "invest", "return", "profit", "double", "guaranteed",
            "stock", "mutual fund", "crypto", "trading",
            "निवेश", "मुनाफा", "रिटर्न",
        ]
        if celebrities and any(kw in text_lower for kw in invest_kw):
            return SuspectedUseCase.FAKE_ENDORSEMENT

        if any(kw in text_lower for kw in invest_kw):
            return SuspectedUseCase.INVESTMENT_SCAM

        if target_type == TargetPersonType.GOVT_OFFICIAL:
            return SuspectedUseCase.DIGITAL_ARREST

        if target_type == TargetPersonType.CELEBRITY:
            return SuspectedUseCase.FAKE_ENDORSEMENT

        return SuspectedUseCase.OTHER

    def _get_it_sections(
        self, use_case: SuspectedUseCase, target_type: TargetPersonType
    ) -> List[str]:
        """Get applicable IT Act sections for the deepfake use case."""
        sections = []

        base = ["IT Act §66D — Cheating by personation using computer"]

        if use_case == SuspectedUseCase.SEXTORTION:
            sections = [
                "IT Act §66E — Violation of privacy",
                "BNS §77 — Criminal intimidation",
                "IT Act §67 — Publishing obscene material",
                "IT Act §67A — Sexually explicit material",
            ]
        elif use_case == SuspectedUseCase.DIGITAL_ARREST:
            sections = [
                "IPC §170 / BNS §204 — Impersonating public servant",
                "IT Act §66D — Cheating by personation",
                "BNS §351 — Criminal intimidation",
            ]
        elif use_case in (SuspectedUseCase.INVESTMENT_SCAM, SuspectedUseCase.FAKE_ENDORSEMENT):
            sections = [
                "IT Act §66D — Cheating by personation",
                "IPC §420 / BNS §318 — Cheating",
                "Copyright Act §63 — Using likeness without consent",
            ]
            if use_case == SuspectedUseCase.INVESTMENT_SCAM:
                sections.append("SEBI Act §12A — Fraudulent trade practices")

        return base + sections

    def _heuristic_analysis(self, image_path: str) -> float:
        """Heuristic deepfake analysis when model is not loaded."""
        try:
            img = cv2.imread(image_path)
            if img is None:
                return 0.0

            score = 0.0
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            if laplacian_var < 50:
                score += 0.15

            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            h_std = np.std(hsv[:, :, 0])
            if h_std > 60:
                score += 0.1

            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            if edge_density < 0.02 or edge_density > 0.15:
                score += 0.1

            return min(score, 0.5)
        except Exception:
            return 0.0

    def _detect_indicators(
        self, image_path: str, faces: List[np.ndarray],
        deepfake_prob: float, df_type: DeepfakeType,
    ) -> List[str]:
        """Detect human-readable manipulation indicators."""
        indicators = []

        if deepfake_prob >= 0.8:
            indicators.append("HIGH PROBABILITY: Strong deepfake indicators detected")
        elif deepfake_prob >= self.threshold:
            indicators.append("MODERATE: Possible face manipulation detected")

        if df_type != DeepfakeType.UNKNOWN:
            type_desc = {
                DeepfakeType.FACE_SWAP: "Face swap detected — different face placed on body",
                DeepfakeType.FACE_REENACTMENT: "Face reenactment — expressions manipulated",
                DeepfakeType.ENTIRELY_GENERATED: "AI-generated face — no real person",
                DeepfakeType.VOICE_CLONE: "Voice clone suspected",
            }
            indicators.append(type_desc.get(df_type, f"Manipulation type: {df_type.value}"))

        try:
            img = cv2.imread(image_path)
            if img is not None:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                blur = cv2.Laplacian(gray, cv2.CV_64F).var()
                if blur < 100:
                    indicators.append("Low sharpness: Possible blending artifacts")

                for i, face in enumerate(faces):
                    face_gray = cv2.cvtColor(face, cv2.COLOR_RGB2GRAY) if len(face.shape) == 3 else face
                    face_noise = np.std(face_gray.astype(float))
                    if face_noise < 20:
                        indicators.append(f"Face {i+1}: Unusually smooth texture")
                    elif face_noise > 60:
                        indicators.append(f"Face {i+1}: High noise in face region")
        except Exception as e:
            logger.debug("Indicator analysis error: %s", e)

        if not indicators:
            indicators.append("No significant manipulation indicators found")

        return indicators
