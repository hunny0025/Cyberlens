"""
CyberLens -- Recommendation Engine
=======================================
Produces defensible, evidence-based enforcement recommendations
with mandatory suppression rules for false positive prevention.

This replaces the old DecisionScoringEngine entirely.

Key design principles:
    1. Recommendations are CONDITIONAL on evidence strength and confidence.
    2. Suppression rules are as important as detection rules.
    3. Every recommendation carries human-readable justification + caveats.
    4. No "magic numbers" -- every threshold is justified and documented.

Action taxonomy (replaces BLOCK/ESCALATE/MONITOR/IGNORE):
    TAKEDOWN_REQUEST      -- DEFINITIVE evidence + HIGH confidence
    PRIORITY_INVESTIGATION -- STRONG evidence + MODERATE+ confidence
    ANALYST_REVIEW        -- MODERATE evidence, needs human judgment
    AUTOMATED_MONITORING  -- WEAK/CIRCUMSTANTIAL evidence
    NO_ACTION             -- No threat evidence or insufficient data
    SUPPRESSED            -- Evidence exists but confidence too low

Author: CyberLens Team
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.intelligence.confidence_engine import ConfidenceAssessment, ConfidenceEngine
from src.intelligence.evidence_collector import EvidenceCollector
from src.intelligence.evidence_model import (
    ChannelAssessment,
    EvidenceItem,
    EvidenceStrength,
)

logger = logging.getLogger("cyberlens.intelligence.recommendation")


# ---------------------------------------------------------------------------
# IT Act / BNS Section Mapping
# ---------------------------------------------------------------------------

IT_ACT_SECTIONS = {
    "INVESTMENT_SCAM": [
        "IT Act S.66D -- Cheating by personation using computer resource",
        "BNS S.318 -- Cheating and dishonestly inducing delivery of property",
        "SEBI Act S.12A -- Prohibition of fraudulent and unfair trade practices",
    ],
    "BETTING_SCAM": [
        "IT Act S.67 -- Publishing or transmitting obscene material",
        "Public Gambling Act S.3 -- Running a gaming house",
    ],
    "DIGITAL_ARREST": [
        "BNS S.204 -- Personating a public servant",
        "IT Act S.66D -- Cheating by personation",
        "BNS S.308 -- Extortion",
    ],
    "IMPERSONATION": [
        "IT Act S.66C -- Identity theft",
        "IT Act S.66D -- Cheating by personation",
    ],
    "JOB_SCAM": [
        "IT Act S.66D -- Cheating by personation",
        "BNS S.318 -- Cheating",
    ],
    "LOTTERY_SCAM": [
        "IT Act S.66D -- Cheating by personation",
        "BNS S.318 -- Cheating",
        "Lotteries (Regulation) Act S.3 -- Prohibition",
    ],
    "LOAN_SCAM": [
        "IT Act S.66D -- Cheating by personation",
        "RBI Directions on Digital Lending",
    ],
    "UNKNOWN": [
        "IT Act S.66 -- Computer-related offences (general)",
    ],
}


# ---------------------------------------------------------------------------
# Recommendation data class
# ---------------------------------------------------------------------------

@dataclass
class Recommendation:
    """Defensible, evidence-based enforcement recommendation.

    Every recommendation is traceable to specific evidence items,
    carries confidence assessment, lists caveats, and specifies
    analyst instructions.

    Attributes:
        channel_id:  Channel identifier.
        channel_name:  Human-readable name.
        action:  Recommended enforcement action.
        urgency:  Time sensitivity (IMMEDIATE, 24_HOURS, ROUTINE, DEFERRED).
        primary_justification:  One-sentence human-readable reason.
        supporting_evidence:  List of evidence items backing this recommendation.
        evidence_strength:  Highest evidence strength.
        recommendation_confidence:  How confident is this recommendation.
        applicable_sections:  IT Act / BNS sections.
        analyst_instructions:  Specific next steps for the analyst.
        caveats:  What the system is uncertain about.
        suppressed:  True if recommendation withheld due to low confidence.
        suppression_reason:  Why it was suppressed.
        generated_at:  ISO-8601 timestamp.
    """
    channel_id: str = ""
    channel_name: str = ""

    action: str = "NO_ACTION"
    urgency: str = "DEFERRED"

    primary_justification: str = ""
    supporting_evidence: List[Dict] = field(default_factory=list)
    evidence_strength: str = "CIRCUMSTANTIAL"

    recommendation_confidence: str = "LOW"
    applicable_sections: List[str] = field(default_factory=list)
    analyst_instructions: str = ""
    caveats: List[str] = field(default_factory=list)

    suppressed: bool = False
    suppression_reason: str = ""

    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


# ---------------------------------------------------------------------------
# Recommendation Engine
# ---------------------------------------------------------------------------

class RecommendationEngine:
    """Evidence-conditional recommendation engine.

    Replaces the old DecisionScoringEngine with a defensible
    framework where recommendations are determined by evidence
    strength and confidence, not by thresholds on continuous scores.

    Suppression rules prevent false positives by withholding
    recommendations when confidence is insufficient.

    Attributes:
        evidence_collector: Collects structured evidence.
        confidence_engine: Computes assessment confidence.
    """

    def __init__(
        self,
        i4c_ground_truth_path: str = "data/ground_truth/i4c_advisories.json",
        certin_ground_truth_path: str = "data/ground_truth/certin_alerts.json",
    ):
        self.evidence_collector = EvidenceCollector(
            i4c_ground_truth_path=i4c_ground_truth_path,
            certin_ground_truth_path=certin_ground_truth_path,
        )
        self.confidence_engine = ConfidenceEngine()

    # =====================================================================
    # Public API
    # =====================================================================

    def recommend(
        self,
        channel_data: Dict[str, Any],
        all_channels: Optional[List[Dict[str, Any]]] = None,
    ) -> Recommendation:
        """Generate a recommendation for a single channel.

        Pipeline:
            1. Collect evidence (infrastructure, behavioral, content)
            2. Compute confidence
            3. Determine action from evidence strength + confidence
            4. Apply suppression rules
            5. Generate analyst instructions and caveats

        Args:
            channel_data:  Channel dataset dict.
            all_channels:  All channels for cross-reference.

        Returns:
            Recommendation with full evidence chain and caveats.
        """
        # Step 1: Collect evidence
        assessment = self.evidence_collector.assess_channel(
            channel_data, all_channels,
        )

        # Step 2: Compute confidence
        confidence = self.confidence_engine.compute(assessment, channel_data)

        # Step 3: Determine action
        rec = self._determine_action(assessment, confidence)

        # Step 4: Apply suppression rules
        suppressed, reason = self._should_suppress(
            assessment.all_evidence, confidence, rec.action,
        )
        if suppressed:
            original_action = rec.action
            rec.suppressed = True
            rec.suppression_reason = reason
            rec.action = "SUPPRESSED"
            rec.urgency = "DEFERRED"
            rec.caveats.append(
                f"Original recommendation ({original_action}) suppressed: {reason}"
            )

        # Step 5: Map legal sections
        rec.applicable_sections = IT_ACT_SECTIONS.get(
            assessment.content.scam_category, IT_ACT_SECTIONS["UNKNOWN"]
        )

        # Step 6: Generate analyst instructions
        rec.analyst_instructions = self._generate_instructions(rec, assessment)

        logger.info(
            "Recommendation for @%s: %s (%s) [strength=%s confidence=%s%s]",
            rec.channel_name, rec.action, rec.urgency,
            rec.evidence_strength, rec.recommendation_confidence,
            " SUPPRESSED" if rec.suppressed else "",
        )

        return rec

    def recommend_batch(
        self,
        channels: List[Dict[str, Any]],
    ) -> List[Recommendation]:
        """Generate recommendations for multiple channels.

        Cross-references entities across all channels for
        entity sharing detection.

        Args:
            channels:  List of channel dataset dicts.

        Returns:
            List of Recommendation sorted by urgency/strength.
        """
        results = [self.recommend(ch, channels) for ch in channels]

        # Sort: non-suppressed first, then by urgency
        urgency_order = {
            "IMMEDIATE": 0, "24_HOURS": 1, "ROUTINE": 2, "DEFERRED": 3,
        }
        results.sort(key=lambda r: (
            r.suppressed,
            urgency_order.get(r.urgency, 99),
        ))

        # Summary log
        action_counts = {}
        for r in results:
            action_counts[r.action] = action_counts.get(r.action, 0) + 1
        logger.info(
            "Batch recommendations: %d channels -> %s",
            len(channels),
            ", ".join(f"{k}={v}" for k, v in sorted(action_counts.items())),
        )

        return results

    # =====================================================================
    # Action Determination (Evidence-Conditional)
    # =====================================================================

    def _determine_action(
        self,
        assessment: ChannelAssessment,
        confidence: ConfidenceAssessment,
    ) -> Recommendation:
        """Determine action from evidence strength + confidence.

        NOT threshold-based.  Uses categorical rules:
        - TAKEDOWN requires DEFINITIVE evidence + HIGH confidence
        - PRIORITY requires STRONG evidence + MODERATE+ confidence
        - etc.
        """
        rec = Recommendation(
            channel_id=assessment.channel_id,
            channel_name=assessment.channel_name,
        )

        evidence = assessment.all_evidence
        strength = assessment.overall_strength

        # Build evidence list for output
        rec.supporting_evidence = [e.to_dict() for e in evidence[:20]]
        rec.evidence_strength = strength.value
        rec.recommendation_confidence = confidence.confidence_class

        # Primary justification = strongest evidence item
        if evidence:
            strongest = max(evidence, key=lambda e: EvidenceStrength(e.strength).numeric_rank)
            rec.primary_justification = strongest.details or f"{strongest.evidence_type}: {strongest.value}"
        else:
            rec.primary_justification = "No significant evidence found"

        # -- Decision rules ------------------------------------------------

        # TAKEDOWN: DEFINITIVE evidence + HIGH confidence
        if strength == EvidenceStrength.DEFINITIVE and confidence.confidence_class == "HIGH":
            rec.action = "TAKEDOWN_REQUEST"
            rec.urgency = "IMMEDIATE"
            return rec

        # TAKEDOWN: DEFINITIVE evidence + MODERATE confidence (with caveat)
        if strength == EvidenceStrength.DEFINITIVE and confidence.confidence_class == "MODERATE":
            rec.action = "TAKEDOWN_REQUEST"
            rec.urgency = "24_HOURS"
            rec.caveats.append(
                "Confidence is MODERATE. Verify blocklist match manually before proceeding."
            )
            return rec

        # PRIORITY: STRONG evidence + MODERATE+ confidence
        if strength >= EvidenceStrength.STRONG and confidence.confidence_class in ("HIGH", "MODERATE"):
            rec.action = "PRIORITY_INVESTIGATION"
            rec.urgency = "24_HOURS"
            return rec

        # ANALYST_REVIEW: MODERATE evidence
        if strength >= EvidenceStrength.MODERATE:
            rec.action = "ANALYST_REVIEW"
            rec.urgency = "ROUTINE"
            rec.caveats.append(
                "Evidence is MODERATE. Human review required before escalation."
            )
            return rec

        # MONITORING: WEAK evidence
        if strength >= EvidenceStrength.WEAK:
            rec.action = "AUTOMATED_MONITORING"
            rec.urgency = "DEFERRED"
            rec.caveats.append(
                "Evidence is WEAK. Added to automated monitoring queue. "
                "Re-evaluate in 72 hours."
            )
            return rec

        # NO_ACTION: CIRCUMSTANTIAL only or no evidence
        rec.action = "NO_ACTION"
        rec.urgency = "DEFERRED"
        return rec

    # =====================================================================
    # Suppression Logic (Critical for False Positive Prevention)
    # =====================================================================

    def _should_suppress(
        self,
        evidence: List[EvidenceItem],
        confidence: ConfidenceAssessment,
        proposed_action: str,
    ) -> Tuple[bool, str]:
        """Determine if a recommendation should be suppressed.

        Suppression prevents false positives by withholding
        recommendations when conditions are not met.

        This is the most important safety mechanism in the system.

        Args:
            evidence:  All evidence items.
            confidence:  Confidence assessment.
            proposed_action:  The action that would be recommended.

        Returns:
            Tuple of (should_suppress, reason).
        """
        # Rule 1: Never TAKEDOWN with less than MODERATE confidence
        if proposed_action == "TAKEDOWN_REQUEST" and confidence.confidence_class in ("LOW", "INSUFFICIENT"):
            return True, (
                f"TAKEDOWN requires at least MODERATE confidence. "
                f"Current: {confidence.confidence_class} ({confidence.overall_confidence:.2f}). "
                f"Gather more data before requesting takedown."
            )

        # Rule 2: Never act on purely CIRCUMSTANTIAL evidence
        if evidence and all(e.strength == EvidenceStrength.CIRCUMSTANTIAL.value for e in evidence):
            if proposed_action not in ("NO_ACTION", "AUTOMATED_MONITORING"):
                return True, (
                    "All evidence is CIRCUMSTANTIAL (pattern matches only, no specific entities). "
                    "Insufficient for enforcement action."
                )

        # Rule 3: Single-source PRIORITY or TAKEDOWN requires corroboration
        if confidence.source_count < 2 and proposed_action in ("TAKEDOWN_REQUEST", "PRIORITY_INVESTIGATION"):
            return True, (
                f"Only {confidence.source_count} evidence source(s). "
                f"TAKEDOWN and PRIORITY require at least 2 independent sources. "
                f"Gather corroborating evidence."
            )

        # Rule 4: Insufficient data completeness
        if confidence.data_completeness < 0.4 and proposed_action not in ("NO_ACTION", "AUTOMATED_MONITORING"):
            return True, (
                f"Data completeness is {confidence.data_completeness:.0%}. "
                f"Minimum 40% required for enforcement recommendations. "
                f"Continue data collection."
            )

        # Rule 5: Very few posts analyzed
        if confidence.post_count_observed < 5 and proposed_action not in ("NO_ACTION", "AUTOMATED_MONITORING"):
            return True, (
                f"Only {confidence.post_count_observed} posts analyzed. "
                f"Minimum 5 posts required for any enforcement recommendation."
            )

        return False, ""

    # =====================================================================
    # Analyst Instructions
    # =====================================================================

    def _generate_instructions(
        self,
        rec: Recommendation,
        assessment: ChannelAssessment,
    ) -> str:
        """Generate specific analyst instructions based on the recommendation."""
        if rec.action == "TAKEDOWN_REQUEST":
            entities = []
            for item in assessment.infrastructure.blocklist_matches[:3]:
                entities.append(item.value)
            entity_str = ", ".join(entities) if entities else "see evidence chain"
            return (
                f"IMMEDIATE ACTION REQUIRED:\n"
                f"1. Verify blocklist match for: {entity_str}\n"
                f"2. Prepare IT Act S.69A blocking request for I4C\n"
                f"3. Notify platform (Telegram) for content takedown\n"
                f"4. Preserve all evidence (screenshots, entity list, graph)\n"
                f"5. Cross-reference with NCRP complaint database"
            )

        if rec.action == "PRIORITY_INVESTIGATION":
            return (
                f"PRIORITY (24-hour response):\n"
                f"1. Assign to senior analyst for review\n"
                f"2. Verify shared entities across linked channels\n"
                f"3. Cross-reference UPI/phone with NPCI/telecom records\n"
                f"4. Check for related NCRP complaints\n"
                f"5. If confirmed, escalate to TAKEDOWN_REQUEST"
            )

        if rec.action == "ANALYST_REVIEW":
            return (
                f"ROUTINE REVIEW:\n"
                f"1. Review evidence chain and verify key entities\n"
                f"2. Check if channel is legitimately impersonating or actually official\n"
                f"3. Monitor for 48-72 hours for additional evidence\n"
                f"4. If evidence strengthens, escalate to PRIORITY"
            )

        if rec.action == "AUTOMATED_MONITORING":
            return (
                f"NO MANUAL ACTION NEEDED:\n"
                f"1. Added to automated monitoring queue\n"
                f"2. System will re-evaluate in 72 hours\n"
                f"3. Alert will trigger if evidence strengthens"
            )

        if rec.action == "SUPPRESSED":
            return (
                f"RECOMMENDATION WITHHELD:\n"
                f"1. {rec.suppression_reason}\n"
                f"2. Continue automated data collection\n"
                f"3. System will re-evaluate when more data is available"
            )

        return "No action required."

    # =====================================================================
    # Utility: Save results
    # =====================================================================

    def save_recommendations(
        self,
        recommendations: List[Recommendation],
        output_path: str = "reports/recommendations/latest.json",
    ) -> None:
        """Save recommendations to JSON file.

        Args:
            recommendations:  List of Recommendation objects.
            output_path:  File path for output.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_channels": len(recommendations),
            "action_summary": {},
            "recommendations": [],
        }

        for rec in recommendations:
            report["recommendations"].append(rec.to_dict())
            report["action_summary"][rec.action] = (
                report["action_summary"].get(rec.action, 0) + 1
            )

        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info("Recommendations saved -> %s", path)
