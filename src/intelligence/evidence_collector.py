"""
CyberLens -- Evidence Collector
===================================
Collects structured evidence from channel data, blocklists,
and the entity graph.  Produces EvidenceItem objects -- never
raw scores or arbitrary points.

This replaces the point-based _score_infrastructure, _score_network,
_score_behavioral, _score_content methods in the old scoring engine.

Author: CyberLens Team
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import numpy as np

from src.intelligence.evidence_model import (
    BehavioralEvidence,
    ChannelAssessment,
    ContentEvidence,
    EvidenceItem,
    EvidenceStrength,
    EvidenceType,
    InfrastructureEvidence,
)

logger = logging.getLogger("cyberlens.intelligence.evidence_collector")

# ---------------------------------------------------------------------------
# Urgency / impersonation keyword lists
# ---------------------------------------------------------------------------

URGENCY_KEYWORDS = [
    "urgent", "hurry", "last chance", "limited time", "act now",
    "guaranteed", "double money", "free", "winner", "claim now",
    "immediately", "don't delay",
    # Hindi
    "jaldi", "turant", "abhi", "aakhiri mauka",
    "garanTi", "paisa dugna",
]

IMPERSONATION_TARGETS = {
    "sbi": "State Bank of India",
    "rbi": "Reserve Bank of India",
    "cbi": "Central Bureau of Investigation",
    "ed": "Enforcement Directorate",
    "paytm": "Paytm",
    "phonepe": "PhonePe",
    "google pay": "Google Pay",
    "airtel": "Airtel",
    "customer care": "Customer Care Impersonation",
    "helpline": "Official Helpline Impersonation",
    "aadhaar": "UIDAI / Aadhaar",
    "income tax": "Income Tax Department",
    "digital arrest": "Law Enforcement Impersonation",
}


# ---------------------------------------------------------------------------
# Evidence Collector
# ---------------------------------------------------------------------------

class EvidenceCollector:
    """Collects structured evidence for channel assessment.

    Replaces the old point-based scoring with auditable evidence
    objects.  Each piece of evidence has a type, strength, source,
    and provenance.

    Attributes:
        blocked_domains:  Set of domains from I4C / CERT-In.
        blocked_urls:     Set of URLs from I4C.
        blocked_channels: Set of channel names from I4C.
        blocked_upis:     Set of UPI IDs from blocklists.
        blocked_phones:   Set of phone numbers from blocklists.
    """

    def __init__(
        self,
        i4c_ground_truth_path: str = "data/ground_truth/i4c_advisories.json",
        certin_ground_truth_path: str = "data/ground_truth/certin_alerts.json",
    ):
        self._blocked_domains: Set[str] = set()
        self._blocked_urls: Set[str] = set()
        self._blocked_channels: Set[str] = set()
        self._blocked_upis: Set[str] = set()
        self._blocked_phones: Set[str] = set()

        self._load_blocklists(
            Path(i4c_ground_truth_path),
            Path(certin_ground_truth_path),
        )

    # -- Blocklist loading -------------------------------------------------

    def _load_blocklists(self, i4c_path: Path, certin_path: Path) -> None:
        """Load confirmed blocked entities from ground truth files."""
        if i4c_path.exists():
            try:
                with open(i4c_path, "r", encoding="utf-8") as f:
                    for adv in json.load(f):
                        self._blocked_domains.update(adv.get("blocked_domains", []))
                        self._blocked_urls.update(adv.get("blocked_urls", []))
                        self._blocked_channels.update(adv.get("blocked_channels", []))
                        self._blocked_upis.update(adv.get("blocked_upis", []))
                        self._blocked_phones.update(adv.get("blocked_phones", []))
                logger.info(
                    "Loaded I4C blocklist: %d domains, %d channels, %d UPIs",
                    len(self._blocked_domains),
                    len(self._blocked_channels),
                    len(self._blocked_upis),
                )
            except Exception as exc:
                logger.debug("Could not load I4C blocklist: %s", exc)

        if certin_path.exists():
            try:
                with open(certin_path, "r", encoding="utf-8") as f:
                    for alert in json.load(f):
                        self._blocked_domains.update(alert.get("domains", []))
                logger.info(
                    "Loaded CERT-In blocklist: %d domains total",
                    len(self._blocked_domains),
                )
            except Exception as exc:
                logger.debug("Could not load CERT-In blocklist: %s", exc)

    # =====================================================================
    # Public API
    # =====================================================================

    def assess_channel(
        self,
        channel_data: Dict[str, Any],
        all_channels: Optional[List[Dict[str, Any]]] = None,
    ) -> ChannelAssessment:
        """Produce a complete evidence assessment for a channel.

        Args:
            channel_data:  Channel dataset dict (from training_dataset.json).
            all_channels:  All channels in the dataset (for cross-reference).

        Returns:
            ChannelAssessment with structured evidence across all layers.
        """
        metadata = channel_data.get("channel_metadata", {})
        channel_name = metadata.get("username", "unknown")

        assessment = ChannelAssessment(
            channel_id=channel_name,
            channel_name=channel_name,
        )

        # Layer 1a: Infrastructure evidence
        assessment.infrastructure = self._collect_infrastructure(
            channel_data, all_channels or [],
        )

        # Layer 1b: Behavioral evidence
        assessment.behavioral = self._collect_behavioral(channel_data)

        # Layer 1c: Content evidence
        assessment.content = self._collect_content(channel_data)

        return assessment

    def assess_batch(
        self,
        channels: List[Dict[str, Any]],
    ) -> List[ChannelAssessment]:
        """Assess multiple channels (enables cross-reference).

        Args:
            channels: List of channel dataset dicts.

        Returns:
            List of ChannelAssessment.
        """
        return [self.assess_channel(ch, channels) for ch in channels]

    # =====================================================================
    # Infrastructure Evidence Collection
    # =====================================================================

    def _collect_infrastructure(
        self,
        channel_data: Dict[str, Any],
        all_channels: List[Dict[str, Any]],
    ) -> InfrastructureEvidence:
        """Collect infrastructure evidence: blocklist matches + entity sharing."""
        entities = channel_data.get("entities_found", {})
        metadata = channel_data.get("channel_metadata", {})
        channel_name = metadata.get("username", "unknown")
        xref = channel_data.get("cross_reference", {})

        infra = InfrastructureEvidence(channel_id=channel_name)

        # -- DEFINITIVE: blocklist matches ---------------------------------
        for upi in entities.get("upis", []):
            if upi in self._blocked_upis:
                infra.blocklist_matches.append(EvidenceItem(
                    evidence_type=EvidenceType.I4C_BLOCKLIST_MATCH,
                    source="i4c_blocklist",
                    value=upi,
                    strength=EvidenceStrength.DEFINITIVE.value,
                    extraction_method="exact_match",
                    details=f"UPI ID '{upi}' is on the I4C blocked entity list",
                ))

        for phone in entities.get("phones", []):
            if phone in self._blocked_phones:
                infra.blocklist_matches.append(EvidenceItem(
                    evidence_type=EvidenceType.I4C_BLOCKLIST_MATCH,
                    source="i4c_blocklist",
                    value=phone,
                    strength=EvidenceStrength.DEFINITIVE.value,
                    extraction_method="exact_match",
                    details=f"Phone '{phone}' is on the I4C blocked entity list",
                ))

        for url in entities.get("urls", []):
            for domain in self._blocked_domains:
                if domain and domain in url:
                    infra.blocklist_matches.append(EvidenceItem(
                        evidence_type=EvidenceType.CERTIN_BLOCKLIST_MATCH,
                        source="certin_blocklist",
                        value=domain,
                        strength=EvidenceStrength.DEFINITIVE.value,
                        extraction_method="substring_match",
                        details=f"Domain '{domain}' found in URL '{url[:80]}' is on blocklist",
                    ))
                    break  # one match per URL is sufficient

        # From cross-reference data
        for match in xref.get("matched_blocked_urls", []):
            infra.blocklist_matches.append(EvidenceItem(
                evidence_type=EvidenceType.I4C_BLOCKLIST_MATCH,
                source="cross_reference",
                value=match,
                strength=EvidenceStrength.DEFINITIVE.value,
                extraction_method="cross_reference",
                details=f"URL '{match}' matched during cross-reference check",
            ))

        # -- STRONG/MODERATE: entity sharing with other channels -----------
        if all_channels:
            my_upis = set(entities.get("upis", []))
            my_phones = set(entities.get("phones", []))
            my_domains = set(entities.get("urls", []))

            for other_ch in all_channels:
                other_name = other_ch.get("channel_metadata", {}).get("username", "")
                if other_name == channel_name or not other_name:
                    continue

                other_ent = other_ch.get("entities_found", {})

                for upi in my_upis & set(other_ent.get("upis", [])):
                    infra.shared_upis.setdefault(upi, [channel_name])
                    if other_name not in infra.shared_upis[upi]:
                        infra.shared_upis[upi].append(other_name)

                for phone in my_phones & set(other_ent.get("phones", [])):
                    infra.shared_phones.setdefault(phone, [channel_name])
                    if other_name not in infra.shared_phones[phone]:
                        infra.shared_phones[phone].append(other_name)

                for url in my_domains & set(other_ent.get("urls", [])):
                    infra.shared_domains.setdefault(url, [channel_name])
                    if other_name not in infra.shared_domains[url]:
                        infra.shared_domains[url].append(other_name)

        # Derived metrics
        infra.blocklist_hit_count = len(infra.blocklist_matches)
        sharing_channels: Set[str] = set()
        for channels_list in list(infra.shared_upis.values()) + \
                              list(infra.shared_phones.values()) + \
                              list(infra.shared_domains.values()):
            sharing_channels.update(ch for ch in channels_list if ch != channel_name)
        infra.entity_sharing_degree = len(sharing_channels)

        return infra

    # =====================================================================
    # Behavioral Evidence Collection
    # =====================================================================

    def _collect_behavioral(
        self,
        channel_data: Dict[str, Any],
    ) -> BehavioralEvidence:
        """Collect behavioral evidence organized by manipulation tier."""
        metadata = channel_data.get("channel_metadata", {})
        channel_name = metadata.get("username", "unknown")
        entities = channel_data.get("entities_found", {})
        posts = channel_data.get("posts", [])

        beh = BehavioralEvidence(channel_id=channel_name)

        # -- Tier 1: Hard to fake -----------------------------------------
        upi_count = len(set(entities.get("upis", [])))
        phone_count = len(set(entities.get("phones", [])))
        domain_count = len(set(entities.get("urls", [])))

        payment_types = sum([
            1 if entities.get("upis") else 0,
            1 if entities.get("phones") else 0,
            1 if entities.get("qr_mentions") else 0,
        ])

        beh.tier1_features = {
            "unique_upi_count": min(upi_count / 20.0, 1.0),
            "unique_phone_count": min(phone_count / 20.0, 1.0),
            "unique_domain_count": min(domain_count / 50.0, 1.0),
            "payment_method_diversity": payment_types / 3.0,
        }

        # -- Tier 2: Moderate effort to change ----------------------------
        posting_schedule = channel_data.get("posting_schedule", [0.0] * 24)
        hours_entropy = self._entropy(posting_schedule)

        deletion_rate = self._estimate_deletion_rate(posts)
        forward_ratio = channel_data.get("forward_ratio", 0.0)
        backup_mentions = self._count_backup_mentions(posts)
        regularity = self._compute_regularity(posts)

        beh.tier2_features = {
            "posting_hours_entropy": hours_entropy,
            "posting_regularity": regularity,
            "content_deletion_rate": deletion_rate,
            "forward_ratio": forward_ratio,
            "backup_channel_mentions": min(backup_mentions / 10.0, 1.0),
        }

        # -- Tier 3: Easy to change (low attribution weight) --------------
        lang = channel_data.get("language_distribution", {})
        beh.tier3_features = {
            "hindi_ratio": lang.get("hindi", 0.0),
            "english_ratio": lang.get("english", 0.0),
            "hinglish_ratio": lang.get("hinglish", 0.0),
            "urgency_word_density": self._urgency_density(posts),
            "emoji_density": self._emoji_density(posts),
        }

        # -- Generate specific evidence items -----------------------------
        if deletion_rate > 0.3:
            beh.evidence_items.append(EvidenceItem(
                evidence_type=EvidenceType.DELETION_PATTERN,
                source="message_id_analysis",
                value=f"{deletion_rate:.1%}",
                strength=EvidenceStrength.WEAK.value,
                extraction_method="message_id_gap_analysis",
                details=f"Estimated {deletion_rate:.1%} of messages deleted (message ID gap analysis)",
            ))

        if backup_mentions > 0:
            beh.evidence_items.append(EvidenceItem(
                evidence_type=EvidenceType.BACKUP_CHANNEL_MENTION,
                source="text_analysis",
                value=f"{backup_mentions} mentions",
                strength=EvidenceStrength.MODERATE.value,
                extraction_method="keyword_match",
                details=f"Channel mentions backup/alternative channels {backup_mentions} times",
            ))

        return beh

    # =====================================================================
    # Content Evidence Collection
    # =====================================================================

    def _collect_content(
        self,
        channel_data: Dict[str, Any],
    ) -> ContentEvidence:
        """Collect content evidence from text analysis."""
        metadata = channel_data.get("channel_metadata", {})
        channel_name = metadata.get("username", "unknown")
        posts = channel_data.get("posts", [])

        content = ContentEvidence(channel_id=channel_name)

        all_text = " ".join(
            p.get("text", "").lower() for p in posts[:200]
        )

        # -- Impersonation detection (requires org keyword + scam context) ---
        # A legitimate channel can MENTION "RBI" or "SBI" in news context.
        # Impersonation requires the keyword PLUS scam-indicative context:
        #   "call now", "account blocked", "verify immediately", etc.
        scam_context_keywords = [
            "call now", "call us", "contact", "helpline", "support",
            "blocked", "suspended", "deactivated", "verify", "update kyc",
            "click here", "pay now", "pay fine", "penalty", "arrest",
            "immediately", "urgent", "warning", "freeze",
        ]
        has_scam_context = any(ctx in all_text for ctx in scam_context_keywords)

        if has_scam_context:
            for keyword, entity in IMPERSONATION_TARGETS.items():
                if keyword in all_text:
                    content.contains_impersonation = True
                    content.impersonated_entity = entity
                    content.evidence_items.append(EvidenceItem(
                        evidence_type=EvidenceType.IMPERSONATION_DETECTED,
                        source="text_pattern_match",
                        value=entity,
                        strength=EvidenceStrength.MODERATE.value,
                        extraction_method="keyword_co_occurrence",
                        requires_corroboration=True,
                        details=f"Channel text references '{entity}' WITH scam context "
                                f"(call/verify/blocked/urgent) -- probable impersonation",
                    ))
                    break  # report first match


        # -- Financial promises detection ---------------------------------
        promise_patterns = [
            r"\d+%\s*(?:return|profit|daily|monthly|guaranteed)",
            r"double\s+(?:your\s+)?money",
            r"paisa\s+dugna",
            r"guaranteed\s+(?:return|income|profit)",
        ]
        for pattern in promise_patterns:
            match = re.search(pattern, all_text)
            if match:
                content.contains_financial_promises = True
                content.promised_returns = match.group(0)[:80]
                content.evidence_items.append(EvidenceItem(
                    evidence_type=EvidenceType.FINANCIAL_PROMISE,
                    source="text_pattern_match",
                    value=content.promised_returns,
                    strength=EvidenceStrength.WEAK.value,
                    extraction_method="regex",
                    details=f"Financial promise detected: '{content.promised_returns}'",
                ))
                break

        # -- Urgency pressure detection -----------------------------------
        urgency_count = 0
        for post in posts[:100]:
            text = post.get("text", "").lower()
            if any(kw in text for kw in URGENCY_KEYWORDS):
                urgency_count += 1

        if posts and urgency_count / max(len(posts[:100]), 1) > 0.15:
            content.contains_urgency_pressure = True
            content.evidence_items.append(EvidenceItem(
                evidence_type=EvidenceType.URGENCY_PRESSURE,
                source="text_analysis",
                value=f"{urgency_count}/{len(posts[:100])} posts",
                strength=EvidenceStrength.CIRCUMSTANTIAL.value,
                extraction_method="keyword_frequency",
                details=f"Urgency keywords in {urgency_count} of {len(posts[:100])} analyzed posts",
            ))

        # -- Category detection (rule-based, pending LLM integration) -----
        content.scam_category = self._detect_category(all_text)
        if content.scam_category != "UNKNOWN":
            content.category_confidence = 0.5  # rule-based = low confidence
            content.evidence_items.append(EvidenceItem(
                evidence_type=EvidenceType.SCAM_CATEGORY_MATCH,
                source="rule_based_classifier",
                value=content.scam_category,
                strength=EvidenceStrength.CIRCUMSTANTIAL.value,
                extraction_method="keyword_pattern_match",
                requires_corroboration=True,
                details=f"Category '{content.scam_category}' detected via keyword patterns. "
                        f"Low confidence -- rule-based, not ML-validated.",
            ))

        return content

    # =====================================================================
    # Helper methods
    # =====================================================================

    @staticmethod
    def _detect_category(text: str) -> str:
        """Rule-based category detection. Returns UNKNOWN if unsure.

        Uses multi-word phrases and requires ≥2 distinct keyword hits
        to avoid false positives from generic single words like
        'return' or 'invest'.  Scores all categories and picks the
        best match rather than short-circuiting on the first hit.
        """
        # Each category maps to a list of specific keyword patterns.
        # Patterns use word boundaries (\\b) to avoid substring matches
        # (e.g., 'return' inside 'returned').
        category_patterns = {
            "INVESTMENT_SCAM": [
                r"\binvest(?:ment|ing)?\b",
                r"\bguaranteed\s+return",
                r"\bdouble\s+(?:your\s+)?money\b",
                r"\bstock\s+tips?\b",
                r"\bmutual\s+fund\b",
                r"\bshare\s+market\b",
                r"\bforex\s+trad",
                r"\bcrypto\s+profit",
                r"\bponzi\b",
                r"\bzero\s+risk\b",
                r"\bmonthly\s+income\b",
                r"\bpaisa\s+dugna\b",
                r"\bpakka\s+munafa\b",
                r"\b\d+%\s*(?:return|profit|daily|guaranteed)\b",
            ],
            "BETTING_SCAM": [
                r"\bbetting\s+tips?\b",
                r"\bcricket\s+predict",
                r"\bipl\s+(?:jackpot|toss|bet)",
                r"\bsatta\s+matka\b",
                r"\bmatch\s+fix",
                r"\btoss\s+winner\b",
                r"\bcasino\s+online\b",
                r"\bwin\s+big\s+money\b",
            ],
            "DIGITAL_ARREST": [
                r"\bdigital\s+arrest\b",
                r"\bcbi\s+officer\b",
                r"\benforcement\s+directorate\b",
                r"\bed\s+notice\b",
                r"\barrest\s+warrant\b",
                r"\bcourt\s+order\b",
                r"\bfir\s+registered\b",
            ],
            "IMPERSONATION": [
                r"\bcustomer\s+care\b",
                r"\bhelpline\s+number\b",
                r"\bkyc\s+(?:update|verify|expir)",
                r"\baccount\s+(?:block|suspend|deactivat)",
                r"\btoll\s+free\b",
                r"\bbank\s+(?:alert|support)\b",
                r"\btrai\s+notice\b",
            ],
            "JOB_SCAM": [
                r"\bwork\s+from\s+home\b",
                r"\bpart\s+time\s+job\b",
                r"\bonline\s+(?:job|earn)",
                r"\btyping\s+job\b",
                r"\bdata\s+entry\s+job\b",
                r"\bearn\s+daily\b",
                r"\bregistration\s+fee\b",
            ],
            "LOTTERY_SCAM": [
                r"\blottery\s+winner\b",
                r"\blucky\s+draw\b",
                r"\bkbc\s+winner\b",
                r"\bprize\s+money\b",
                r"\bcongratulations?\s+you\s+won\b",
                r"\bclaim\s+(?:your\s+)?prize\b",
                r"\bwhatsapp\s+lottery\b",
            ],
            "LOAN_SCAM": [
                r"\binstant\s+loan\b",
                r"\bloan\s+app(?:roved)?\b",
                r"\bno\s+document\s+loan\b",
                r"\badvance\s+fee\b",
                r"\bprocessing\s+fee\b",
            ],
        }

        # Score each category: count how many distinct patterns match
        scores = {}
        for category, patterns in category_patterns.items():
            hits = sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))
            if hits >= 2:
                scores[category] = hits

        if not scores:
            return "UNKNOWN"

        # Return the category with the most keyword hits
        return max(scores, key=scores.get)

    @staticmethod
    def _entropy(distribution: List[float]) -> float:
        """Normalized Shannon entropy of a distribution."""
        total = sum(distribution) or 1
        probs = [x / total for x in distribution]
        n = len(probs)
        if n <= 1:
            return 0.0
        entropy = 0.0
        for p in probs:
            if p > 0:
                entropy -= p * math.log2(p)
        max_entropy = math.log2(n)
        return round(entropy / max_entropy, 4) if max_entropy > 0 else 0.0

    @staticmethod
    def _estimate_deletion_rate(posts: List[Dict]) -> float:
        """Estimate message deletion rate from message ID gaps."""
        ids = sorted(
            p.get("message_id", 0) for p in posts if p.get("message_id")
        )
        if len(ids) < 2:
            return 0.0
        expected = ids[-1] - ids[0] + 1
        if expected <= 0:
            return 0.0
        return round(1.0 - (len(ids) / expected), 4)

    @staticmethod
    def _count_backup_mentions(posts: List[Dict]) -> int:
        """Count mentions of backup/alternative channels."""
        backup_kw = ["backup", "new channel", "moved to", "join new", "alternative"]
        count = 0
        for post in posts:
            text = post.get("text", "").lower()
            if any(kw in text for kw in backup_kw):
                count += 1
        return count

    @staticmethod
    def _compute_regularity(posts: List[Dict]) -> float:
        """Posting regularity: 1 - coefficient of variation."""
        day_counts: Counter = Counter()
        for post in posts:
            ts = post.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    day_counts[dt.strftime("%Y-%m-%d")] += 1
                except Exception:
                    pass
        if len(day_counts) < 2:
            return 0.0
        values = list(day_counts.values())
        mean = np.mean(values)
        std = np.std(values)
        cv = std / max(mean, 1e-6)
        return round(max(0.0, 1.0 - cv), 4)

    @staticmethod
    def _urgency_density(posts: List[Dict]) -> float:
        """Fraction of posts containing urgency keywords."""
        if not posts:
            return 0.0
        count = 0
        for post in posts[:100]:
            text = post.get("text", "").lower()
            if any(kw in text for kw in URGENCY_KEYWORDS):
                count += 1
        return round(count / len(posts[:100]), 4)

    @staticmethod
    def _emoji_density(posts: List[Dict]) -> float:
        """Emoji count per 100 characters."""
        total_chars = 0
        total_emojis = 0
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F900-\U0001F9FF"
            "\U00002702-\U000027B0]+",
            flags=re.UNICODE,
        )
        for post in posts[:100]:
            text = post.get("text", "")
            total_chars += len(text)
            total_emojis += len(emoji_pattern.findall(text))
        if total_chars == 0:
            return 0.0
        return round(total_emojis / total_chars * 100, 4)
