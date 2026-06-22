"""
CyberLens — Telegram Channel Data Collector
===============================================
Collects structured datasets from PUBLIC Telegram channels
for training the behavioral fingerprinter and scam classifier.

Uses Telethon to gather channel metadata, full message history,
posting schedules, language distribution, entity extraction, and
growth snapshots.

PUBLIC channels only — no private groups or DMs.

Author: CyberLens Team — GPCSSI Internship
"""

import asyncio
import json
import logging
import os
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("cyberlens.data_collection.telegram")

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class PostData:
    """Single Telegram channel post."""
    message_id: int = 0
    text: str = ""
    timestamp: str = ""
    views: int = 0
    forwards: int = 0
    has_media: bool = False
    media_type: str = ""
    reactions_count: int = 0
    reply_count: int = 0


@dataclass
class ChannelDataset:
    """Full structured dataset for a single Telegram channel."""

    # Channel metadata
    channel_metadata: Dict[str, Any] = field(default_factory=dict)

    # All posts
    posts: List[Dict[str, Any]] = field(default_factory=list)

    # Behavioral signals
    posting_schedule: List[float] = field(default_factory=lambda: [0.0] * 24)
    posting_frequency: float = 0.0
    language_distribution: Dict[str, float] = field(default_factory=dict)
    media_ratio: Dict[str, float] = field(default_factory=dict)
    forward_ratio: float = 0.0
    growth_snapshots: List[Dict[str, Any]] = field(default_factory=list)
    linked_channels: List[str] = field(default_factory=list)
    entities_found: Dict[str, List[str]] = field(default_factory=dict)

    # Collection metadata
    collected_at: str = ""
    collector_version: str = "5.0"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON export."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Entity extraction regexes
# ---------------------------------------------------------------------------

# Indian phone numbers: +91XXXXXXXXXX or 10-digit starting with 6-9
RE_PHONE = re.compile(
    r"(?:\+91[\-\s]?)?[6-9]\d{4}[\-\s]?\d{5}"
)

# UPI IDs: name@bankcode
RE_UPI = re.compile(
    r"[a-zA-Z0-9._\-]+@(?:upi|paytm|oksbi|okaxis|okicici|okhdfcbank|"
    r"ybl|ibl|axl|sbi|icici|hdfc|kotak|apl|boi|citi|indus|"
    r"freecharge|phonepe|gpay|amazonpay|jupiteraxis|slice|fi|niyoicici)\b",
    re.IGNORECASE,
)

# URLs
RE_URL = re.compile(
    r"https?://[^\s<>\"']+|(?:www\.)[^\s<>\"']+"
)

# Telegram links: t.me/xxx or @xxx
RE_TELEGRAM_LINK = re.compile(
    r"(?:https?://)?t\.me/(?:joinchat/)?[a-zA-Z0-9_]+"
    r"|@[a-zA-Z][a-zA-Z0-9_]{3,}",
)

