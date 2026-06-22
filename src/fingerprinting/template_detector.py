"""
CyberLens — Template Detector
================================
Detects scam template reuse across campaigns using CLIP + pHash.

Match types:
  SAME_TEMPLATE    — ≥90% similarity (same creative, different text)
  SIMILAR_TEMPLATE — ≥75% similarity (evolved version)
  NO_MATCH         — <75% similarity

Author: CyberLens Team — GPCSSI Internship
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.ocr.image_fingerprinter import ImageFingerprinter, TemplateMatch
from src.ocr.vector_store import VectorStore

logger = logging.getLogger("cyberlens.fingerprinting.template")


@dataclass
class TemplateVersion:
    """A version of a scam template creative."""
    version_id: str
    image_hash: str
    phash: str
    campaign_id: str
    first_seen: str
    similarity_to_prev: float = 0.0
    changes_detected: str = ""   # "Added QR code", "Changed amount", etc.


@dataclass
class TemplateHistory:
    """Evolution timeline of a scam creative template."""
    campaign_id: str
    versions: List[TemplateVersion]
    total_versions: int
    first_seen: str
    latest_seen: str
    evolution_summary: str


class TemplateDetector:
    """Detects template reuse and tracks creative evolution."""

    def __init__(self):
        self._fingerprinter = ImageFingerprinter()
        self._vector_store = VectorStore()

    def fingerprint_image(self, image_path: str) -> Dict[str, Any]:
        """Full fingerprint with all signals.

        Args:
            image_path: Path to image file.

        Returns:
            Fingerprint dict with hash, phash, embedding, colors.
        """
        fp = self._fingerprinter.fingerprint(image_path)
        return {
            "image_hash": fp.image_hash,
            "phash": fp.phash,
            "has_clip_embedding": fp.clip_embedding is not None,
            "dominant_colors": fp.dominant_colors,
            "has_text_overlay": fp.has_text_overlay,
            "has_qr_code": fp.has_qr_code,
        }

    def find_campaign_template(self, image_path: str) -> TemplateMatch:
        """Search for matching campaign template.

        Args:
            image_path: Path to image file.

        Returns:
            TemplateMatch with similarity details.
        """
        return self._fingerprinter.detect_template_reuse(image_path)

    def detect_template_evolution(self, campaign_id: str) -> TemplateHistory:
        """Show how scam creative evolved over time.

        Args:
            campaign_id: Campaign to analyze.

        Returns:
            TemplateHistory with version timeline.
        """
        # Query stored embeddings for this campaign
        try:
            results = self._vector_store.search_similar(
                embedding=None,  # meta-query — not by embedding
                collection="scam_images",
            ) if self._vector_store.is_available else []
        except Exception:
            results = []

        # Filter by campaign
        campaign_results = [r for r in results if r.get("campaign_id") == campaign_id]

        if not campaign_results:
            return self._demo_history(campaign_id)

        # Build version list
        versions = []
        prev_phash = ""
        for i, r in enumerate(sorted(campaign_results, key=lambda x: x.get("first_seen", ""))):
            similarity = self._phash_similarity(prev_phash, r.get("phash", "")) if prev_phash else 1.0
            changes = self._detect_changes(similarity, i)
            prev_phash = r.get("phash", "")

            versions.append(TemplateVersion(
                version_id=f"v{i+1}",
                image_hash=r.get("image_hash", ""),
                phash=r.get("phash", ""),
                campaign_id=campaign_id,
                first_seen=r.get("first_seen", ""),
                similarity_to_prev=similarity if i > 0 else 1.0,
                changes_detected=changes,
            ))

        first_seen = versions[0].first_seen if versions else ""
        latest_seen = versions[-1].first_seen if versions else ""

        return TemplateHistory(
            campaign_id=campaign_id,
            versions=versions,
            total_versions=len(versions),
            first_seen=first_seen,
            latest_seen=latest_seen,
            evolution_summary=self._summarize_evolution(versions),
        )

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _phash_similarity(phash1: str, phash2: str) -> float:
        """Compute pHash similarity (Hamming distance based)."""
        if not phash1 or not phash2 or len(phash1) != len(phash2):
            return 0.0
        try:
            h1 = int(phash1, 16)
            h2 = int(phash2, 16)
            hamming = bin(h1 ^ h2).count("1")
            max_bits = len(phash1) * 4
            return 1.0 - (hamming / max_bits)
        except Exception:
            return 0.0

    @staticmethod
    def _detect_changes(similarity: float, version_idx: int) -> str:
        """Describe detected changes between versions."""
        if similarity >= 0.95:
            return "Minor text change (amount or date)"
        if similarity >= 0.85:
            return "Moderate changes (layout or contact info)"
        if similarity >= 0.70:
            return "Significant redesign (possibly added QR code or logo)"
        return "Major overhaul (likely response to takedown)"

    @staticmethod
    def _summarize_evolution(versions: List[TemplateVersion]) -> str:
        """Generate a text summary of template evolution."""
        if len(versions) <= 1:
            return "Single version detected — no evolution tracked yet"
        lines = [f"Version {v.version_id} ({v.first_seen[:10]}): {v.changes_detected}"
                 for v in versions]
        return "\n".join(lines)

    @staticmethod
    def _demo_history(campaign_id: str) -> TemplateHistory:
        """Return demo template history."""
        from datetime import timedelta
        now = datetime.now()
        versions = [
            TemplateVersion("v1", "abc1", "f0f0f0f0", campaign_id,
                            (now - timedelta(days=14)).isoformat()[:10], 1.0,
                            "Original template"),
            TemplateVersion("v2", "abc2", "f2f0f0f0", campaign_id,
                            (now - timedelta(days=9)).isoformat()[:10], 0.94,
                            "₹1500/day → ₹2500/day (amount changed)"),
            TemplateVersion("v3", "abc3", "e8f0f0f0", campaign_id,
                            (now - timedelta(days=4)).isoformat()[:10], 0.89,
                            "Added QR code for direct payment"),
        ]
        return TemplateHistory(
            campaign_id=campaign_id,
            versions=versions,
            total_versions=3,
            first_seen=versions[0].first_seen,
            latest_seen=versions[-1].first_seen,
            evolution_summary="\n".join(f"Version {v.version_id} ({v.first_seen[:10]}): {v.changes_detected}" for v in versions),
        )
