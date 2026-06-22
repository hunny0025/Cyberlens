"""
CyberLens — Synthetic Feed
==============================
Simulates a real-time crawler feed by reading from the synthetic
dataset and serving items with realistic timestamps and sources.

Can be mixed with real scraped posts for demo/development.
"""

import datetime
import hashlib
import json
import logging
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from src.crawler.social_scraper import ScrapedPost

logger = logging.getLogger("cyberlens.crawler.synthetic")


@dataclass
class CrawlerItem:
    """A single item from the crawler feed."""
    source_url: str
    image_text: str
    raw_text: str
    category_hint: str
    timestamp: str
    record_id: str


# Simulated source URLs
SOURCE_PATTERNS = [
    "https://t.me/betting_tips_official/{id}",
    "https://t.me/ipl_jackpot_2025/{id}",
    "https://t.me/invest_india_profit/{id}",
    "https://instagram.com/p/{code}/",
    "https://www.facebook.com/posts/{code}",
    "https://wa.me/91{phone}?text=join",
    "https://twitter.com/scam_alert/status/{id}",
    "https://google.com/search?q=scam+report+{code}",
    "https://reddit.com/r/india/comments/{code}/",
    "https://youtube.com/watch?v={code}",
]

# Category-to-source mapping for realistic mixing
CATEGORY_SOURCE_MAP = {
    "Real Money Betting": ["TELEGRAM", "INSTAGRAM"],
    "Investment Scam": ["FACEBOOK", "TELEGRAM", "INSTAGRAM"],
    "Fake Customer Care": ["FACEBOOK", "TELEGRAM"],
}


