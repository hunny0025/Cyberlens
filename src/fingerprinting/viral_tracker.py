"""
CyberLens — Viral Tracker + Dedup Engine
==========================================
Tracks how scam content spreads across platforms
and prevents duplicate analysis.

Author: CyberLens Team — GPCSSI Internship
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("cyberlens.fingerprinting")


# ---------------------------------------------------------------------------
# Deduplication Engine
# ---------------------------------------------------------------------------

class DedupEngine:
    """Prevents duplicate post analysis using multi-signal hashing.

    Signals:
      1. URL hash — exact same post URL
      2. Image pHash — near-identical images
      3. Content hash — same caption text
    """

    def __init__(self):
        self._seen_urls: Set[str] = set()
        self._seen_phashes: Set[str] = set()
        self._seen_content: Set[str] = set()
        self._total_deduped = 0

    def is_duplicate(self, post: Any) -> bool:
        """Check if a post has already been processed.

        Args:
            post: Object with post_url, image_phash, caption_text attributes.

        Returns:
            True if post is a duplicate.
        """
        url = getattr(post, "post_url", "") or post.get("post_url", "")
        phash = getattr(post, "image_phash", "") or post.get("image_phash", "")
        text = getattr(post, "caption_text", "") or post.get("caption_text", "")

        url_hash = self._hash(url) if url else ""
        content_hash = self._hash(text[:200]) if text else ""

        if url_hash and url_hash in self._seen_urls:
            self._total_deduped += 1
            return True
        if phash and phash in self._seen_phashes:
            self._total_deduped += 1
            return True
        if content_hash and content_hash in self._seen_content:
            self._total_deduped += 1
            return True

        # Register as seen
        if url_hash: self._seen_urls.add(url_hash)
        if phash: self._seen_phashes.add(phash)
        if content_hash: self._seen_content.add(content_hash)

        return False

    @property
    def total_deduped(self) -> int:
        return self._total_deduped

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "seen_urls": len(self._seen_urls),
            "seen_phashes": len(self._seen_phashes),
            "seen_content": len(self._seen_content),
            "total_deduped": self._total_deduped,
        }

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Viral Tracker
# ---------------------------------------------------------------------------

@dataclass
class Appearance:
    """A single appearance of content on a platform."""
    platform: str
    channel: str
    timestamp: str
    subscriber_count: int = 0


@dataclass
class SpreadMap:
    """How a piece of scam content spread across platforms."""
    image_hash: str
    first_seen_platform: str
    first_seen_channel: str
    first_seen_timestamp: str
    appearances: List[Appearance]
    spread_velocity: float    # posts per hour
    platforms_reached: List[str]
    estimated_reach: int      # sum of subscriber counts
    spread_score: float       # 0–100 virality score


class ViralTracker:
    """Tracks how scam content spreads across platforms.

    Answers: "Where did this scam start and how fast is it spreading?"
    """

    def __init__(self):
        # In production: query Neo4j / DB for spread history
        self._spread_db: Dict[str, List[Appearance]] = {}

    def record_appearance(
        self,
        image_hash: str,
        platform: str,
        channel: str,
        timestamp: str,
        subscriber_count: int = 0,
    ) -> None:
        """Record a new appearance of an image."""
        if image_hash not in self._spread_db:
            self._spread_db[image_hash] = []

        self._spread_db[image_hash].append(Appearance(
            platform=platform,
            channel=channel,
            timestamp=timestamp,
            subscriber_count=subscriber_count,
        ))

    def track_spread(self, image_hash: str) -> SpreadMap:
        """Get the spread map for an image.

        Args:
            image_hash: SHA256 or pHash of the image.

        Returns:
            SpreadMap showing viral spread pattern.
        """
        appearances = self._spread_db.get(image_hash, [])

        if not appearances:
            return self._demo_spread(image_hash)

        # Sort by timestamp
        appearances_sorted = sorted(appearances, key=lambda a: a.timestamp)
        first = appearances_sorted[0]

        # Compute spread velocity (appearances per hour)
        if len(appearances_sorted) >= 2:
            first_ts = datetime.fromisoformat(appearances_sorted[0].timestamp)
            last_ts = datetime.fromisoformat(appearances_sorted[-1].timestamp)
            hours = max(1, (last_ts - first_ts).total_seconds() / 3600)
            velocity = len(appearances) / hours
        else:
            velocity = 0.0

        platforms = list({a.platform for a in appearances})
        total_reach = sum(a.subscriber_count for a in appearances)

        # Virality score (0–100)
        spread_score = min(100.0,
            len(appearances) * 3 +
            len(platforms) * 15 +
            min(30, total_reach / 1000)
        )

        return SpreadMap(
            image_hash=image_hash,
            first_seen_platform=first.platform,
            first_seen_channel=first.channel,
            first_seen_timestamp=first.timestamp,
            appearances=appearances_sorted,
            spread_velocity=round(velocity, 2),
            platforms_reached=platforms,
            estimated_reach=total_reach,
            spread_score=round(spread_score, 1),
        )

    @staticmethod
    def _demo_spread(image_hash: str) -> SpreadMap:
        """Demo spread data when no real tracking data."""
        from datetime import timedelta
        now = datetime.now()
        appearances = [
            Appearance("Telegram", "t.me/invest_vip",
                       (now - timedelta(hours=72)).isoformat(), 12000),
            Appearance("Instagram", "@quick_money_tips",
                       (now - timedelta(hours=48)).isoformat(), 8500),
            Appearance("Instagram", "@earn_daily_india",
                       (now - timedelta(hours=36)).isoformat(), 4200),
            Appearance("Facebook", "Investment Tips India",
                       (now - timedelta(hours=24)).isoformat(), 15000),
            Appearance("WhatsApp", "Group forward", now.isoformat(), 0),
        ]
        return SpreadMap(
            image_hash=image_hash,
            first_seen_platform="Telegram",
            first_seen_channel="t.me/invest_vip",
            first_seen_timestamp=appearances[0].timestamp,
            appearances=appearances,
            spread_velocity=1.4,
            platforms_reached=["Telegram", "Instagram", "Facebook", "WhatsApp"],
            estimated_reach=39700,
            spread_score=74.0,
        )
