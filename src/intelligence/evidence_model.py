"""
CyberLens -- Evidence Data Model
====================================
Structured, auditable evidence objects for intelligence analysis.

Every output of this system traces back to specific EvidenceItem
objects with provenance, strength classification, and legal weight.

Evidence Strength (adapted from NATO/Admiralty System):
    DEFINITIVE      -- Entity on official blocklist, confirmed match
    STRONG          -- Entity shared across 3+ independent channels
    MODERATE        -- Entity shared across 2 channels, or moderate-confidence extraction
    WEAK            -- Single occurrence, suspicious pattern
    CIRCUMSTANTIAL  -- Pattern match only, no specific entity

Author: CyberLens Team
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("cyberlens.intelligence.evidence_model")


# ---------------------------------------------------------------------------
# Evidence Strength
# ---------------------------------------------------------------------------

class EvidenceStrength(str, Enum):
    """Categorical evidence strength -- NOT a continuous score.

    Ordered from strongest to weakest.  Each level has a precise
    definition tied to observable, auditable conditions.
    """
    DEFINITIVE = "DEFINITIVE"
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    CIRCUMSTANTIAL = "CIRCUMSTANTIAL"

    @property
    def numeric_rank(self) -> int:
        """Integer rank for comparison. Higher = stronger."""
        return {
            "DEFINITIVE": 5,
            "STRONG": 4,
            "MODERATE": 3,
            "WEAK": 2,
            "CIRCUMSTANTIAL": 1,
        }[self.value]

    def __ge__(self, other: EvidenceStrength) -> bool:
        return self.numeric_rank >= other.numeric_rank

    def __gt__(self, other: EvidenceStrength) -> bool:
        return self.numeric_rank > other.numeric_rank

    def __le__(self, other: EvidenceStrength) -> bool:
        return self.numeric_rank <= other.numeric_rank

    def __lt__(self, other: EvidenceStrength) -> bool:
        return self.numeric_rank < other.numeric_rank


# ---------------------------------------------------------------------------
# Evidence Item -- atomic unit of evidence
# ---------------------------------------------------------------------------

@dataclass
class EvidenceItem:
    """A single piece of intelligence evidence.

    Every assertion the system makes must be traceable to one or
    more EvidenceItem objects.

    Attributes:
        evidence_type:  Category of evidence (e.g. SHARED_UPI, I4C_BLOCKLIST_MATCH).
        source:         Where this evidence was obtained (e.g. "telegram_channel", "i4c_advisory").
        value:          The actual entity value (e.g. "fraud@paytm", "+91-9876543210").
        observed_at:    ISO-8601 timestamp of observation.
        strength:       Categorical strength classification.
        extraction_method: How the entity was obtained (regex, ocr, api, graph_traversal).
        extraction_confidence: Float 0-1 indicating extraction reliability.
        admissible:     Whether this could be used under Indian Evidence Act.
        requires_corroboration: Whether this needs independent confirmation.
        details:        Free-form supporting details.
    """
    evidence_type: str
    source: str
    value: str
    observed_at: str = ""

    strength: str = "CIRCUMSTANTIAL"

    extraction_method: str = "unknown"
    extraction_confidence: float = 1.0

    admissible: bool = True
    requires_corroboration: bool = False
    details: str = ""

    def __post_init__(self):
        if not self.observed_at:
            self.observed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Evidence Types -- enumerated for consistency
# ---------------------------------------------------------------------------

class EvidenceType:
    """Constants for evidence_type field."""
    # Infrastructure (DEFINITIVE / STRONG)
    I4C_BLOCKLIST_MATCH = "I4C_BLOCKLIST_MATCH"
    CERTIN_BLOCKLIST_MATCH = "CERTIN_BLOCKLIST_MATCH"
    SHARED_UPI = "SHARED_UPI"
    SHARED_PHONE = "SHARED_PHONE"
    SHARED_DOMAIN = "SHARED_DOMAIN"
    SHARED_IMAGE = "SHARED_IMAGE"
    SHARED_QR = "SHARED_QR"
    SHARED_WALLET = "SHARED_WALLET"

    # Behavioral (MODERATE / WEAK)
    BEHAVIORAL_SIMILARITY = "BEHAVIORAL_SIMILARITY"
    TEMPORAL_MIGRATION = "TEMPORAL_MIGRATION"
    POSTING_PATTERN_MATCH = "POSTING_PATTERN_MATCH"
    DELETION_PATTERN = "DELETION_PATTERN"
    BACKUP_CHANNEL_MENTION = "BACKUP_CHANNEL_MENTION"

    # Content (MODERATE / WEAK)
    SCAM_CATEGORY_MATCH = "SCAM_CATEGORY_MATCH"
    IMPERSONATION_DETECTED = "IMPERSONATION_DETECTED"
    FINANCIAL_PROMISE = "FINANCIAL_PROMISE"
    URGENCY_PRESSURE = "URGENCY_PRESSURE"

    # Graph (STRONG / MODERATE)
    GRAPH_ENTITY_OVERLAP = "GRAPH_ENTITY_OVERLAP"
    CAMPAIGN_MEMBERSHIP = "CAMPAIGN_MEMBERSHIP"


# ---------------------------------------------------------------------------
# Infrastructure Evidence
# ---------------------------------------------------------------------------

@dataclass
class InfrastructureEvidence:
    """Structured infrastructure evidence for a channel.

    Captures hard evidence: blocklist matches, entity sharing
    across channels.  This is the strongest evidence category
    because infrastructure entities (UPI, phone, domain) require
    real-world resources to acquire.

    Attributes:
        channel_id:  Channel being assessed.
        blocklist_matches: Entities found on I4C/CERT-In blocklists.
        shared_entities:  Entities shared with other channels, grouped by type.
        entity_sharing_degree: Number of other channels sharing entities.
        blocklist_hit_count: Number of distinct blocklist matches.
    """
    channel_id: str = ""

    # DEFINITIVE evidence
    blocklist_matches: List[EvidenceItem] = field(default_factory=list)

    # STRONG / MODERATE evidence -- entity -> list of channels sharing it
    shared_upis: Dict[str, List[str]] = field(default_factory=dict)
    shared_phones: Dict[str, List[str]] = field(default_factory=dict)
    shared_domains: Dict[str, List[str]] = field(default_factory=dict)
    shared_images: Dict[str, List[str]] = field(default_factory=dict)

    # Derived
    entity_sharing_degree: int = 0
    blocklist_hit_count: int = 0

    @property
    def max_evidence_strength(self) -> EvidenceStrength:
        """Highest strength evidence available."""
        if self.blocklist_hit_count > 0:
            return EvidenceStrength.DEFINITIVE
        if self.entity_sharing_degree >= 3:
            return EvidenceStrength.STRONG
        if self.entity_sharing_degree >= 1:
            return EvidenceStrength.MODERATE
        return EvidenceStrength.CIRCUMSTANTIAL

    def all_evidence_items(self) -> List[EvidenceItem]:
        """Flatten all evidence into a single list."""
        items = list(self.blocklist_matches)
        for upi, channels in self.shared_upis.items():
            if len(channels) >= 2:
                items.append(EvidenceItem(
                    evidence_type=EvidenceType.SHARED_UPI,
                    source="entity_resolution",
                    value=upi,
                    strength=EvidenceStrength.STRONG.value if len(channels) >= 3
                             else EvidenceStrength.MODERATE.value,
                    details=f"Shared across {len(channels)} channels: {', '.join(channels[:5])}",
                ))
        for phone, channels in self.shared_phones.items():
            if len(channels) >= 2:
                items.append(EvidenceItem(
                    evidence_type=EvidenceType.SHARED_PHONE,
                    source="entity_resolution",
                    value=phone,
                    strength=EvidenceStrength.STRONG.value if len(channels) >= 3
                             else EvidenceStrength.MODERATE.value,
                    details=f"Shared across {len(channels)} channels: {', '.join(channels[:5])}",
                ))
        for domain, channels in self.shared_domains.items():
            if len(channels) >= 2:
                items.append(EvidenceItem(
                    evidence_type=EvidenceType.SHARED_DOMAIN,
                    source="entity_resolution",
                    value=domain,
                    strength=EvidenceStrength.MODERATE.value,
                    details=f"Shared across {len(channels)} channels: {', '.join(channels[:5])}",
                ))
        return items

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["max_evidence_strength"] = self.max_evidence_strength.value
        return d


# ---------------------------------------------------------------------------
# Behavioral Evidence (Tiered)
# ---------------------------------------------------------------------------

@dataclass
class BehavioralEvidence:
    """Behavioral evidence organized by manipulation difficulty.

    Tier 1 features are hard to fake (require real resources).
    Tier 3 features are trivially manipulable and carry near-zero
    attribution weight.

    Attributes:
        channel_id: Channel being assessed.
        tier1_features: Hard-to-fake features (infrastructure reuse patterns).
        tier2_features: Moderate-effort features (posting schedule, deletion rate).
        tier3_features: Easy-to-fake features (emoji, language ratio). Low trust.
        evidence_items: Specific behavioral observations as EvidenceItem list.
    """
    channel_id: str = ""

    # Tier 1: Hard to fake -- require real-world resources to change
    tier1_features: Dict[str, float] = field(default_factory=dict)
    #   infrastructure_reuse_pattern
    #   financial_entity_velocity
    #   payment_method_diversity

    # Tier 2: Moderate effort to change
    tier2_features: Dict[str, float] = field(default_factory=dict)
    #   posting_hours_entropy
    #   posting_days_entropy
    #   posting_regularity
    #   content_deletion_rate
    #   backup_channel_mentions
    #   forward_ratio

    # Tier 3: Easy to change -- low weight in attribution
    tier3_features: Dict[str, float] = field(default_factory=dict)
    #   hindi_ratio, english_ratio, hinglish_ratio
    #   avg_message_length
    #   urgency_word_density
    #   emoji_density

    # Specific behavioral observations
    evidence_items: List[EvidenceItem] = field(default_factory=list)

    def get_attribution_vector(self) -> List[float]:
        """Return feature vector for attribution (Tier 1 + Tier 2 only).

        Tier 3 features are excluded because they are trivially
        manipulable and would allow adversarial evasion.

        Returns:
            List of floats from Tier 1 and Tier 2 features.
        """
        vec = []
        # Consistent ordering
        for key in sorted(self.tier1_features.keys()):
            vec.append(self.tier1_features[key])
        for key in sorted(self.tier2_features.keys()):
            vec.append(self.tier2_features[key])
        return vec

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Content Evidence
# ---------------------------------------------------------------------------

@dataclass
class ContentEvidence:
    """Content-based evidence from text/image analysis.

    Uses pattern matching for deterministic signals and LLM
    classification for category/narrative analysis.

    Attributes:
        channel_id: Channel being assessed.
        scam_category: Detected scam type.
        category_confidence: Confidence in the category assignment.
        contains_financial_promises: Deterministic pattern match.
        contains_urgency_pressure: Deterministic pattern match.
        contains_impersonation: Claims to be a known entity (SBI, CBI, etc.).
        impersonated_entity: Name of the impersonated entity.
        promised_returns: Specific financial claim if detected.
        evidence_items: Content observations as EvidenceItem list.
    """
    channel_id: str = ""

    scam_category: str = "UNKNOWN"
    category_confidence: float = 0.0
    category_reasoning: str = ""

    contains_financial_promises: bool = False
    contains_urgency_pressure: bool = False
    contains_impersonation: bool = False

    impersonated_entity: Optional[str] = None
    promised_returns: Optional[str] = None

    evidence_items: List[EvidenceItem] = field(default_factory=list)

    @property
    def max_evidence_strength(self) -> EvidenceStrength:
        if self.contains_impersonation:
            return EvidenceStrength.MODERATE
        if self.contains_financial_promises:
            return EvidenceStrength.WEAK
        return EvidenceStrength.CIRCUMSTANTIAL

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["max_evidence_strength"] = self.max_evidence_strength.value
        return d


# ---------------------------------------------------------------------------
# Channel Assessment -- aggregated evidence for one channel
# ---------------------------------------------------------------------------

@dataclass
class ChannelAssessment:
    """Complete evidence assessment for a single channel.

    Aggregates infrastructure, behavioral, and content evidence
    into a unified view with overall strength and confidence.

    Attributes:
        channel_id: Channel identifier.
        channel_name: Human-readable name.
        assessed_at: ISO-8601 timestamp.
        infrastructure: Infrastructure evidence package.
        behavioral: Behavioral evidence package.
        content: Content evidence package.
        all_evidence: Flattened list of all evidence items.
        overall_strength: Highest strength across all evidence.
    """
    channel_id: str = ""
    channel_name: str = ""
    assessed_at: str = ""

    infrastructure: InfrastructureEvidence = field(
        default_factory=InfrastructureEvidence
    )
    behavioral: BehavioralEvidence = field(
        default_factory=BehavioralEvidence
    )
    content: ContentEvidence = field(
        default_factory=ContentEvidence
    )

    def __post_init__(self):
        if not self.assessed_at:
            self.assessed_at = datetime.now(timezone.utc).isoformat()

    @property
    def all_evidence(self) -> List[EvidenceItem]:
        """All evidence items across all categories."""
        items = []
        items.extend(self.infrastructure.all_evidence_items())
        items.extend(self.behavioral.evidence_items)
        items.extend(self.content.evidence_items)
        return items

    @property
    def overall_strength(self) -> EvidenceStrength:
        """Highest evidence strength across all categories."""
        strengths = [
            self.infrastructure.max_evidence_strength,
            self.content.max_evidence_strength,
        ]
        # Add behavioral only if there are actual observations
        if self.behavioral.evidence_items:
            max_beh = max(
                (EvidenceStrength(e.strength) for e in self.behavioral.evidence_items),
                default=EvidenceStrength.CIRCUMSTANTIAL,
            )
            strengths.append(max_beh)

        return max(strengths, key=lambda s: s.numeric_rank)

    @property
    def evidence_count(self) -> int:
        return len(self.all_evidence)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "assessed_at": self.assessed_at,
            "overall_strength": self.overall_strength.value,
            "evidence_count": self.evidence_count,
            "infrastructure": self.infrastructure.to_dict(),
            "behavioral": self.behavioral.to_dict(),
            "content": self.content.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)
