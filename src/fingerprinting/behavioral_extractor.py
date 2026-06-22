"""
CyberLens — Behavioral Feature Extractor
============================================
Extracts a 28-dimensional behavioral fingerprint from a
Telegram channel dataset for operator attribution.

Feature groups:
    - Temporal (8 dims): posting hours, days, frequency, bursts
    - Linguistic (6 dims): language ratios, message length, urgency, emoji
    - Network Behavior (6 dims): forwards, media, links, cross-channel
    - Infrastructure (5 dims): UPI, phone, domain, QR, payment diversity
    - Growth (3 dims): subscriber growth, view ratio, engagement

Author: CyberLens Team — GPCSSI Internship
"""

import json
import logging
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger("cyberlens.fingerprinting.behavioral")


# ---------------------------------------------------------------------------
# Urgency keywords (Hindi + English)
# ---------------------------------------------------------------------------

URGENCY_KEYWORDS = [
    # English
    "urgent", "hurry", "last chance", "limited time", "act now",
    "don't miss", "final warning", "only today", "expires",
    "guaranteed", "double money", "free", "winner", "claim now",
    "immediately", "right now", "don't delay",
    # Hindi
    "जल्दी", "तुरंत", "अभी", "सीमित समय", "आखिरी मौका",
    "गारंटी", "पैसा दुगना", "फ्री", "विजेता", "अभी क्लेम करो",
    "देर न करें", "जल्दी करो",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BehavioralFingerprint:
    """28-dimensional behavioral fingerprint for a channel.

    Used as input to the Siamese network for operator attribution.
    """
    # Temporal features (8 dims)
    posting_hours_entropy: float = 0.0
    posting_days_entropy: float = 0.0
    posts_per_day_mean: float = 0.0
    posts_per_day_std: float = 0.0
    burst_score: float = 0.0
    silence_pattern: float = 0.0
    peak_hour: float = 0.0
    regularity_score: float = 0.0

    # Linguistic features (6 dims)
    hindi_ratio: float = 0.0
    english_ratio: float = 0.0
    hinglish_ratio: float = 0.0
    avg_message_length: float = 0.0
    urgency_word_density: float = 0.0
    emoji_density: float = 0.0

    # Network behavior features (6 dims)
    forward_ratio: float = 0.0
    media_ratio: float = 0.0
    link_ratio: float = 0.0
    cross_channel_links: float = 0.0
    backup_channel_mentions: float = 0.0
    deletion_rate: float = 0.0

    # Infrastructure features (5 dims)
    unique_upi_count: float = 0.0
    unique_phone_count: float = 0.0
    unique_domain_count: float = 0.0
    qr_usage: float = 0.0
    payment_method_diversity: float = 0.0

    # Growth features (3 dims)
    subscriber_growth_rate: float = 0.0
    view_to_subscriber_ratio: float = 0.0
    engagement_score: float = 0.0

    # Metadata (not part of feature vector)
    channel_name: str = ""

    def to_vector(self) -> List[float]:
        """Convert to 28-dimensional feature vector.

        Returns:
            List of 28 float values.
        """
        return [
            # Temporal (8)
            self.posting_hours_entropy,
            self.posting_days_entropy,
            self.posts_per_day_mean,
            self.posts_per_day_std,
            self.burst_score,
            self.silence_pattern,
            self.peak_hour / 24.0,  # Normalize to 0-1
            self.regularity_score,
            # Linguistic (6)
            self.hindi_ratio,
            self.english_ratio,
            self.hinglish_ratio,
            self.avg_message_length / 1000.0,  # Normalize
            self.urgency_word_density,
            self.emoji_density,
            # Network (6)
            self.forward_ratio,
            self.media_ratio,
            self.link_ratio,
            self.cross_channel_links / 50.0,  # Normalize
            self.backup_channel_mentions / 10.0,  # Normalize
            self.deletion_rate,
            # Infrastructure (5)
            self.unique_upi_count / 20.0,  # Normalize
            self.unique_phone_count / 20.0,
            self.unique_domain_count / 50.0,
            self.qr_usage,
            self.payment_method_diversity,
            # Growth (3)
            min(self.subscriber_growth_rate / 100.0, 1.0),
            self.view_to_subscriber_ratio,
            self.engagement_score,
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        d = asdict(self)
        d["feature_vector"] = self.to_vector()
        return d


# ---------------------------------------------------------------------------
# BehavioralExtractor
# ---------------------------------------------------------------------------

class BehavioralExtractor:
    """Extracts behavioral fingerprints from Telegram channel datasets.

    Processes a ChannelDataset (or its dict representation) and
    produces a 28-dimensional BehavioralFingerprint suitable for
    input to the Siamese network.

    Attributes:
        output_dir: Directory for saving fingerprint JSON files.
    """

    def __init__(
        self,
        output_dir: str = "data/processed/fingerprints",
    ):
        """Initialize the extractor.

        Args:
            output_dir: Directory for fingerprint JSON files.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract(
        self, channel_data: Dict[str, Any]
    ) -> BehavioralFingerprint:
        """Extract a behavioral fingerprint from a channel dataset.

        Args:
            channel_data: ChannelDataset as dict (from JSON).

        Returns:
            BehavioralFingerprint with all 28 features.
        """
        posts = channel_data.get("posts", [])
        metadata = channel_data.get("channel_metadata", {})
        channel_name = metadata.get("username", "unknown")

        fp = BehavioralFingerprint(channel_name=channel_name)

        # ── Temporal features ────────────────────────────────
        fp.posting_hours_entropy = self._compute_hours_entropy(channel_data)
        fp.posting_days_entropy = self._compute_days_entropy(posts)
        ppd = self._compute_posting_frequency(posts)
        fp.posts_per_day_mean = ppd[0]
        fp.posts_per_day_std = ppd[1]
        fp.burst_score = self._compute_burst_score(posts)
        fp.silence_pattern = self._compute_silence_pattern(posts)
        fp.peak_hour = self._compute_peak_hour(channel_data)
        fp.regularity_score = self._compute_regularity(posts)

        # ── Linguistic features ──────────────────────────────
        lang = channel_data.get("language_distribution", {})
        fp.hindi_ratio = lang.get("hindi", 0.0)
        fp.english_ratio = lang.get("english", 0.0)
        fp.hinglish_ratio = lang.get("hinglish", 0.0)
        fp.avg_message_length = self._avg_message_length(posts)
        fp.urgency_word_density = self._urgency_density(posts)
        fp.emoji_density = self._emoji_density(posts)

        # ── Network behavior features ────────────────────────
        fp.forward_ratio = channel_data.get("forward_ratio", 0.0)
        media = channel_data.get("media_ratio", {})
        fp.media_ratio = (
            (media.get("images", 0) + media.get("videos", 0)) / 100.0
        )
        fp.link_ratio = media.get("links", 0.0) / 100.0
        fp.cross_channel_links = float(
            len(channel_data.get("linked_channels", []))
        )
        fp.backup_channel_mentions = self._count_backup_mentions(posts)
        fp.deletion_rate = self._estimate_deletion_rate(posts)

        # ── Infrastructure features ──────────────────────────
        entities = channel_data.get("entities_found", {})
        fp.unique_upi_count = float(len(entities.get("upis", [])))
        fp.unique_phone_count = float(len(entities.get("phones", [])))
        fp.unique_domain_count = float(
            len(set(entities.get("urls", [])))
        )
        fp.qr_usage = float(len(entities.get("qr_mentions", [])))
        if posts:
            fp.qr_usage = fp.qr_usage / len(posts) * 100.0
        fp.payment_method_diversity = self._payment_diversity(entities)

        # ── Growth features ──────────────────────────────────
        fp.subscriber_growth_rate = self._estimate_growth_rate(channel_data)
        fp.view_to_subscriber_ratio = self._view_sub_ratio(
            posts, metadata.get("subscriber_count", 0)
        )
        fp.engagement_score = self._engagement_score(posts)

        # Save
        self._save(channel_name, fp)
        return fp

    def extract_batch(
        self, channel_list: List[Dict[str, Any]]
    ) -> List[BehavioralFingerprint]:
        """Extract fingerprints for multiple channels.

        Args:
            channel_list: List of channel datasets as dicts.

        Returns:
            List of BehavioralFingerprint.
        """
        return [self.extract(ch) for ch in channel_list]

    # ── Temporal feature helpers ─────────────────────────────────

    def _compute_hours_entropy(self, channel_data: Dict) -> float:
        """Compute Shannon entropy of posting hour distribution."""
        schedule = channel_data.get("posting_schedule", [0.0] * 24)
        return self._entropy(schedule)

    def _compute_days_entropy(self, posts: List[Dict]) -> float:
        """Compute Shannon entropy of posting day-of-week distribution."""
        from datetime import datetime
        day_counts = [0] * 7
        for post in posts:
            ts = post.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    day_counts[dt.weekday()] += 1
                except Exception:
                    pass
        total = sum(day_counts) or 1
        dist = [c / total for c in day_counts]
        return self._entropy(dist)

    def _compute_posting_frequency(
        self, posts: List[Dict]
    ) -> tuple:
        """Compute mean and std of posts per day."""
        from datetime import datetime
        from collections import Counter

        day_counts: Counter = Counter()
        for post in posts:
            ts = post.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    day_counts[dt.strftime("%Y-%m-%d")] += 1
                except Exception:
                    pass

        if not day_counts:
            return (0.0, 0.0)

        values = list(day_counts.values())
        mean = float(np.mean(values))
        std = float(np.std(values))
        return (round(mean, 2), round(std, 2))

    def _compute_burst_score(self, posts: List[Dict]) -> float:
        """Compute burst score: max_posts_in_1hr / avg_posts_per_hr."""
        from datetime import datetime
        from collections import Counter

        hour_counts: Counter = Counter()
        for post in posts:
            ts = post.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    hour_key = dt.strftime("%Y-%m-%d-%H")
                    hour_counts[hour_key] += 1
                except Exception:
                    pass

        if not hour_counts:
            return 0.0

        max_in_hour = max(hour_counts.values())
        avg_per_hour = np.mean(list(hour_counts.values()))
        return round(max_in_hour / max(avg_per_hour, 1.0), 2)

    def _compute_silence_pattern(self, posts: List[Dict]) -> float:
        """Compute longest gap in hours between consecutive posts."""
        from datetime import datetime

        timestamps = []
        for post in posts:
            ts = post.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    timestamps.append(dt)
                except Exception:
                    pass

        if len(timestamps) < 2:
            return 0.0

        timestamps.sort()
        max_gap = 0.0
        for i in range(1, len(timestamps)):
            gap = (timestamps[i] - timestamps[i - 1]).total_seconds() / 3600
            max_gap = max(max_gap, gap)

        return round(min(max_gap, 720.0) / 720.0, 4)  # Normalize to 0-1 (max 30 days)

    def _compute_peak_hour(self, channel_data: Dict) -> float:
        """Return the peak posting hour (0-23)."""
        schedule = channel_data.get("posting_schedule", [0.0] * 24)
        if not schedule or max(schedule) == 0:
            return 12.0
        return float(schedule.index(max(schedule)))

    def _compute_regularity(self, posts: List[Dict]) -> float:
        """Compute posting regularity: 1 - coefficient of variation."""
        from datetime import datetime
        from collections import Counter

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

    # ── Linguistic feature helpers ───────────────────────────────

    def _avg_message_length(self, posts: List[Dict]) -> float:
        """Average character length of post text."""
        lengths = [len(p.get("text", "")) for p in posts if p.get("text")]
        return float(np.mean(lengths)) if lengths else 0.0

    def _urgency_density(self, posts: List[Dict]) -> float:
        """Urgency keywords per 100 posts."""
        if not posts:
            return 0.0

        count = 0
        for post in posts:
            text = post.get("text", "").lower()
            for kw in URGENCY_KEYWORDS:
                if kw.lower() in text:
                    count += 1

        return round(count / len(posts) * 100, 2)

    def _emoji_density(self, posts: List[Dict]) -> float:
        """Emoji count per 100 characters of text."""
        total_chars = 0
        total_emojis = 0

        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F900-\U0001F9FF"
            "\U00002702-\U000027B0"
            "\U0001FA00-\U0001FA6F"
            "\U0001FA70-\U0001FAFF]+",
            flags=re.UNICODE,
        )

        for post in posts:
            text = post.get("text", "")
            total_chars += len(text)
            total_emojis += len(emoji_pattern.findall(text))

        if total_chars == 0:
            return 0.0
        return round(total_emojis / total_chars * 100, 4)

    # ── Network feature helpers ──────────────────────────────────

    def _count_backup_mentions(self, posts: List[Dict]) -> float:
        """Count mentions of backup/alternative channels."""
        backup_kw = [
            "backup", "back up", "new channel", "moved to",
            "join new", "alternative", "बैकअप", "नया चैनल",
        ]
        count = 0
        for post in posts:
            text = post.get("text", "").lower()
            if any(kw in text for kw in backup_kw):
                count += 1
        return float(count)

    def _estimate_deletion_rate(self, posts: List[Dict]) -> float:
        """Estimate message deletion rate from message ID gaps."""
        ids = sorted(
            p.get("message_id", 0) for p in posts if p.get("message_id")
        )
        if len(ids) < 2:
            return 0.0

        expected = ids[-1] - ids[0] + 1
        actual = len(ids)
        if expected <= 0:
            return 0.0
        return round(1.0 - (actual / expected), 4)

    # ── Infrastructure feature helpers ───────────────────────────

    def _payment_diversity(self, entities: Dict) -> float:
        """How many different payment methods are used (0-1)."""
        methods = 0
        if entities.get("upis"):
            methods += 1
        if entities.get("phones"):
            methods += 1
        if entities.get("qr_mentions"):
            methods += 1
        # Crypto patterns
        if entities.get("urls"):
            for url in entities["urls"]:
                if any(kw in url.lower() for kw in ["bitcoin", "btc", "eth", "usdt"]):
                    methods += 1
                    break
        return methods / 4.0  # Max 4 types

    # ── Growth feature helpers ───────────────────────────────────

    def _estimate_growth_rate(self, channel_data: Dict) -> float:
        """Estimate subscriber growth rate (subs/day)."""
        snapshots = channel_data.get("growth_snapshots", [])
        if len(snapshots) < 2:
            return 0.0

        from datetime import datetime

        try:
            first = snapshots[0]
            last = snapshots[-1]
            d1 = datetime.fromisoformat(first["date"].replace("Z", "+00:00"))
            d2 = datetime.fromisoformat(last["date"].replace("Z", "+00:00"))
            days = max((d2 - d1).total_seconds() / 86400, 1.0)
            growth = last["subscribers"] - first["subscribers"]
            return round(growth / days, 2)
        except Exception:
            return 0.0

    def _view_sub_ratio(
        self, posts: List[Dict], subscriber_count: int
    ) -> float:
        """Average views / subscriber count ratio."""
        if not posts or subscriber_count <= 0:
            return 0.0

        views = [p.get("views", 0) for p in posts if p.get("views", 0) > 0]
        if not views:
            return 0.0

        avg_views = np.mean(views)
        return round(min(avg_views / subscriber_count, 5.0), 4)

    def _engagement_score(self, posts: List[Dict]) -> float:
        """Compute engagement score from reactions, forwards, views."""
        if not posts:
            return 0.0

        scores = []
        for post in posts:
            views = post.get("views", 0) or 1
            reactions = post.get("reactions_count", 0)
            forwards = post.get("forwards", 0)
            replies = post.get("reply_count", 0)

            engagement = (reactions + forwards + replies) / views
            scores.append(engagement)

        return round(float(np.mean(scores)), 6)

    # ── Utility ──────────────────────────────────────────────────

    @staticmethod
    def _entropy(distribution: List[float]) -> float:
        """Compute normalized Shannon entropy of a distribution.

        Args:
            distribution: Probability distribution (sums to ~1).

        Returns:
            Normalized entropy value (0-1).
        """
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

    def _save(
        self, channel_name: str, fp: BehavioralFingerprint
    ) -> None:
        """Save fingerprint to JSON.

        Args:
            channel_name: Channel identifier for filename.
            fp: Computed fingerprint.
        """
        filepath = self.output_dir / f"{channel_name}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(fp.to_dict(), f, indent=2)
        logger.debug("Fingerprint saved -> %s", filepath)
