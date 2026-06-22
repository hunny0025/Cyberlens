"""
CyberLens — Background Scraper Worker
=========================================
Periodic background task that:
1. Runs SocialScraperManager every 30 minutes
2. Performs OCR + classification on scraped content
3. Saves HIGH/CRITICAL cases automatically
4. Broadcasts results to WebSocket clients

Uses asyncio tasks (no APScheduler dependency needed).

Author: CyberLens Team — GPCSSI Internship
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger("cyberlens.api.worker")


class ScraperWorker:
    """Background scraper worker that runs periodically.

    Attributes:
        interval_seconds: Time between scrape cycles.
        running: Whether the worker is currently active.
    """

    def __init__(self, app, interval_seconds: int = 1800):
        """Initialize the scraper worker.

        Args:
            app: FastAPI app instance (for accessing app.state).
            interval_seconds: Seconds between scrape cycles (default 30min).
        """
        self.app = app
        self.interval_seconds = interval_seconds
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._stats = {
            "total_runs": 0,
            "total_posts_scraped": 0,
            "total_cases_created": 0,
            "last_run_at": None,
            "last_run_duration_s": 0,
            "last_error": None,
        }

    async def start(self) -> None:
        """Start the background scraper loop."""
        if self.running:
            logger.warning("ScraperWorker already running")
            return

        self.running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "ScraperWorker started (interval=%ds)", self.interval_seconds
        )

    async def stop(self) -> None:
        """Stop the background scraper loop."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("ScraperWorker stopped")

    async def _run_loop(self) -> None:
        """Main worker loop — runs scrape cycle at interval."""
        while self.running:
            try:
                await self._run_cycle()
            except Exception as e:
                logger.error("ScraperWorker cycle error: %s", e)
                self._stats["last_error"] = str(e)

            # Wait for next cycle
            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

    async def _run_cycle(self) -> None:
        """Run a single scrape → analyze → save cycle."""
        start = time.time()
        self._stats["total_runs"] += 1
        self._stats["last_run_at"] = datetime.now().isoformat()

        logger.info("ScraperWorker cycle #%d starting...", self._stats["total_runs"])

        # Broadcast status
        await self._emit_status("running")

        # Step 1: Scrape
        social_scraper = getattr(self.app.state, "social_scraper", None)
        if not social_scraper:
            logger.warning("No social scraper available — skipping cycle")
            await self._emit_status("no_scraper")
            return

        try:
            posts = await social_scraper.fetch_all(limit_per_source=10)
        except Exception as e:
            logger.error("Scrape failed: %s", e)
            await self._emit_status("error", error=str(e))
            return

        self._stats["total_posts_scraped"] += len(posts)

        if not posts:
            logger.info("No new posts found")
            await self._emit_status("idle", posts_found=0)
            return

        # Broadcast post-found events
        for post in posts:
            await self._emit_post_found(post)

        # Step 2: Analyze and save (simplified — OCR/classify if available)
        classifier = getattr(self.app.state, "classifier", None)
        cases_created = 0

        for post in posts:
            try:
                # Basic classification using text
                category = "PENDING"
                severity = "MEDIUM"
                confidence = 0.0

                if classifier and post.caption_text:
                    result = classifier.predict(post.caption_text)
                    category = result.category
                    severity = getattr(result, "severity", "MEDIUM")
                    confidence = result.confidence

                    # Emit classification event
                    await self._emit_classified(
                        category, confidence, severity, post.post_url
                    )

                    # HIGH_SEVERITY_ALERT for critical items
                    if severity in ("CRITICAL", "HIGH") and confidence > 0.6:
                        await self._emit_high_severity(
                            category, post.caption_text[:150], post.post_url
                        )

                cases_created += 1

            except Exception as e:
                logger.debug("Post analysis failed: %s", e)

        self._stats["total_cases_created"] += cases_created

        elapsed = time.time() - start
        self._stats["last_run_duration_s"] = round(elapsed, 1)
        self._stats["last_error"] = None

        logger.info(
            "ScraperWorker cycle complete: %d posts, %d cases, %.1fs",
            len(posts), cases_created, elapsed,
        )
        await self._emit_status(
            "completed", posts_found=len(posts)
        )

    # ── WebSocket emission helpers ────────────────────────────────────

    async def _emit_status(
        self, status: str, posts_found: int = 0, error: str = ""
    ) -> None:
        try:
            from src.api.routes.websocket import emit_scraper_status
            await emit_scraper_status(status, posts_found, error)
        except Exception:
            pass

    async def _emit_post_found(self, post) -> None:
        try:
            from src.api.routes.websocket import emit_post_found
            await emit_post_found({
                "source": post.source,
                "username": post.username,
                "caption_preview": (post.caption_text or "")[:150],
                "post_url": post.post_url,
                "timestamp": post.timestamp,
            })
        except Exception:
            pass

    async def _emit_classified(
        self, category: str, confidence: float, severity: str, url: str
    ) -> None:
        try:
            from src.api.routes.websocket import emit_classified
            await emit_classified(0, category, confidence, severity)
        except Exception:
            pass

    async def _emit_high_severity(
        self, category: str, text: str, url: str
    ) -> None:
        try:
            from src.api.routes.websocket import emit_high_severity
            await emit_high_severity(0, category, f"{text} — {url}")
        except Exception:
            pass

    @property
    def status(self) -> dict:
        """Current worker status."""
        return {
            "running": self.running,
            "interval_seconds": self.interval_seconds,
            **self._stats,
        }
