"""
CyberLens — Identity Resolver
================================
Resolves same scammer identity across multiple platforms using
shared entities, username fuzzy matching, and cross-platform signals.

Example output:
  "87% probability these 3 Telegram channels and 2 Instagram accounts
   belong to the same operator: same phone +91-9876XXXXX, similar
   username pattern @quick_money_*"

Author: CyberLens Team — GPCSSI Internship
"""

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("cyberlens.intelligence.identity")


@dataclass
class Entity:
    """An entity (phone, UPI, username, etc.) with its source."""
    value: str
    entity_type: str          # PHONE / UPI / USERNAME / TELEGRAM / URL
    platform: str = ""
    channel: str = ""


@dataclass
class IdentityCluster:
    """A cluster of entities likely belonging to the same operator."""
    cluster_id: str
    entities: List[Entity]
    match_probability: float
    match_evidence: List[str]
    platforms_linked: List[str]
    operator_name: str = ""    # guessed operator identifier
    summary: str = ""

    def to_readable(self) -> str:
        """Human-readable summary for investigators."""
        return (
            f"Identity Cluster — {self.match_probability:.0%} probability\n"
            f"Operator: {self.operator_name or 'Unknown'}\n"
            f"Platforms: {', '.join(self.platforms_linked)}\n"
            f"Evidence:\n" +
            "\n".join(f"  • {ev}" for ev in self.match_evidence)
        )


class IdentityResolver:
    """Resolves same-operator identity across platforms.

    Uses:
      1. Exact entity matching (phone/UPI seen on multiple platforms)
      2. Username fuzzy matching (similar username patterns)
      3. Behavioral clustering (same posting times, templates)
    """

    def resolve(self, entities: List[Entity]) -> List[IdentityCluster]:
        """Group entities into identity clusters.

        Args:
            entities: List of Entity from multiple platforms.

        Returns:
            List of IdentityCluster sorted by match probability.
        """
        clusters = []

        # Step 1: Exact entity linking (phone / UPI shared across platforms)
        clusters.extend(self._link_by_exact_entity(entities))

        # Step 2: Username fuzzy matching
        clusters.extend(self._link_by_username(entities))

        # Merge overlapping clusters
        merged = self._merge_overlapping(clusters)

        merged.sort(key=lambda c: c.match_probability, reverse=True)
        return merged

    # ── Exact entity matching ─────────────────────────────────────────

    def _link_by_exact_entity(self, entities: List[Entity]) -> List[IdentityCluster]:
        """Find entities that appear on multiple platforms."""
        from collections import defaultdict

        value_to_entities: dict = defaultdict(list)
        for e in entities:
            if e.entity_type in ("PHONE", "UPI"):
                value_to_entities[e.value].append(e)

        clusters = []
        for value, occurrences in value_to_entities.items():
            platforms = list({e.platform for e in occurrences})
            if len(platforms) < 2:
                continue

            probability = min(0.98, 0.7 + len(platforms) * 0.1)
            evidence = [
                f"{e.entity_type} '{value}' found on {e.platform} ({e.channel})"
                for e in occurrences
            ]

            clusters.append(IdentityCluster(
                cluster_id=f"ic-exact-{abs(hash(value)):06d}",
                entities=occurrences,
                match_probability=probability,
                match_evidence=evidence,
                platforms_linked=platforms,
                operator_name=self._guess_operator_name(occurrences),
                summary=f"{value} linked across {', '.join(platforms)}",
            ))

        return clusters

    # ── Username fuzzy matching ───────────────────────────────────────

    def _link_by_username(self, entities: List[Entity]) -> List[IdentityCluster]:
        """Find similar usernames across platforms using fuzzy matching."""
        usernames = [e for e in entities if e.entity_type == "USERNAME"]
        clusters = []

        for i in range(len(usernames)):
            for j in range(i + 1, len(usernames)):
                a, b = usernames[i], usernames[j]
                if a.platform == b.platform:
                    continue

                similarity = self._username_similarity(a.value, b.value)
                if similarity < 0.7:
                    continue

                evidence = [
                    f"Username '{a.value}' ({a.platform}) ≈ '{b.value}' ({b.platform})",
                    f"Similarity: {similarity:.0%}",
                ]
                if self._same_pattern(a.value, b.value):
                    evidence.append(f"Same naming pattern: {self._extract_pattern(a.value)}")

                clusters.append(IdentityCluster(
                    cluster_id=f"ic-fuzzy-{abs(hash(a.value + b.value)):06d}",
                    entities=[a, b],
                    match_probability=similarity * 0.85,
                    match_evidence=evidence,
                    platforms_linked=[a.platform, b.platform],
                    summary=f"Similar usernames: {a.value} / {b.value}",
                ))

        return clusters

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _username_similarity(a: str, b: str) -> float:
        """Compute username similarity using SequenceMatcher."""
        a_clean = re.sub(r"[@_\.\-\d]", "", a.lower())
        b_clean = re.sub(r"[@_\.\-\d]", "", b.lower())
        return SequenceMatcher(None, a_clean, b_clean).ratio()

    @staticmethod
    def _same_pattern(a: str, b: str) -> bool:
        """Check if two usernames follow the same pattern (base + suffix)."""
        a_base = re.sub(r"\d+$|_\w{1,4}$", "", a.lower())
        b_base = re.sub(r"\d+$|_\w{1,4}$", "", b.lower())
        return a_base == b_base and len(a_base) >= 4

    @staticmethod
    def _extract_pattern(username: str) -> str:
        """Extract the pattern (e.g., 'quick_money_*')."""
        return re.sub(r"\d+$", "*", username.lower())

    @staticmethod
    def _guess_operator_name(occurrences: List[Entity]) -> str:
        """Guess operator identity from channel names."""
        channels = [e.channel for e in occurrences if e.channel]
        if channels:
            return f"Operator via {channels[0]}"
        return "Unknown Operator"

    @staticmethod
    def _merge_overlapping(clusters: List[IdentityCluster]) -> List[IdentityCluster]:
        """Merge clusters that share entities (simple dedup)."""
        seen_ids = set()
        merged = []
        for c in clusters:
            key = frozenset(e.value for e in c.entities)
            if key not in seen_ids:
                seen_ids.add(key)
                merged.append(c)
        return merged
