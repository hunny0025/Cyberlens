"""
CyberLens — Monitor Orchestrator
=====================================
Coordinates all monitors + early warning system.
Uses asyncio tasks + APScheduler for periodic tasks.

Schedule:
  Every 5 min  — check early warning thresholds
  Every 15 min — run campaign discovery on new posts
  Every 1 hour — update growth predictions
  Every 6 hours — full network analysis

Author: CyberLens Team — GPCSSI Internship
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cyberlens.monitor.orchestrator")


@dataclass
class MonitorStatus:
    """Status of all monitors."""
    telegram_active: bool = False
    instagram_active: bool = False
    early_warning_active: bool = False
    posts_per_hour: float = 0.0
    total_posts_today: int = 0
    active_alerts: int = 0
    monitored_channels: int = 0
    monitored_hashtags: int = 0
    last_update: str = ""

    def __post_init__(self):
        if not self.last_update:
            self.last_update = datetime.now().isoformat()


class MonitorOrchestrator:
    """Coordinates all monitoring components.

    Starts Telegram + Instagram monitors as asyncio tasks,
    runs periodic scheduled tasks for campaign discovery,
    growth prediction, and network analysis.
    """

    def __init__(self, app=None):
        self.app = app
        self._tasks: List[asyncio.Task] = []
        self._running = False
        self._stats = {
            "total_posts_processed": 0,
            "total_posts_today": 0,
            "posts_per_hour": 0.0,
            "campaigns_discovered": 0,
        }
        self._early_warning = None
        self._telegram_monitor = None
        self._watchlist_channels: List[str] = []
        self._watchlist_hashtags: List[str] = [
            "#investment", "#doublemoney", "#stocktips", "#betting",
            "#ipl", "#earnmoney", "#workfromhome",
        ]
        self._scheduler = None

    async def start(self) -> None:
        """Start all monitors and scheduled tasks."""
        if self._running:
            logger.warning("Orchestrator already running")
            return

        self._running = True
        logger.info("MonitorOrchestrator starting...")

        # Initialize components
        try:
            from src.monitor.telegram_monitor import TelegramMonitor
            self._telegram_monitor = TelegramMonitor()
        except Exception as e:
            logger.warning("TelegramMonitor init failed: %s", e)

        try:
            from src.monitor.early_warning import EarlyWarningSystem
            self._early_warning = EarlyWarningSystem()
        except Exception as e:
            logger.warning("EarlyWarningSystem init failed: %s", e)

        # Start asyncio tasks
        self._tasks = [
            asyncio.create_task(self._telegram_loop(), name="telegram_loop"),
            asyncio.create_task(self._periodic_tasks_loop(), name="periodic_tasks"),
        ]

        logger.info("MonitorOrchestrator started (%d tasks)", len(self._tasks))

    async def stop(self) -> None:
        """Gracefully stop all monitors."""
        self._running = False

        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._tasks.clear()
        logger.info("MonitorOrchestrator stopped")

    def status(self) -> MonitorStatus:
        """Get current monitor status."""
        return MonitorStatus(
            telegram_active=bool(
                self._telegram_monitor and
                getattr(self._telegram_monitor, "_available", False)
            ),
            instagram_active=False,  # planned
            early_warning_active=bool(self._early_warning),
            posts_per_hour=self._stats["posts_per_hour"],
            total_posts_today=self._stats["total_posts_today"],
            active_alerts=len(
                self._early_warning.get_active_alerts()
                if self._early_warning else []
            ),
            monitored_channels=len(self._watchlist_channels),
            monitored_hashtags=len(self._watchlist_hashtags),
        )

    def add_channel(self, channel: str) -> None:
        """Add a Telegram channel to the watchlist."""
        if channel not in self._watchlist_channels:
            self._watchlist_channels.append(channel)
            if self._telegram_monitor:
                self._telegram_monitor.add_channel(channel)
            logger.info("Channel added to watchlist: %s", channel)

    def add_hashtag(self, hashtag: str) -> None:
        """Add an Instagram hashtag to monitoring."""
        if hashtag not in self._watchlist_hashtags:
            self._watchlist_hashtags.append(hashtag)
            logger.info("Hashtag added to monitor: %s", hashtag)

    # ── Private task loops ────────────────────────────────────────────

    async def _telegram_loop(self) -> None:
        """Continuous Telegram monitoring loop."""
        if not self._telegram_monitor:
            return

        try:
            async for post in self._telegram_monitor.monitor_channels(self._watchlist_channels):
                self._stats["total_posts_processed"] += 1
                self._stats["total_posts_today"] += 1
                await self._process_post(post)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Telegram loop error: %s", e)

    async def _periodic_tasks_loop(self) -> None:
        """Run periodic analysis tasks."""
        intervals = {
            "early_warning": 300,      # 5 min
            "campaign_discovery": 900,  # 15 min
            "growth_update": 3600,      # 1 hour
            "network_analysis": 21600,  # 6 hours
        }
        last_run = {k: 0.0 for k in intervals}

        while self._running:
            now = asyncio.get_event_loop().time()

            for task_name, interval in intervals.items():
                if now - last_run[task_name] >= interval:
                    last_run[task_name] = now
                    await self._run_periodic_task(task_name)

            await asyncio.sleep(60)  # check every minute

    async def _run_periodic_task(self, task_name: str) -> None:
        """Execute a specific periodic task."""
        try:
            if task_name == "early_warning":
                await self._check_early_warnings()
            elif task_name == "campaign_discovery":
                await self._run_campaign_discovery()
            elif task_name == "growth_update":
                await self._update_growth_predictions()
            elif task_name == "network_analysis":
                await self._run_network_analysis()
        except Exception as e:
            logger.error("Periodic task %s failed: %s", task_name, e)

    async def _process_post(self, post: Any) -> None:
        """Process a single scraped post through the analysis pipeline."""
        try:
            from src.api.routes.websocket import emit_post_found
            await emit_post_found({
                "source": post.source,
                "username": post.channel_name,
                "caption_preview": (post.text or "")[:150],
                "post_url": "",
                "timestamp": post.timestamp,
            })
        except Exception:
            pass

    async def _check_early_warnings(self) -> None:
        if not self._early_warning:
            return
        # Check demo campaigns
        demo_campaigns = [
            {"id": "cpg-001", "name": "IPL Betting Ring", "channel_count": 23,
             "growth_rate": 12.5, "estimated_reach": 45000, "victim_estimate": 4500},
        ]
        for campaign in demo_campaigns:
            await self._early_warning.check_thresholds(campaign)

    async def _run_campaign_discovery(self) -> None:
        logger.debug("Running campaign discovery cycle...")
        self._stats["campaigns_discovered"] += 1  # placeholder

    async def _update_growth_predictions(self) -> None:
        logger.debug("Updating growth predictions...")

    async def _run_network_analysis(self) -> None:
        logger.debug("Running network analysis...")