# QR code mentions
RE_QR = re.compile(
    r"\bQR\s*code\b|\bQR\b|\bscan\s*(?:the\s*)?code\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Language detection (heuristic)
# ---------------------------------------------------------------------------

def _detect_language(text: str) -> str:
    """Detect language via Unicode range heuristic.

    Returns:
        'hindi', 'english', or 'hinglish'.
    """
    if not text:
        return "unknown"

    devanagari = sum(1 for ch in text if "\u0900" <= ch <= "\u097F")
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    total = devanagari + latin

    if total == 0:
        return "unknown"

    hindi_ratio = devanagari / total
    if hindi_ratio > 0.6:
        return "hindi"
    elif hindi_ratio > 0.2:
        return "hinglish"
    else:
        return "english"


# ---------------------------------------------------------------------------
# TelegramDataCollector
# ---------------------------------------------------------------------------

class TelegramDataCollector:
    """Collects structured datasets from public Telegram channels.

    Uses Telethon to access the Telegram API. Requires
    TELEGRAM_API_ID and TELEGRAM_API_HASH environment variables.

    Attributes:
        api_id: Telegram API ID.
        api_hash: Telegram API hash.
        output_dir: Directory to save raw channel data.
    """

    def __init__(
        self,
        api_id: Optional[str] = None,
        api_hash: Optional[str] = None,
        output_dir: str = "data/raw/telegram",
        message_limit: int = 500,
    ):
        """Initialize the collector.

        Args:
            api_id: Telegram API ID (defaults to TELEGRAM_API_ID env var).
            api_hash: Telegram API hash (defaults to TELEGRAM_API_HASH env var).
            output_dir: Directory for raw JSON output files.
            message_limit: Max messages to collect per channel.
        """
        self.api_id = api_id or os.getenv("TELEGRAM_API_ID", "")
        self.api_hash = api_hash or os.getenv("TELEGRAM_API_HASH", "")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.message_limit = message_limit
        self._available = False

        try:
            from telethon import TelegramClient  # noqa: F401
            self._available = bool(self.api_id and self.api_hash)
        except ImportError:
            logger.warning(
                "Telethon not installed. Install: pip install telethon"
            )

        if not self._available:
            logger.warning(
                "TelegramDataCollector unavailable — "
                "set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env"
            )

    @property
    def is_available(self) -> bool:
        """Whether the collector has valid credentials."""
        return self._available

    async def collect_channel(
        self, channel_username: str
    ) -> ChannelDataset:
        """Collect a full dataset from a public Telegram channel.

        Args:
            channel_username: Channel username (without @).

        Returns:
            ChannelDataset with all behavioral signals.
        """
        if not self._available:
            logger.error("Collector not available — missing credentials")
            return ChannelDataset()

        from telethon import TelegramClient
        from telethon.tl.functions.channels import GetFullChannelRequest

        channel_username = channel_username.lstrip("@")
        session_path = Path("data/.telethon_collector")
        session_path.parent.mkdir(parents=True, exist_ok=True)

        client = TelegramClient(
            str(session_path), int(self.api_id), self.api_hash
        )

        dataset = ChannelDataset(collected_at=datetime.now(timezone.utc).isoformat())

        try:
            await client.start()
            logger.info("Collecting channel: @%s", channel_username)

            # Get channel entity
            try:
                entity = await client.get_entity(channel_username)
            except Exception as e:
                logger.error("Could not find channel @%s: %s", channel_username, e)
                return dataset

            # Channel metadata
            try:
                full = await client(GetFullChannelRequest(entity))
                dataset.channel_metadata = {
                    "name": getattr(entity, "title", ""),
                    "description": getattr(full.full_chat, "about", "") or "",
                    "subscriber_count": getattr(full.full_chat, "participants_count", 0) or 0,
                    "creation_date": entity.date.isoformat() if hasattr(entity, "date") and entity.date else "",
                    "username": channel_username,
                    "invite_link": getattr(full.full_chat, "exported_invite", None) and
                                   getattr(full.full_chat.exported_invite, "link", "") or "",
                    "is_verified": getattr(entity, "verified", False),
                }
            except Exception as e:
                logger.warning("Could not get full metadata for @%s: %s", channel_username, e)
                dataset.channel_metadata = {
                    "name": getattr(entity, "title", channel_username),
                    "username": channel_username,
                }

            # Collect messages
            posts: List[Dict] = []
            hour_counts = Counter()
            day_counts = Counter()
            lang_counts = Counter()
            media_counts = Counter({"images": 0, "videos": 0, "links": 0})
            forward_count = 0
            total_count = 0
            all_entities: Dict[str, set] = {
                "phones": set(),
                "upis": set(),
                "urls": set(),
                "qr_mentions": set(),
                "telegram_links": set(),
            }
            linked_channels: set = set()
            timestamps: List[datetime] = []

            async for msg in client.iter_messages(entity, limit=self.message_limit):
                total_count += 1
                text = msg.text or ""

                # Determine media type
                has_media = msg.media is not None
                media_type = ""
                if has_media:
                    media_cls = type(msg.media).__name__
                    if "Photo" in media_cls:
                        media_type = "photo"
                        media_counts["images"] += 1
                    elif "Document" in media_cls or "Video" in media_cls:
                        media_type = "video"
                        media_counts["videos"] += 1
                    else:
                        media_type = "other"

                # Count reactions
                reactions_count = 0
                if hasattr(msg, "reactions") and msg.reactions:
                    try:
                        reactions_count = sum(
                            r.count for r in msg.reactions.results
                        )
                    except Exception:
                        pass

                post = PostData(
                    message_id=msg.id,
                    text=text[:5000],
                    timestamp=msg.date.isoformat() if msg.date else "",
                    views=msg.views or 0,
                    forwards=msg.forwards or 0,
                    has_media=has_media,
                    media_type=media_type,
                    reactions_count=reactions_count,
                    reply_count=getattr(msg, "replies", None) and
                                getattr(msg.replies, "replies", 0) or 0,
                )
                posts.append(asdict(post))

                # Temporal analysis
                if msg.date:
                    hour_counts[msg.date.hour] += 1
                    day_counts[msg.date.weekday()] += 1
                    timestamps.append(msg.date)

                # Language detection
                if text.strip():
                    lang = _detect_language(text)
                    lang_counts[lang] += 1

                # Forward tracking
                if msg.fwd_from:
                    forward_count += 1

                # Entity extraction
                phones = RE_PHONE.findall(text)
                upis = RE_UPI.findall(text)
                urls = RE_URL.findall(text)
                tg_links = RE_TELEGRAM_LINK.findall(text)
                qr_mentions = RE_QR.findall(text)

                all_entities["phones"].update(phones)
                all_entities["upis"].update(upis)
                all_entities["urls"].update(urls)
                all_entities["telegram_links"].update(tg_links)
                if qr_mentions:
                    all_entities["qr_mentions"].add(f"msg_{msg.id}")

                # Link counting
                if urls:
                    media_counts["links"] += len(urls)

                # Linked channels from telegram links
                for link in tg_links:
                    clean = link.lstrip("@").replace("https://t.me/", "").replace("http://t.me/", "")
                    if "/" in clean:
                        clean = clean.split("/")[0]
                    if clean and clean != channel_username:
                        linked_channels.add(clean)

            dataset.posts = posts

            # Posting schedule (24-dim normalized histogram)
            if total_count > 0:
                schedule = [0.0] * 24
                for hour, count in hour_counts.items():
                    schedule[hour] = count / total_count
                dataset.posting_schedule = schedule

            # Posting frequency (posts per day)
            if timestamps and len(timestamps) >= 2:
                sorted_ts = sorted(timestamps)
                span_days = max(
                    (sorted_ts[-1] - sorted_ts[0]).total_seconds() / 86400,
                    1.0,
                )
                dataset.posting_frequency = round(total_count / span_days, 2)

            # Language distribution
            total_lang = sum(lang_counts.values()) or 1
            dataset.language_distribution = {
                lang: round(count / total_lang, 3)
                for lang, count in lang_counts.most_common()
            }

            # Media ratio (per 100 posts)
            if total_count > 0:
                dataset.media_ratio = {
                    k: round(v / total_count * 100, 2)
                    for k, v in media_counts.items()
                }

            # Forward ratio
            dataset.forward_ratio = round(
                forward_count / max(total_count, 1), 3
            )

            # Growth snapshots (current only — historical requires repeated collection)
            sub_count = dataset.channel_metadata.get("subscriber_count", 0)
            if sub_count:
                dataset.growth_snapshots = [{
                    "date": datetime.now(timezone.utc).isoformat(),
                    "subscribers": sub_count,
                }]

            # Linked channels
            dataset.linked_channels = sorted(linked_channels)

            # Entities found (convert sets to lists)
            dataset.entities_found = {
                k: sorted(v) for k, v in all_entities.items()
            }

            logger.info(
                "Collected @%s: %d posts, %d entities, langs=%s",
                channel_username,
                total_count,
                sum(len(v) for v in all_entities.values()),
                dict(lang_counts.most_common(3)),
            )

        except Exception as e:
            logger.error("Collection failed for @%s: %s", channel_username, e)
        finally:
            await client.disconnect()

        # Save raw data
        self._save(channel_username, dataset)
        return dataset

    async def collect_batch(
        self, channel_list: List[str]
    ) -> List[ChannelDataset]:
        """Collect datasets from multiple channels.

        Args:
            channel_list: List of channel usernames.

        Returns:
            List of ChannelDataset, one per channel.
        """
        results: List[ChannelDataset] = []
        for i, channel in enumerate(channel_list, 1):
            logger.info(
                "Collecting %d/%d: @%s", i, len(channel_list), channel
            )
            try:
                ds = await self.collect_channel(channel)
                results.append(ds)
            except Exception as e:
                logger.error("Batch collect failed for @%s: %s", channel, e)
                results.append(ChannelDataset())
            # Rate limit between channels
            await asyncio.sleep(2.0)
        return results

    def _save(self, channel_username: str, dataset: ChannelDataset) -> None:
        """Save raw channel data to JSON.

        Args:
            channel_username: Channel name for filename.
            dataset: Collected dataset.
        """
        filepath = self.output_dir / f"{channel_username}.json"
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(dataset.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info("Saved -> %s", filepath)
        except Exception as e:
            logger.error("Save failed for @%s: %s", channel_username, e)
