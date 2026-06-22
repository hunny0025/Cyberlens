"""
CyberLens — Composite Decision Scoring Engine
=================================================
Combines outputs from all model layers into a unified
risk score with law enforcement action recommendations.

Score components:
    - Infrastructure (30%): I4C match, CERT-In match, domain, UPI, phone
    - Network (25%): Neo4j connections, operator attribution, campaign clusters
    - Behavioral (25%): Fingerprint match, rapid growth, urgency density
    - Content (20%): Classifier confidence, QR-UPI link, OCR phone match

Decision classes:
    IGNORE      (<30)  → No action needed
    MONITOR     (30-50) → Add to watchlist
    INVESTIGATE (50-70) → Assign to analyst
    ESCALATE    (70-85) → Priority case
    BLOCK       (>85)  → Immediate takedown request

Author: CyberLens Team — GPCSSI Internship
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cyberlens.decision")


# ---------------------------------------------------------------------------
# IT Act sections by severity
# ---------------------------------------------------------------------------

IT_ACT_SECTIONS = {
    "BLOCK": [
        "IT Act §69A — Government blocking orders",
        "IT Act §66D — Cheating by personation using computer resource",
        "BNS §318 — Cheating",
        "IT Act §67B — CSAM provisions (if applicable)",
    ],
    "ESCALATE": [
        "IT Act §66D — Cheating by personation",
        "IT Act §66C — Identity theft",
        "BNS §318 — Cheating",
    ],
    "INVESTIGATE": [
        "IT Act §66 — Computer related offences",
        "IT Act §43 — Penalty for unauthorized access",
    ],
    "MONITOR": [
        "IT Act §66 — Computer related offences",
    ],
    "IGNORE": [],
}

ACTION_RECOMMENDATIONS = {
    "BLOCK": "IMMEDIATE: File blocking request with I4C under IT Act §69A. Notify platform for takedown. Preserve evidence chain.",
    "ESCALATE": "PRIORITY: Assign senior analyst. Cross-reference with NCRP complaints. Prepare preliminary FIR draft.",
    "INVESTIGATE": "STANDARD: Assign to analyst queue. Gather additional evidence. Cross-reference entity databases.",
    "MONITOR": "PASSIVE: Add to automated monitoring. Alert if activity escalates. Re-evaluate in 72 hours.",
    "IGNORE": "NO ACTION: Below threshold. Channel may be legitimate or inactive.",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ScoreComponent:
    """A single component of the composite risk score."""
    name: str
    score: float  # 0-100
    weight: float  # 0-1
    weighted_score: float = 0.0
    signals: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.weighted_score = round(self.score * self.weight, 2)


@dataclass
class DecisionScore:
    """Composite decision output for a channel or entity."""

    # Component scores
    infrastructure_score: float = 0.0
    network_score: float = 0.0
    behavioral_score: float = 0.0
    content_score: float = 0.0

    # Composite
    composite_score: float = 0.0
    decision: str = "IGNORE"

    # Evidence chain
    evidence_chain: List[str] = field(default_factory=list)
    it_act_sections: List[str] = field(default_factory=list)
    recommended_action: str = ""

    # Component details
    components: List[Dict] = field(default_factory=list)

    # Metadata
    channel_name: str = ""
    scored_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Decision Scoring Engine
# ---------------------------------------------------------------------------

class DecisionScoringEngine:
    """Composite risk scoring engine for threat decision-making.

    Combines infrastructure, network, behavioral, and content signals
    into a unified 0-100 risk score with law enforcement action mapping.

    Weights:
        - Infrastructure: 0.30
        - Network: 0.25
        - Behavioral: 0.25
        - Content: 0.20

    Attributes:
        weights: Component weight dict.
        thresholds: Decision boundary thresholds.
    """

    # Component weights
    WEIGHTS = {
        "infrastructure": 0.30,
        "network": 0.25,
        "behavioral": 0.25,
        "content": 0.20,
    }

    # Decision thresholds
    THRESHOLDS = {
        "BLOCK": 85,
        "ESCALATE": 70,
        "INVESTIGATE": 50,
        "MONITOR": 30,
        "IGNORE": 0,
    }

    def __init__(
        self,
        i4c_ground_truth_path: str = "data/ground_truth/i4c_advisories.json",
        certin_ground_truth_path: str = "data/ground_truth/certin_alerts.json",
    ):
        """Initialize the scoring engine.

        Args:
            i4c_ground_truth_path: Path to I4C advisories JSON.
            certin_ground_truth_path: Path to CERT-In alerts JSON.
        """
        self._blocked_domains: set = set()
        self._blocked_urls: set = set()
        self._blocked_channels: set = set()
        self._malicious_ips: set = set()

        # Load ground truth
        self._load_ground_truth(
            Path(i4c_ground_truth_path),
            Path(certin_ground_truth_path),
        )

    def _load_ground_truth(self, i4c_path: Path, certin_path: Path) -> None:
        """Load confirmed blocked entities from ground truth files."""
        if i4c_path.exists():
            try:
                with open(i4c_path, "r", encoding="utf-8") as f:
                    for adv in json.load(f):
                        self._blocked_domains.update(adv.get("blocked_domains", []))
                        self._blocked_urls.update(adv.get("blocked_urls", []))
                        self._blocked_channels.update(adv.get("blocked_channels", []))
                logger.info("Loaded I4C ground truth: %d domains, %d channels",
                            len(self._blocked_domains), len(self._blocked_channels))
            except Exception as e:
                logger.debug("Could not load I4C ground truth: %s", e)

        if certin_path.exists():
            try:
                with open(certin_path, "r", encoding="utf-8") as f:
                    for alert in json.load(f):
                        self._blocked_domains.update(alert.get("domains", []))
                        self._malicious_ips.update(alert.get("ips", []))
                logger.info("Loaded CERT-In ground truth: %d domains, %d IPs",
                            len(self._blocked_domains), len(self._malicious_ips))
            except Exception as e:
                logger.debug("Could not load CERT-In ground truth: %s", e)

    def score(
        self,
        channel_data: Dict[str, Any],
        classifier_result: Optional[Dict] = None,
        fingerprint_result: Optional[Dict] = None,
        neo4j_data: Optional[Dict] = None,
    ) -> DecisionScore:
        """Compute composite risk score for a channel.

        Args:
            channel_data: Channel dataset dict with entities, metadata, etc.
            classifier_result: Scam classifier output (category, confidence).
            fingerprint_result: Behavioral fingerprint match results.
            neo4j_data: Neo4j graph connections data.

        Returns:
            DecisionScore with full breakdown.
        """
        from datetime import datetime, timezone

        result = DecisionScore(
            channel_name=channel_data.get("channel_metadata", {}).get("username", "unknown"),
            scored_at=datetime.now(timezone.utc).isoformat(),
        )

        # Compute each component
        infra = self._score_infrastructure(channel_data)
        network = self._score_network(channel_data, neo4j_data)
        behavioral = self._score_behavioral(channel_data, fingerprint_result)
        content = self._score_content(channel_data, classifier_result)

        result.infrastructure_score = infra.score
        result.network_score = network.score
        result.behavioral_score = behavioral.score
        result.content_score = content.score

        # Composite weighted sum
        result.composite_score = round(
            infra.weighted_score +
            network.weighted_score +
            behavioral.weighted_score +
            content.weighted_score,
            2,
        )
        result.composite_score = min(100, max(0, result.composite_score))

        # Decision classification
        result.decision = self._classify_decision(result.composite_score)

        # Evidence chain
        evidence = []
        evidence.extend(infra.signals)
        evidence.extend(network.signals)
        evidence.extend(behavioral.signals)
        evidence.extend(content.signals)
        result.evidence_chain = evidence

        # IT Act sections and action
        result.it_act_sections = IT_ACT_SECTIONS.get(result.decision, [])
        result.recommended_action = ACTION_RECOMMENDATIONS.get(result.decision, "")

        # Component details
        result.components = [
            asdict(infra), asdict(network),
            asdict(behavioral), asdict(content),
        ]

        logger.info(
            "Decision for @%s: score=%.1f -> %s (infra=%.0f net=%.0f beh=%.0f cont=%.0f)",
            result.channel_name, result.composite_score, result.decision,
            infra.score, network.score, behavioral.score, content.score,
        )

        return result

    # ── Component scoring methods ────────────────────────────────

    def _score_infrastructure(
        self, channel_data: Dict
    ) -> ScoreComponent:
        """Score infrastructure signals (0-100).

        Signals:
            - I4C blocked entity match (40 points)
            - CERT-In domain/IP match (25 points)
            - UPI cross-reference (15 points)
            - Phone cross-reference (10 points)
            - Suspicious domain patterns (10 points)
        """
        score = 0.0
        signals = []
        entities = channel_data.get("entities_found", {})
        xref = channel_data.get("cross_reference", {})

        # I4C match
        if xref.get("matched_blocked_urls") or xref.get("matched_blocked_channels"):
            i4c_match_count = len(xref.get("matched_blocked_urls", [])) + \
                              len(xref.get("matched_blocked_channels", []))
            score += min(40, i4c_match_count * 20)
            signals.append(f"I4C blocked entity match: {i4c_match_count} hits")

        # Domain check against ground truth
        for url in entities.get("urls", []):
            for domain in self._blocked_domains:
                if domain in url:
                    score += 25
                    signals.append(f"CERT-In/I4C domain match: {domain}")
                    break
            if score >= 65:
                break

        # UPI entity count (more UPIs = more suspicious in scam context)
        upi_count = len(entities.get("upis", []))
        if upi_count > 0:
            score += min(15, upi_count * 5)
            signals.append(f"UPI IDs found: {upi_count}")

        # Phone entity count
        phone_count = len(entities.get("phones", []))
        if phone_count > 2:
            score += min(10, phone_count * 3)
            signals.append(f"Phone numbers found: {phone_count}")

        # Suspicious domain patterns
        for url in entities.get("urls", [])[:10]:
            if any(sus in url.lower() for sus in [".xyz", ".online", ".site", ".top", ".club"]):
                score += 10
                signals.append(f"Suspicious TLD in URL: {url[:50]}")
                break

        return ScoreComponent(
            name="infrastructure",
            score=min(100, score),
            weight=self.WEIGHTS["infrastructure"],
            signals=signals,
        )

    def _score_network(
        self, channel_data: Dict, neo4j_data: Optional[Dict]
    ) -> ScoreComponent:
        """Score network behavior signals (0-100)."""
        score = 0.0
        signals = []

        # Linked channels count
        linked = channel_data.get("linked_channels", [])
        if len(linked) > 5:
            score += min(30, len(linked) * 3)
            signals.append(f"Cross-linked to {len(linked)} channels")

        # Forward ratio (high forwards = network distribution)
        fwd_ratio = channel_data.get("forward_ratio", 0)
        if fwd_ratio > 0.3:
            score += 20
            signals.append(f"High forward ratio: {fwd_ratio:.2f}")

        # Neo4j connections (if available)
        if neo4j_data:
            connections = neo4j_data.get("total_connections", 0)
            campaigns = neo4j_data.get("campaign_count", 0)
            if connections > 10:
                score += min(25, connections * 2)
                signals.append(f"Neo4j: {connections} entity connections")
            if campaigns > 0:
                score += min(15, campaigns * 5)
                signals.append(f"Linked to {campaigns} known campaigns")

        # Entity overlap (shared UPIs/phones with other channels)
        entity_overlap = channel_data.get("cross_reference", {}).get("blocked_entity_count", 0)
        if entity_overlap > 0:
            score += min(20, entity_overlap * 10)
            signals.append(f"Entity overlap with blocked channels: {entity_overlap}")

        return ScoreComponent(
            name="network",
            score=min(100, score),
            weight=self.WEIGHTS["network"],
            signals=signals,
        )

    def _score_behavioral(
        self, channel_data: Dict, fingerprint_result: Optional[Dict]
    ) -> ScoreComponent:
        """Score behavioral signals (0-100)."""
        score = 0.0
        signals = []

        # Fingerprint match to known scam patterns
        if fingerprint_result:
            similarity = fingerprint_result.get("similarity_score", 0)
            if similarity > 0.8:
                score += 40
                signals.append(f"Behavioral fingerprint match: {similarity:.2f}")
            elif similarity > 0.6:
                score += 20
                signals.append(f"Moderate fingerprint similarity: {similarity:.2f}")

        # Rapid growth (suspicious if very fast)
        growth_snapshots = channel_data.get("growth_snapshots", [])
        if growth_snapshots:
            latest_subs = growth_snapshots[-1].get("subscribers", 0)
            if latest_subs > 10000:
                score += 10
                signals.append(f"Large channel: {latest_subs:,} subscribers")

        # Urgency density
        # Extract from posts if available
        posts = channel_data.get("posts", [])
        if posts:
            urgency_keywords = [
                "urgent", "limited", "hurry", "last chance", "act now",
                "guaranteed", "जल्दी", "तुरंत", "अभी",
            ]
            urgency_count = 0
            for post in posts[:100]:
                text = post.get("text", "").lower()
                if any(kw in text for kw in urgency_keywords):
                    urgency_count += 1

            urgency_pct = urgency_count / max(len(posts[:100]), 1) * 100
            if urgency_pct > 30:
                score += 25
                signals.append(f"High urgency density: {urgency_pct:.1f}%")
            elif urgency_pct > 10:
                score += 10
                signals.append(f"Moderate urgency density: {urgency_pct:.1f}%")

        # Backup channel mentions
        backup_count = sum(
            1 for p in posts[:100]
            if any(kw in p.get("text", "").lower()
                   for kw in ["backup", "new channel", "moved to", "बैकअप"])
        )
        if backup_count > 0:
            score += 15
            signals.append(f"Backup channel mentions: {backup_count}")

        # High deletion rate (estimated)
        message_ids = sorted(p.get("message_id", 0) for p in posts if p.get("message_id"))
        if len(message_ids) >= 2:
            expected = message_ids[-1] - message_ids[0] + 1
            actual = len(message_ids)
            deletion_rate = 1.0 - (actual / max(expected, 1))
            if deletion_rate > 0.3:
                score += 10
                signals.append(f"High deletion rate: {deletion_rate:.1%}")

        return ScoreComponent(
            name="behavioral",
            score=min(100, score),
            weight=self.WEIGHTS["behavioral"],
            signals=signals,
        )

    def _score_content(
        self, channel_data: Dict, classifier_result: Optional[Dict]
    ) -> ScoreComponent:
        """Score content signals (0-100)."""
        score = 0.0
        signals = []

        # Classifier confidence
        if classifier_result:
            confidence = classifier_result.get("confidence", 0)
            category = classifier_result.get("category", "unknown")
            if confidence > 0.8:
                score += 50
                signals.append(f"Classifier: {category} ({confidence:.1%} confidence)")
            elif confidence > 0.5:
                score += 25
                signals.append(f"Classifier: {category} ({confidence:.1%} confidence)")

        # QR + UPI link (common scam pattern)
        entities = channel_data.get("entities_found", {})
        has_qr = len(entities.get("qr_mentions", [])) > 0
        has_upi = len(entities.get("upis", [])) > 0
        if has_qr and has_upi:
            score += 20
            signals.append("QR code + UPI ID combination detected")

        # High media ratio with UPI (visual scam pattern)
        media_ratio = channel_data.get("media_ratio", {})
        image_pct = media_ratio.get("images", 0)
        if image_pct > 50 and has_upi:
            score += 15
            signals.append(f"High image ratio ({image_pct:.0f}%) with UPI IDs")

        # Language signals (mixed Hindi-English common in Indian scams)
        lang_dist = channel_data.get("language_distribution", {})
        hinglish = lang_dist.get("hinglish", 0)
        if hinglish > 0.3:
            score += 10
            signals.append(f"High Hinglish ratio: {hinglish:.1%}")

        return ScoreComponent(
            name="content",
            score=min(100, score),
            weight=self.WEIGHTS["content"],
            signals=signals,
        )

    def _classify_decision(self, composite_score: float) -> str:
        """Classify composite score into decision category.

        Args:
            composite_score: Weighted sum (0-100).

        Returns:
            Decision string.
        """
        if composite_score >= self.THRESHOLDS["BLOCK"]:
            return "BLOCK"
        elif composite_score >= self.THRESHOLDS["ESCALATE"]:
            return "ESCALATE"
        elif composite_score >= self.THRESHOLDS["INVESTIGATE"]:
            return "INVESTIGATE"
        elif composite_score >= self.THRESHOLDS["MONITOR"]:
            return "MONITOR"
        return "IGNORE"

    def score_batch(
        self, channels: List[Dict], **kwargs
    ) -> List[DecisionScore]:
        """Score multiple channels.

        Args:
            channels: List of channel dataset dicts.

        Returns:
            List of DecisionScore.
        """
        return [self.score(ch, **kwargs) for ch in channels]
