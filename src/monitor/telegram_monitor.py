"""
CyberLens — Telegram Monitor (Telethon-based)
================================================
Monitors PUBLIC Telegram channels in real-time for scam content.

Uses: Telethon MTProto client (public channels only — no auth needed)
Credentials: TELEGRAM_API_ID, TELEGRAM_API_HASH from .env (free from my.telegram.org)

Author: CyberLens Team — GPCSSI Internship
"""

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncGenerator, Callable, Dict, List, Optional

logger = logging.getLogger("cyberlens.monitor.telegram")

SCAM_HASHTAGS = [
    "#investment", "#doublemoney", "#stocktips", "#earnmoney",
    "#workfromhome", "#investmenttips", "#stockmarket",
    "#ipl", "#betting", "#cricket", "#guaranteedreturns",
    "#freemoney", "#cryptoinvestment",
]

DEFAULT_CHANNELS = [
    # Known scam channels will be added here by operators
    # Format: username or https://t.me/channelname
]


@dataclass
class TelegramPost:
    """A scraped Telegram post."""
    post_id: str
    channel_id: str
    channel_name: str
    text: str
    timestamp: str
    view_count: int = 0
    forward_count: int = 0
    has_media: bool = False
    media_path: str = ""
    source: str = "telegram"


class TelegramMonitor:
    """Monitors public Telegram channels using Telethon.

    Falls back to stub mode when Telethon is not installed.
    """

    def __init__(self):
        self._client = None
        self._running = False
        self._monitored_channels: List[str] = list(DEFAULT_CHANNELS)
        self._posts_scraped = 0
        self._available = False
        self._init_client()

    def _init_client(self) -> None:
        """Initialize Telethon client."""
        api_id = os.getenv("TELEGRAM_API_ID", "")
        api_hash = os.getenv("TELEGRAM_API_HASH", "")

        if not api_id or not api_hash:
            logger.info("TelegramMonitor: TELEGRAM_API_ID/HASH not set — stub mode")
            return

        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession

            session_str = os.getenv("TELEGRAM_SESSION_STRING", "")
            session = StringSession(session_str) if session_str else StringSession()

            self._client = TelegramClient(
                session=session,
                api_id=int(api_id),
                api_hash=api_hash,
            )
            self._available = True
            logger.info("TelegramMonitor: Telethon client ready")

        except ImportError:
            logger.info("telethon not installed — Telegram monitoring disabled. "
                        "Install: pip install telethon")
        except Exception as e:
            logger.warning("TelegramMonitor init failed: %s", e)

    async def monitor_channels(
        self,
        channel_list: Optional[List[str]] = None,
    ) -> AsyncGenerator[TelegramPost, None]:
        """Monitor public Telegram channels for new posts.

        Args:
            channel_list: List of channel usernames/URLs. Uses default if None.

        Yields:
            TelegramPost for each new message.
        """
        channels = channel_list or self._monitored_channels

        if not self._available:
            # Yield synthetic posts in stub mode
            async for post in self._stub_posts(channels):
                yield post
            return

        try:
            async with self._client:
                logger.info("TelegramMonitor: connected, monitoring %d channels", len(channels))

                # Event handler for new messages
                from telethon import events

                @self._client.on(events.NewMessage(chats=channels))
                async def handle_new_message(event):
                    msg = event.message
                    chat = await event.get_chat()
                    yield TelegramPost(
                        post_id=str(msg.id),
                        channel_id=str(chat.id),
                        channel_name=getattr(chat, "title", "") or getattr(chat, "username", ""),
                        text=msg.message or "",
                        timestamp=msg.date.isoformat() if msg.date else datetime.now().isoformat(),
                        view_count=getattr(msg, "views", 0) or 0,
                        forward_count=getattr(msg, "forwards", 0) or 0,
                        has_media=bool(msg.media),
                    )
                    self._posts_scraped += 1

                await self._client.run_until_disconnected()

        except Exception as e:
            logger.error("TelegramMonitor error: %s", e)

    async def discover_related_channels(self, channel: str) -> List[str]:
        """Find channels mentioned/linked in the given channel.

        Args:
            channel: Source channel username.

        Returns:
            List of discovered related channel usernames.
        """
        if not self._available:
            return []

        discovered = []
        try:
            async with self._client:
                async for msg in self._client.iter_messages(channel, limit=100):
                    text = msg.message or ""
                    # Find t.me links
                    links = re.findall(r"t\.me/([a-zA-Z0-9_]+)", text)
                    for link in links:
                        if link not in self._monitored_channels and link != channel:
                            discovered.append(link)

        except Exception as e:
            logger.error("Channel discovery failed: %s", e)

        return list(set(discovered))

    def add_channel(self, channel: str) -> None:
        """Add a channel to the monitoring list."""
        if channel not in self._monitored_channels:
            self._monitored_channels.append(channel)
            logger.info("Added channel: %s (total: %d)", channel, len(self._monitored_channels))

    @property
    def status(self) -> Dict:
        return {
            "available": self._available,
            "running": self._running,
            "channels_monitored": len(self._monitored_channels),
            "posts_scraped": self._posts_scraped,
        }

    async def _stub_posts(self, channels: List[str]) -> AsyncGenerator[TelegramPost, None]:
        """Yield synthetic posts in stub mode (for demo/testing)."""
        import random
        SAMPLE_TEXTS = [
            "🔥 Invest ₹5000 → Get ₹20,000 in 24 hours! Guaranteed! Contact now.",
            "IPL Match fixed today! 100% accurate prediction. Pay ₹500 to join VIP.",
            "CBI Officer calling — Your Aadhaar is linked to money laundering. Stay on call.",
            "Customer Care SBI: Share your OTP to unblock your account.",
            "Work from home earn ₹3000/day! No investment needed. DM for details.",
        ]
        for i in range(5):
            await asyncio.sleep(0.1)
            yield TelegramPost(
                post_id=f"demo-{i}",
                channel_id=f"ch-demo-{i}",
                channel_name=channels[i % len(channels)] if channels else "demo_channel",
                text=random.choice(SAMPLE_TEXTS),
                timestamp=datetime.now().isoformat(),
                view_count=random.randint(100, 5000),
                source="telegram",
            )
