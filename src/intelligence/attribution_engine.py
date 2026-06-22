"""
CyberLens -- Attribution Engine
===================================
Probabilistic operator attribution between channels.

Answers:  P(same_operator | evidence_A, evidence_B, shared_evidence_AB)

Uses a log-linear model with justified initial coefficients.
Outputs decomposed probability with confidence intervals and
human-readable evidence summaries.

Mathematical formulation:
    log-odds = b0 + b1*infra_overlap + b2*behavioral_sim
             + b3*temporal_prox + b4*content_sim
             + b5*(infra_overlap * temporal_prox)

Initial coefficients are set by the principle of evidence strength
ordering and documented with explicit justification.  They will be
replaced by learned coefficients once 200+ analyst decisions are
available (see feedback_store.py).

Author: CyberLens Team
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from src.intelligence.evidence_model import (
    BehavioralEvidence,
    ChannelAssessment,
    EvidenceItem,
    EvidenceStrength,
    EvidenceType,
)

logger = logging.getLogger("cyberlens.intelligence.attribution")


# ---------------------------------------------------------------------------
# Attribution Result
# ---------------------------------------------------------------------------

@dataclass
class AttributionResult:
    """Probabilistic operator attribution between two channels.

    Attributes:
        channel_a:  First channel identifier.
        channel_b:  Second channel identifier.
        probability_same_operator:  P(same_operator | evidence).
        confidence_interval:  90% CI around the probability.
        infrastructure_contribution:  log-odds contribution from entity overlap.
        behavioral_contribution:   log-odds contribution from behavioral similarity.
        temporal_contribution:   log-odds contribution from temporal proximity.
        content_contribution:   log-odds contribution from content similarity.
        interaction_contribution:  log-odds from infra x temporal interaction.
        primary_evidence:  Human-readable evidence strings.
        attribution_strength:  Categorical strength (DEFINITIVE -> INSUFFICIENT).
        raw_log_odds:  Raw log-odds score before sigmoid.
    """
    channel_a: str = ""
    channel_b: str = ""

    probability_same_operator: float = 0.0
    confidence_interval: Tuple[float, float] = (0.0, 0.0)

    infrastructure_contribution: float = 0.0
    behavioral_contribution: float = 0.0
    temporal_contribution: float = 0.0
    content_contribution: float = 0.0
    interaction_contribution: float = 0.0

    primary_evidence: List[str] = field(default_factory=list)
    attribution_strength: str = "INSUFFICIENT"

    raw_log_odds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["confidence_interval"] = list(self.confidence_interval)
        return d


# ---------------------------------------------------------------------------
# Attribution Engine
# ---------------------------------------------------------------------------

class AttributionEngine:
    """Log-linear operator attribution model.

    Computes the probability that two channels are operated by the
    same person or organization, based on four evidence streams:

    1. Infrastructure overlap (Jaccard similarity of entity sets)
    2. Behavioral similarity (cosine similarity of Tier 1+2 features)
    3. Temporal proximity (exponential decay from takedown to creation)
    4. Content similarity (cosine similarity of text features)
    5. Interaction: infrastructure x temporal (strongest combined signal)

    Coefficients are manually set with documented justification.
    They will be replaced by logistic regression on analyst decisions
    once sufficient feedback data exists (see feedback_store.py).

    Attributes:
        coefficients: Dict mapping coefficient name to value.
        prior: Prior log-odds (base rate for random channel pairs).
    """

    # Coefficient justification:
    #
    # b0 (prior) = -4.0
    #   Most random channel pairs are NOT same-operator.
    #   P(same_op) before evidence = sigmoid(-4.0) ~ 0.018.
    #   This is conservative -- we require evidence to move the needle.
    #
    # b1 (infrastructure) = 3.0
    #   Shared UPI/phone requires real-world resources (bank KYC, SIM card).
    #   Strongest independent signal.  Jaccard=1.0 shifts prior from
    #   0.018 to sigmoid(-4 + 3) = sigmoid(-1) ~ 0.27.  Still not
    #   definitive alone -- requires corroboration.
    #
    # b2 (behavioral) = 1.0
    #   Behavioral similarity is moderate evidence.  Can be gamed by
    #   sophisticated operators.  Low weight reflects this.
    #
    # b3 (temporal) = 2.0
    #   Channel B created within hours of Channel A being banned is
    #   strong evidence of migration.  But temporal proximity alone
    #   could be coincidence.
    #
    # b4 (content) = 0.5
    #   Many independent operators run similar scams.  Content
    #   similarity alone is very weak evidence of same-operator.
    #
    # b5 (interaction: infra x temporal) = 1.5
    #   Infrastructure overlap COMBINED with temporal proximity is
    #   the strongest signal: "same UPI AND created right after ban."
    #   This interaction makes the combined evidence much stronger
    #   than either alone.
    #
    DEFAULT_COEFFICIENTS = {
        "prior": -4.0,
        "infrastructure": 3.0,
        "behavioral": 1.0,
        "temporal": 2.0,
        "content": 0.5,
        "interaction_infra_temporal": 1.5,
    }

    # Infrastructure sub-weights (justified by cost of acquisition)
    # UPI requires bank account (KYC) -> highest weight
    # Phone requires SIM card -> high weight
    # Domain requires a few dollars -> moderate weight
    # Image can be copied by anyone -> lowest weight
    INFRA_WEIGHTS = {
        "upi": 0.40,
        "phone": 0.30,
        "domain": 0.20,
        "image": 0.10,
    }

    # Temporal decay constant (hours)
    # Captures: "Was channel B created within 48h of channel A being banned?"
    TEMPORAL_DECAY_HOURS = 48.0

    def __init__(
        self,
        coefficients: Optional[Dict[str, float]] = None,
    ):
        """Initialize the attribution engine.

        Args:
            coefficients: Override default coefficients (for learned models).
        """
        self.coefficients = dict(self.DEFAULT_COEFFICIENTS)
        if coefficients:
            self.coefficients.update(coefficients)

    # =====================================================================
    # Public API
    # =====================================================================

    def compute_attribution(
        self,
        assessment_a: ChannelAssessment,
        assessment_b: ChannelAssessment,
        takedown_time_a: Optional[str] = None,
        creation_time_b: Optional[str] = None,
    ) -> AttributionResult:
        """Compute P(same_operator) between two channels.

        Args:
            assessment_a:  Evidence assessment for channel A.
            assessment_b:  Evidence assessment for channel B.
            takedown_time_a:  ISO timestamp when A was taken down (optional).
            creation_time_b:  ISO timestamp when B was created (optional).

        Returns:
            AttributionResult with probability, decomposition, and explanation.
        """
        result = AttributionResult(
            channel_a=assessment_a.channel_id,
            channel_b=assessment_b.channel_id,
        )

        # Compute each evidence stream
        infra_score = self._infrastructure_overlap(
            assessment_a.infrastructure,
            assessment_b.infrastructure,
        )
        beh_score = self._behavioral_similarity(
            assessment_a.behavioral,
            assessment_b.behavioral,
        )
        temporal_score = self._temporal_proximity(
            takedown_time_a, creation_time_b,
        )
        content_score = self._content_similarity(
            assessment_a.content,
            assessment_b.content,
        )

        # Log-odds computation
        c = self.coefficients
        log_odds = (
            c["prior"]
            + c["infrastructure"] * infra_score
            + c["behavioral"] * beh_score
            + c["temporal"] * temporal_score
            + c["content"] * content_score
            + c["interaction_infra_temporal"] * (infra_score * temporal_score)
        )

        # Store contributions
        result.infrastructure_contribution = c["infrastructure"] * infra_score
        result.behavioral_contribution = c["behavioral"] * beh_score
        result.temporal_contribution = c["temporal"] * temporal_score
        result.content_contribution = c["content"] * content_score
        result.interaction_contribution = (
            c["interaction_infra_temporal"] * infra_score * temporal_score
        )
        result.raw_log_odds = log_odds

        # Sigmoid -> probability
        result.probability_same_operator = self._sigmoid(log_odds)

        # Confidence interval (approximate using logistic distribution variance)
        result.confidence_interval = self._approximate_ci(
            log_odds, n_evidence=len(assessment_a.all_evidence) + len(assessment_b.all_evidence),
        )

        # Strength classification
        result.attribution_strength = self._classify_strength(
            result.probability_same_operator
        )

        # Human-readable evidence
        result.primary_evidence = self._build_evidence_summary(
            assessment_a, assessment_b,
            infra_score, beh_score, temporal_score, content_score,
        )

        logger.info(
            "Attribution @%s <-> @%s: P=%.3f (%s) [infra=%.2f beh=%.2f temp=%.2f cont=%.2f]",
            result.channel_a, result.channel_b,
            result.probability_same_operator, result.attribution_strength,
            infra_score, beh_score, temporal_score, content_score,
        )

        return result

    def compute_all_pairs(
        self,
        assessments: List[ChannelAssessment],
        min_probability: float = 0.3,
    ) -> List[AttributionResult]:
        """Compute attribution for all channel pairs above threshold.

        Args:
            assessments:  List of ChannelAssessment objects.
            min_probability:  Only return pairs above this threshold.

        Returns:
            List of AttributionResult sorted by probability (descending).
        """
        results = []
        n = len(assessments)
        for i in range(n):
            for j in range(i + 1, n):
                result = self.compute_attribution(assessments[i], assessments[j])
                if result.probability_same_operator >= min_probability:
                    results.append(result)

        results.sort(key=lambda r: r.probability_same_operator, reverse=True)
        logger.info(
            "Attribution: %d pairs evaluated, %d above threshold %.2f",
            n * (n - 1) // 2, len(results), min_probability,
        )
        return results

    # =====================================================================
    # Evidence Stream Computations
    # =====================================================================

    def _infrastructure_overlap(
        self,
        infra_a: Any,
        infra_b: Any,
    ) -> float:
        """Weighted Jaccard overlap of infrastructure entities.

        Returns:
            Float in [0, 1].  0 = no overlap, 1 = complete overlap.
        """
        w = self.INFRA_WEIGHTS

        # Extract entity sets
        upis_a = set(infra_a.shared_upis.keys()) if infra_a.shared_upis else set()
        upis_b = set(infra_b.shared_upis.keys()) if infra_b.shared_upis else set()
        phones_a = set(infra_a.shared_phones.keys()) if infra_a.shared_phones else set()
        phones_b = set(infra_b.shared_phones.keys()) if infra_b.shared_phones else set()
        domains_a = set(infra_a.shared_domains.keys()) if infra_a.shared_domains else set()
        domains_b = set(infra_b.shared_domains.keys()) if infra_b.shared_domains else set()
        images_a = set(infra_a.shared_images.keys()) if infra_a.shared_images else set()
        images_b = set(infra_b.shared_images.keys()) if infra_b.shared_images else set()

        # Weighted Jaccard
        overlap = (
            w["upi"] * self._jaccard(upis_a, upis_b)
            + w["phone"] * self._jaccard(phones_a, phones_b)
            + w["domain"] * self._jaccard(domains_a, domains_b)
            + w["image"] * self._jaccard(images_a, images_b)
        )
        return overlap

    def _behavioral_similarity(
        self,
        beh_a: BehavioralEvidence,
        beh_b: BehavioralEvidence,
    ) -> float:
        """Cosine similarity of Tier 1 + Tier 2 features only.

        Tier 3 features are excluded because they are trivially
        manipulable and would allow adversarial evasion.

        Returns:
            Float in [0, 1].  0 = orthogonal, 1 = identical.
        """
        vec_a = beh_a.get_attribution_vector()
        vec_b = beh_b.get_attribution_vector()

        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0

        a = np.array(vec_a, dtype=np.float64)
        b = np.array(vec_b, dtype=np.float64)

        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a < 1e-10 or norm_b < 1e-10:
            return 0.0

        cosine = float(np.dot(a, b) / (norm_a * norm_b))
        # Map from [-1, 1] to [0, 1]
        return (cosine + 1.0) / 2.0

    def _temporal_proximity(
        self,
        takedown_time_a: Optional[str],
        creation_time_b: Optional[str],
    ) -> float:
        """Exponential decay of time between takedown(A) and creation(B).

        Returns:
            Float in [0, 1].  1 = created immediately after ban.
            0 = no temporal data or large gap.
        """
        if not takedown_time_a or not creation_time_b:
            return 0.0  # No temporal data -> contributes nothing

        try:
            from datetime import datetime
            ta = datetime.fromisoformat(takedown_time_a.replace("Z", "+00:00"))
            tb = datetime.fromisoformat(creation_time_b.replace("Z", "+00:00"))
            gap_hours = abs((tb - ta).total_seconds()) / 3600.0
            return math.exp(-gap_hours / self.TEMPORAL_DECAY_HOURS)
        except Exception:
            return 0.0

    def _content_similarity(
        self,
        content_a: Any,
        content_b: Any,
    ) -> float:
        """Content similarity based on category and pattern overlap.

        Returns:
            Float in [0, 1].
        """
        score = 0.0

        # Same scam category (weak signal -- many independent operators
        # run the same type of scam)
        if (content_a.scam_category != "UNKNOWN" and
                content_a.scam_category == content_b.scam_category):
            score += 0.4

        # Both impersonate the same entity (moderate signal)
        if (content_a.impersonated_entity and
                content_a.impersonated_entity == content_b.impersonated_entity):
            score += 0.4

        # Both contain financial promises (weak)
        if content_a.contains_financial_promises and content_b.contains_financial_promises:
            score += 0.2

        return min(score, 1.0)

    # =====================================================================
    # Helpers
    # =====================================================================

    @staticmethod
    def _jaccard(set_a: Set, set_b: Set) -> float:
        """Jaccard similarity coefficient."""
        if not set_a and not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _sigmoid(x: float) -> float:
        """Numerically stable sigmoid."""
        if x >= 0:
            return 1.0 / (1.0 + math.exp(-x))
        else:
            ex = math.exp(x)
            return ex / (1.0 + ex)

    @staticmethod
    def _approximate_ci(
        log_odds: float,
        n_evidence: int,
        confidence_level: float = 0.90,
    ) -> Tuple[float, float]:
        """Approximate confidence interval for the probability.

        Uses the logistic distribution's variance scaled by evidence
        count.  More evidence -> tighter CI.

        This is a rough approximation.  Proper CIs require
        bootstrapping or Bayesian posterior, which we'll add
        when calibration data exists.
        """
        # Standard error decreases with evidence count
        se = math.pi / (math.sqrt(3) * max(math.sqrt(n_evidence), 1.0))

        # z-score for 90% CI
        z = 1.645

        lo = AttributionEngine._sigmoid(log_odds - z * se)
        hi = AttributionEngine._sigmoid(log_odds + z * se)
        return (round(lo, 4), round(hi, 4))

    @staticmethod
    def _classify_strength(probability: float) -> str:
        """Classify attribution strength from probability."""
        if probability >= 0.95:
            return "DEFINITIVE"
        if probability >= 0.80:
            return "STRONG"
        if probability >= 0.60:
            return "PROBABLE"
        if probability >= 0.40:
            return "POSSIBLE"
        return "INSUFFICIENT"

    def _build_evidence_summary(
        self,
        assess_a: ChannelAssessment,
        assess_b: ChannelAssessment,
        infra: float,
        beh: float,
        temp: float,
        cont: float,
    ) -> List[str]:
        """Build human-readable evidence summary."""
        evidence = []

        if infra > 0.01:
            # Find specific shared entities
            shared_upis = (
                set(assess_a.infrastructure.shared_upis.keys()) &
                set(assess_b.infrastructure.shared_upis.keys())
            )
            shared_phones = (
                set(assess_a.infrastructure.shared_phones.keys()) &
                set(assess_b.infrastructure.shared_phones.keys())
            )
            if shared_upis:
                evidence.append(
                    f"Shared UPI ID(s): {', '.join(list(shared_upis)[:3])}"
                )
            if shared_phones:
                evidence.append(
                    f"Shared phone(s): {', '.join(list(shared_phones)[:3])}"
                )
            if not shared_upis and not shared_phones:
                evidence.append(f"Infrastructure overlap: {infra:.2f}")

        if beh > 0.7:
            evidence.append(f"High behavioral similarity: {beh:.2f}")
        elif beh > 0.5:
            evidence.append(f"Moderate behavioral similarity: {beh:.2f}")

        if temp > 0.5:
            evidence.append(f"Temporal proximity: {temp:.2f} (possible migration)")

        if cont > 0.5:
            evidence.append(f"Content similarity: {cont:.2f}")

        if not evidence:
            evidence.append("No significant evidence of common operation")

        return evidence
