"""
CyberLens — Image Fingerprinter (CLIP + pHash)
=================================================
Generates visual fingerprints for scam images using CLIP embeddings.
Detects template reuse across campaigns.

Models: openai/clip-vit-base-patch32 (local via HuggingFace)
Vector DB: Qdrant (local mode, no server needed for dev)

Author: CyberLens Team — GPCSSI Internship
"""

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np

logger = logging.getLogger("cyberlens.ocr.fingerprinter")


@dataclass
class ImageFingerprint:
    """Complete image fingerprint."""
    image_hash: str            # SHA256
    phash: str                 # Perceptual hash (64-bit hex)
    clip_embedding: Optional[np.ndarray] = None
    dominant_colors: List[str] = field(default_factory=list)
    has_text_overlay: bool = False
    has_qr_code: bool = False
    template_regions: int = 0  # detected logo/watermark regions


@dataclass
class TemplateMatch:
    """Result of template matching against the vector DB."""
    matched: bool = False
    similarity: float = 0.0
    match_type: str = "NONE"   # SAME_TEMPLATE / SIMILAR_TEMPLATE / NO_MATCH
    campaign_id: str = ""
    campaign_name: str = ""
    first_seen: str = ""
    usage_count: int = 0
    diff_highlights: str = ""


class ImageFingerprinter:
    """Generates CLIP + pHash fingerprints for visual deduplication.

    Falls back to pHash-only mode if CLIP/transformers unavailable.
    """

    _clip_model = None
    _clip_processor = None
    _clip_loaded = False

    def __init__(self):
        self._try_load_clip()

    def _try_load_clip(self) -> None:
        """Lazy-load CLIP model."""
        if ImageFingerprinter._clip_loaded:
            return
        try:
            from transformers import CLIPModel, CLIPProcessor
            model_name = "openai/clip-vit-base-patch32"
            logger.info("Loading CLIP model: %s", model_name)
            ImageFingerprinter._clip_processor = CLIPProcessor.from_pretrained(model_name)
            ImageFingerprinter._clip_model = CLIPModel.from_pretrained(model_name)
            ImageFingerprinter._clip_loaded = True
            logger.info("CLIP model loaded")
        except ImportError:
            logger.info("transformers not installed — using pHash-only fingerprinting")
        except Exception as e:
            logger.warning("CLIP model load failed: %s — using pHash-only", e)
        finally:
            ImageFingerprinter._clip_loaded = True  # don't retry

    def fingerprint(self, image_path: str) -> ImageFingerprint:
        """Generate full fingerprint for an image.

        Args:
            image_path: Path to image file.

        Returns:
            ImageFingerprint with all computed fields.
        """
        from PIL import Image

        try:
            img = Image.open(image_path).convert("RGB")
        except Exception as e:
            logger.error("Cannot open image: %s — %s", image_path, e)
            return ImageFingerprint(image_hash="", phash="")

        # SHA256
        with open(image_path, "rb") as f:
            sha256 = hashlib.sha256(f.read()).hexdigest()

        # pHash
        phash = self._compute_phash(img)

        # CLIP embedding
        clip_embedding = self._compute_clip(img)

        # Dominant colors
        colors = self._dominant_colors(img)

        # Detect text overlay (most scam images have white/yellow text)
        has_text = self._has_text_overlay(img)

        return ImageFingerprint(
            image_hash=sha256,
            phash=phash,
            clip_embedding=clip_embedding,
            dominant_colors=colors,
            has_text_overlay=has_text,
        )

    def find_similar(
        self,
        embedding: np.ndarray,
        threshold: float = 0.85,
    ) -> List[dict]:
        """Search Qdrant vector DB for similar images.

        Args:
            embedding: CLIP embedding (512-dim).
            threshold: Minimum cosine similarity.

        Returns:
            List of similar image metadata dicts.
        """
        try:
            from src.ocr.vector_store import VectorStore
            store = VectorStore()
            return store.search_similar(embedding, top_k=5, score_threshold=threshold)
        except Exception as e:
            logger.debug("Vector search failed: %s", e)
            return []

    def detect_template_reuse(self, image_path: str) -> TemplateMatch:
        """Detect if image is a reused scam template.

        Args:
            image_path: Path to image file.

        Returns:
            TemplateMatch describing similarity to known templates.
        """
        fp = self.fingerprint(image_path)
        if fp.clip_embedding is None:
            # Fall back to pHash matching
            return self._phash_template_match(fp.phash)

        similars = self.find_similar(fp.clip_embedding)
        if not similars:
            return TemplateMatch(matched=False, match_type="NO_MATCH")

        top = similars[0]
        score = top.get("score", 0.0)

        if score >= 0.90:
            match_type = "SAME_TEMPLATE"
        elif score >= 0.75:
            match_type = "SIMILAR_TEMPLATE"
        else:
            return TemplateMatch(matched=False, match_type="NO_MATCH", similarity=score)

        return TemplateMatch(
            matched=True,
            similarity=score,
            match_type=match_type,
            campaign_id=top.get("campaign_id", ""),
            campaign_name=top.get("campaign_name", ""),
            first_seen=top.get("first_seen", ""),
            usage_count=top.get("usage_count", 0),
            diff_highlights=(
                f"{score:.0%} similar to Campaign '{top.get('campaign_name', '')}' "
                f"first seen {top.get('first_seen', '')[:10]}"
            ),
        )

    # ── Internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _compute_phash(img) -> str:
        """Compute perceptual hash (dHash)."""
        try:
            import cv2
            import numpy as np
            from PIL import Image
            # Resize to 9x8 grayscale
            small = img.convert("L").resize((9, 8))
            arr = np.array(small)
            # dHash: compare adjacent pixels
            diff = arr[:, 1:] > arr[:, :-1]
            return hex(int("".join(diff.flatten().astype(int).astype(str)), 2))[2:].zfill(16)
        except Exception:
            return ""

    def _compute_clip(self, img) -> Optional[np.ndarray]:
        """Compute CLIP embedding."""
        if not (self._clip_model and self._clip_processor):
            return None
        try:
            import torch
            inputs = self._clip_processor(images=img, return_tensors="pt")
            with torch.no_grad():
                features = self._clip_model.get_image_features(**inputs)
            emb = features[0].numpy()
            # L2 normalize
            norm = np.linalg.norm(emb)
            return emb / norm if norm > 0 else emb
        except Exception as e:
            logger.debug("CLIP embedding failed: %s", e)
            return None

    @staticmethod
    def _dominant_colors(img, n: int = 3) -> List[str]:
        """Extract n dominant colors as hex strings."""
        try:
            small = img.resize((50, 50)).quantize(colors=n).convert("RGB")
            colors = small.getcolors(50 * 50)
            if not colors:
                return []
            colors_sorted = sorted(colors, key=lambda x: x[0], reverse=True)
            return [f"#{r:02x}{g:02x}{b:02x}" for _, (r, g, b) in colors_sorted[:n]]
        except Exception:
            return []

    @staticmethod
    def _has_text_overlay(img) -> bool:
        """Heuristic: detect if image has text overlay (high contrast regions)."""
        try:
            import numpy as np
            gray = img.convert("L")
            arr = np.array(gray)
            std = arr.std()
            return bool(std > 40)  # high std = high contrast = likely text
        except Exception:
            return False

    @staticmethod
    def _phash_template_match(phash: str) -> TemplateMatch:
        """Simple pHash lookup when CLIP is unavailable."""
        # In production: compare against stored pHashes in SQLite
        return TemplateMatch(matched=False, match_type="NO_MATCH",
                             diff_highlights="pHash-only mode — CLIP unavailable")
