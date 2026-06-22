"""
CyberLens -- Confidence Engine
==================================
Computes how much the system's own assessment should be trusted.

Confidence != Threat probability.
- High confidence + low threat = "We are sure this is safe."
- Low confidence + high threat = "This looks bad but we need more data."
Both are useful.  Both are different from a risk score.

Confidence is the geometric mean of three dimensions:
    1. Data completeness -- do we have enough information?
    2. Extraction reliability -- is the extracted data correct?
    3. Evidence convergence -- do multiple sources agree?

Geometric mean is chosen because confidence should collapse
to zero if ANY dimension is poor.  A system with perfect
extraction but zero data should have zero confidence.

Author: CyberLens Team
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from src.intelligence.evidence_model import (
    ChannelAssessment,
    EvidenceItem,
    EvidenceStrength,
)

logger = logging.getLogger("cyberlens.intelligence.confidence")


# ---------------------------------------------------------------------------
# Confidence Assessment
# ---------------------------------------------------------------------------

@dataclass
class ConfidenceAssessment:
    """How reliable is our assessment of this channel?

    Attributes:
        channel_id:  Channel being assessed.
        data_completeness:  Fraction of expected data fields populated (0-1).
        observation_duration_days:  How long we have been watching.
        post_count_observed:  How many posts were analyzed.
        entity_extraction_confidence:  Average extraction confidence.
        source_count:  Number of independent evidence sources.
        evidence_agreement:  Do evidence items point the same direction? (0-1).
        overall_confidence:  Computed overall confidence (0-1).
        confidence_class:  HIGH | MODERATE | LOW | INSUFFICIENT.
        calibration_status:  Always "UNCALIBRATED" until validated.
    """
    channel_id: str = ""

    # Dimension 1: Data completeness
    data_completeness: float = 0.0
    observation_duration_days: int = 0
    post_count_observed: int = 0

    # Dimension 2: Extraction reliability
    entity_extraction_confidence: float = 0.0

    # Dimension 3: Source convergence
    source_count: int = 0
    evidence_agreement: float = 0.0

    # Overall
    overall_confidence: float = 0.0
    confidence_class: str = "INSUFFICIENT"
    calibration_status: str = "UNCALIBRATED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Confidence Engine
# ---------------------------------------------------------------------------

# Expected data fields for a complete channel assessment
EXPECTED_FIELDS = [
    "posts",
    "entities_found",
    "channel_metadata",
    "posting_schedule",
    "language_distribution",
    "media_ratio",
    "growth_snapshots",
]

# Minimum observation thresholds
MIN_POSTS_FOR_MODERATE = 20
MIN_POSTS_FOR_HIGH = 100
MIN_DAYS_FOR_HIGH = 14


class ConfidenceEngine:
    """Computes structured confidence for channel assessments.

    Confidence is NOT a score to be maximized.  It is a measure
    of how much the system's output should be trusted by an analyst.

    A low-confidence assessment should trigger "gather more data"
    not "this is probably fine."
    """

    def compute(
        self,
        assessment: ChannelAssessment,
        channel_data: Dict[str, Any],
    ) -> ConfidenceAssessment:
        """Compute confidence for a channel assessment.

        Args:
            assessment:  The ChannelAssessment to evaluate.
            channel_data:  Raw channel data dict (for completeness check).

        Returns:
            ConfidenceAssessment with overall confidence and dimensions.
        """
        conf = ConfidenceAssessment(channel_id=assessment.channel_id)

        # -- Dimension 1: Data completeness --------------------------------
        populated = sum(
            1 for f in EXPECTED_FIELDS
            if channel_data.get(f)
        )
        conf.data_completeness = populated / len(EXPECTED_FIELDS)

        posts = channel_data.get("posts", [])
        conf.post_count_observed = len(posts)

        # Observation duration
        conf.observation_duration_days = self._observation_days(posts)

        # -- Dimension 2: Extraction reliability ---------------------------
        evidence_items = assessment.all_evidence
        if evidence_items:
            conf.entity_extraction_confidence = sum(
                e.extraction_confidence for e in evidence_items
            ) / len(evidence_items)
        else:
            # No evidence extracted -> low extraction confidence
            conf.entity_extraction_confidence = 0.1

        # -- Dimension 3: Source convergence --------------------------------
        sources = set(e.source for e in evidence_items)
        conf.source_count = len(sources)

        # Evidence agreement: are evidence items consistently
        # pointing toward threat or consistently pointing toward safe?
        conf.evidence_agreement = self._compute_agreement(evidence_items)

        # -- Overall confidence (geometric mean) ---------------------------
        dims = [
            max(conf.data_completeness, 0.01),
            max(conf.entity_extraction_confidence, 0.01),
            max(conf.evidence_agreement, 0.01),
        ]
        conf.overall_confidence = round(
            math.prod(dims) ** (1.0 / len(dims)), 4
        )

        # Penalty for very few posts
        if conf.post_count_observed < MIN_POSTS_FOR_MODERATE:
            conf.overall_confidence *= 0.5

        conf.overall_confidence = min(conf.overall_confidence, 0.99)

        # Classification
        conf.confidence_class = self._classify(conf)
        conf.calibration_status = "UNCALIBRATED"

        logger.info(
            "Confidence for @%s: %.2f (%s) [complete=%.2f extract=%.2f agree=%.2f posts=%d]",
            conf.channel_id,
            conf.overall_confidence,
            conf.confidence_class,
            conf.data_completeness,
            conf.entity_extraction_confidence,
            conf.evidence_agreement,
            conf.post_count_observed,
        )

        return conf

    # =====================================================================
    # Helpers
    # =====================================================================

    @staticmethod
    def _observation_days(posts: List[Dict]) -> int:
        """Compute observation duration from post timestamps."""
        from datetime import datetime
        timestamps = []
        for p in posts:
            ts = p.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    timestamps.append(dt)
                except Exception:
                    pass
        if len(timestamps) < 2:
            return 0
        timestamps.sort()
        return max(1, (timestamps[-1] - timestamps[0]).days)

    @staticmethod
    def _compute_agreement(evidence_items: List[EvidenceItem]) -> float:
        """Compute evidence agreement score.

        Measures whether evidence items consistently point in the
        same direction (all strong or all weak).  Mixed signals
        indicate uncertainty.

        Returns:
            Float in [0, 1].  1 = perfect agreement.
        """
        if not evidence_items:
            return 0.0

        # Group by strength
        strengths = [e.strength for e in evidence_items]
        strength_counts = Counter(strengths)

        # Agreement = fraction of items with the most common strength
        dominant_count = strength_counts.most_common(1)[0][1]
        return dominant_count / len(evidence_items)

    @staticmethod
    def _classify(conf: ConfidenceAssessment) -> str:
        """Classify overall confidence."""
        c = conf.overall_confidence

        if (c >= 0.6
                and conf.post_count_observed >= MIN_POSTS_FOR_HIGH
                and conf.source_count >= 2):
            return "HIGH"

        if (c >= 0.35
                and conf.post_count_observed >= MIN_POSTS_FOR_MODERATE):
            return "MODERATE"

        if c >= 0.15:
            return "LOW"

        return "INSUFFICIENT"