class SyntheticFeed:
    """Simulates a real-time feed of scam content for ingestion.

    Reads from the synthetic dataset and serves items as if they
    were discovered by a web crawler, with realistic timestamps
    and source URLs.

    Can also mix synthetic data with real scraped posts for
    a more realistic demo experience.

    Attributes:
        dataset_path: Path to the synthetic dataset JSON.
        _records: Loaded records.
        _ingested: Set of already-served record IDs.
    """

    def __init__(self, dataset_path: str = "data/synthetic/dataset.json"):
        """Initialize the synthetic feed.

        Args:
            dataset_path: Path to the synthetic dataset JSON file.
        """
        self.dataset_path = Path(dataset_path)
        self._records: List[dict] = []
        self._ingested: Set[str] = set()
        self._load_dataset()

    def _load_dataset(self) -> None:
        """Load the synthetic dataset from disk."""
        if not self.dataset_path.exists():
            logger.warning(
                "Synthetic dataset not found: %s. "
                "Run 'python scripts/generate_dataset.py' first.",
                self.dataset_path,
            )
            return

        with open(self.dataset_path, "r", encoding="utf-8") as f:
            self._records = json.load(f)
        logger.info("Loaded %d records from synthetic dataset", len(self._records))

    def fetch_new_items(self, limit: int = 10) -> List[CrawlerItem]:
        """Fetch a batch of new items (not previously ingested).

        Simulates realistic feed behavior: random subset with
        timestamps spread over recent hours.

        Args:
            limit: Maximum number of items to return.

        Returns:
            List of CrawlerItem instances.
        """
        # Find un-ingested records
        available = [
            r for r in self._records
            if r["id"] not in self._ingested
        ]

        if not available:
            # Reset if all consumed
            logger.info("All items ingested. Resetting feed state.")
            self._ingested.clear()
            available = list(self._records)

        # Random subset
        batch_size = min(limit, len(available))
        batch = random.sample(available, batch_size)

        items = []
        now = datetime.datetime.now()

        for i, record in enumerate(batch):
            # Generate realistic timestamp (spread over last few hours)
            minutes_ago = random.randint(1, 180)
            timestamp = now - datetime.timedelta(minutes=minutes_ago)

            # Generate source URL
            source_url = self._generate_source_url(record["id"])

            item = CrawlerItem(
                source_url=source_url,
                image_text=record.get("image_text", ""),
                raw_text=record.get("text_content", ""),
                category_hint=record.get("category", "Unknown"),
                timestamp=timestamp.isoformat(),
                record_id=record["id"],
            )
            items.append(item)
            self._ingested.add(record["id"])

        logger.info(
            "Synthetic feed: %d new items (%d total ingested / %d available)",
            len(items), len(self._ingested), len(self._records),
        )
        return items

    def mix_with_real(
        self,
        real_posts: List[ScrapedPost],
        ratio: float = 0.3,
    ) -> List[ScrapedPost]:
        """Mix real scraped posts with synthetic data for richer demos.

        Creates a blended feed where `ratio` fraction comes from real
        scraped posts and the remainder is converted from synthetic records.
        This is useful for demos where you want to show the system working
        on both real social media content and synthetic training data.

        Args:
            real_posts: Real scraped posts from SocialScraperManager.
            ratio: Fraction of the output that should be real posts (0.0–1.0).
                   Default 0.3 = 30% real, 70% synthetic.

        Returns:
            Mixed list of ScrapedPost (both real and converted synthetic).
        """
        if not real_posts and not self._records:
            return []

        # Determine counts
        total_desired = max(len(real_posts), 20)
        real_count = min(len(real_posts), int(total_desired * ratio))
        synthetic_count = total_desired - real_count

        # Select real posts
        selected_real = random.sample(real_posts, min(real_count, len(real_posts)))

        # Convert synthetic records to ScrapedPost format
        available_synthetic = [
            r for r in self._records
            if r["id"] not in self._ingested
        ]
        if not available_synthetic:
            available_synthetic = list(self._records)

        synthetic_sample = random.sample(
            available_synthetic,
            min(synthetic_count, len(available_synthetic)),
        )

        converted_synthetic: List[ScrapedPost] = []
        now = datetime.datetime.now()

        for record in synthetic_sample:
            category = record.get("category", "Unknown")
            possible_sources = CATEGORY_SOURCE_MAP.get(category, ["TELEGRAM"])
            source = random.choice(possible_sources)

            post = ScrapedPost(
                id=record["id"],
                source=source,
                post_url=self._generate_source_url(record["id"]),
                image_url="",
                image_local_path="",
                caption_text=record.get("text_content", ""),
                username=f"synthetic_{record['id'][-5:]}",
                timestamp=(
                    now - datetime.timedelta(minutes=random.randint(1, 360))
                ).isoformat(),
                scrape_timestamp=now.isoformat(),
                likes_count=random.randint(0, 500),
                comments_count=random.randint(0, 50),
                processed=False,
            )
            converted_synthetic.append(post)
            self._ingested.add(record["id"])

        # Merge and shuffle
        mixed = selected_real + converted_synthetic
        random.shuffle(mixed)

        logger.info(
            "Mixed feed: %d real + %d synthetic = %d total (ratio=%.1f)",
            len(selected_real), len(converted_synthetic), len(mixed), ratio,
        )
        return mixed

    def as_scraped_posts(self, limit: int = 20) -> List[ScrapedPost]:
        """Convert synthetic feed items to ScrapedPost format.

        Useful for unified API responses that expect ScrapedPost.

        Args:
            limit: Max items to convert.

        Returns:
            List of ScrapedPost converted from synthetic data.
        """
        items = self.fetch_new_items(limit)
        posts: List[ScrapedPost] = []
        now = datetime.datetime.now()

        for item in items:
            post = ScrapedPost(
                id=item.record_id,
                source="SYNTHETIC",
                post_url=item.source_url,
                caption_text=item.raw_text,
                username="synthetic_feed",
                timestamp=item.timestamp,
                scrape_timestamp=now.isoformat(),
            )
            posts.append(post)

        return posts

    def _generate_source_url(self, record_id: str) -> str:
        """Generate a realistic fake source URL.

        Args:
            record_id: Record ID for embedding in URL.

        Returns:
            Fake source URL string.
        """
        pattern = random.choice(SOURCE_PATTERNS)
        code = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=8))
        phone = "".join(random.choices("0123456789", k=10))
        rand_id = random.randint(100000, 999999)

        return pattern.format(id=rand_id, code=code, phone=phone)

    @property
    def total_records(self) -> int:
        """Total number of records in dataset."""
        return len(self._records)

    @property
    def ingested_count(self) -> int:
        """Number of records already ingested."""
        return len(self._ingested)


# Backward-compatible alias
SyntheticCrawler = SyntheticFeed
