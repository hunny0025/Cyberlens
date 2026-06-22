"""
CyberLens — Instagram Monitor (Playwright-based)
==================================================
Monitors PUBLIC Instagram pages and hashtags for scam content.

Uses Playwright for browser automation — no login required for public content.
Rotates user-agents and respects rate limits.

Author: CyberLens Team — GPCSSI Internship
"""

import asyncio
import logging
import random
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cyberlens.monitor.instagram")

# ── Scam hashtags to monitor (Hindi + English) ────────────────────────────
SCAM_HASHTAGS = [
    # Hindi transliterated
    "investment", "doublemoney", "stocktips", "earnmoney",
    "guaranteedreturns", "workfromhome", "cashincome",
    # English
    "investmenttips", "makemoneyonline", "passiveincome",
    "cryptoearning", "ipl", "betting", "fixedmatch",
]

# Typical delay range between requests (seconds)
DELAY_MIN = 3.0
DELAY_MAX = 6.0

# Rotating user agents to avoid blocks
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


@dataclass
class InstagramPost:
    """A scraped Instagram post."""
    post_id: str
    username: str
    caption: str
    post_url: str
    timestamp: str
    image_url: str = ""
    likes: int = 0
    hashtags: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    upi_ids: List[str] = field(default_factory=list)
    source: str = "instagram"


class InstagramMonitor:
    """Monitors public Instagram hashtags and pages for scam content.

    Falls back to stub mode when Playwright is not installed.
    Always enforces 3–6 second delays between requests.
    """

    def __init__(self):
        self._browser = None
        self._context = None
        self._available = False
        self._posts_scraped = 0
        self._monitored_pages: List[str] = []
        self._monitored_hashtags: List[str] = list(SCAM_HASHTAGS)
        self._init_playwright()

    def _init_playwright(self) -> None:
        """Check if Playwright is available."""
        try:
            import playwright  # noqa: F401
            self._available = True
            logger.info("InstagramMonitor: Playwright available")
        except ImportError:
            logger.info(
                "playwright not installed — Instagram monitoring in stub mode. "
                "Install: pip install playwright && playwright install chromium"
            )

    # ── Public API ────────────────────────────────────────────────────

    async def monitor_hashtags(
        self, hashtags: Optional[List[str]] = None
    ) -> List[InstagramPost]:
        """Scrape public posts for scam-related hashtags.

        Args:
            hashtags: List of hashtag strings (without #). Uses defaults if None.

        Returns:
            List of InstagramPost objects found.
        """
        tags = hashtags or self._monitored_hashtags

        if not self._available:
            return self._stub_hashtag_posts(tags)

        posts = []
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport={"width": 1280, "height": 800},
                )
                page = await context.new_page()

                for tag in tags[:5]:  # limit to 5 per cycle
                    try:
                        url = f"https://www.instagram.com/explore/tags/{tag}/"
                        await page.goto(url, timeout=30000)
                        await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

                        # Extract post links
                        links = await page.eval_on_selector_all(
                            "a[href*='/p/']",
                            "els => els.map(e => e.href)",
                        )
                        for link in links[:3]:  # max 3 posts per hashtag
                            post = await self._scrape_post(page, link)
                            if post:
                                posts.append(post)
                                self._posts_scraped += 1
                            await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

                    except Exception as e:
                        logger.debug("Hashtag %s scrape error: %s", tag, e)

                await browser.close()

        except Exception as e:
            logger.error("InstagramMonitor error: %s", e)
            return self._stub_hashtag_posts(tags)

        return posts

    async def monitor_pages(
        self, page_urls: Optional[List[str]] = None
    ) -> List[InstagramPost]:
        """Monitor specific flagged public Instagram pages.

        Args:
            page_urls: List of Instagram profile/post URLs to monitor.

        Returns:
            List of InstagramPost objects.
        """
        urls = page_urls or self._monitored_pages

        if not self._available or not urls:
            return self._stub_page_posts(urls)

        posts = []
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                )
                page = await context.new_page()

                for url in urls[:10]:
                    try:
                        post = await self._scrape_post(page, url)
                        if post:
                            posts.append(post)
                        await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
                    except Exception as e:
                        logger.debug("Page %s error: %s", url, e)

                await browser.close()

        except Exception as e:
            logger.error("InstagramMonitor page error: %s", e)

        return posts

    def add_hashtag(self, hashtag: str) -> None:
        """Add a hashtag to monitor."""
        tag = hashtag.lstrip("#")
        if tag not in self._monitored_hashtags:
            self._monitored_hashtags.append(tag)
            logger.info("Instagram: hashtag added — #%s", tag)

    def add_page(self, page_url: str) -> None:
        """Add a page URL to monitor."""
        if page_url not in self._monitored_pages:
            self._monitored_pages.append(page_url)
            logger.info("Instagram: page added — %s", page_url)

    @property
    def status(self) -> Dict[str, Any]:
        return {
            "available": self._available,
            "posts_scraped": self._posts_scraped,
            "monitored_hashtags": len(self._monitored_hashtags),
            "monitored_pages": len(self._monitored_pages),
        }

    # ── Private ───────────────────────────────────────────────────────

    async def _scrape_post(self, page: Any, url: str) -> Optional[InstagramPost]:
        """Scrape a single public Instagram post."""
        try:
            await page.goto(url, timeout=20000)
            await asyncio.sleep(1.0)

            # Extract caption
            caption = ""
            try:
                caption = await page.inner_text("h1, ._a9zs, span._aade", timeout=5000)
            except Exception:
                pass

            # Extract username
            username = ""
            try:
                username = await page.inner_text("a.x1i10hfl", timeout=3000)
            except Exception:
                pass

            # Parse entities from caption
            phones = re.findall(r"(?:\+91|0)?[6-9]\d{9}", caption)
            upis = re.findall(
                r"[a-zA-Z0-9._\-+]+@(?:paytm|gpay|phonepe|ybl|oksbi|upi|ibl|apl|okhdfcbank)\b",
                caption
            )
            hashtags_found = re.findall(r"#(\w+)", caption)

            post_id = re.search(r"/p/([^/]+)/", url)

            return InstagramPost(
                post_id=post_id.group(1) if post_id else _random_id(),
                username=username[:50] if username else "unknown",
                caption=caption[:500] if caption else "",
                post_url=url,
                timestamp=datetime.now().isoformat(),
                hashtags=hashtags_found[:10],
                phones=phones[:5],
                upi_ids=upis[:5],
            )
        except Exception as e:
            logger.debug("Post scrape error %s: %s", url, e)
            return None

    def _stub_hashtag_posts(self, hashtags: List[str]) -> List[InstagramPost]:
        """Return synthetic posts for demo/testing."""
        SAMPLE = [
            ("invest_tips_india", "🔥 Invest ₹5000 → ₹20,000 in 24 hours! Guaranteed 300% return. DM now! #investment #doublemoney", ["9876543210"], ["invest@paytm"]),
            ("ipl_vip_tips", "💰 IPL match fixed today! Join our VIP group. Pay ₹999 only. #ipl #betting #cricket", [], []),
            ("earn_daily_real", "Work from home earn ₹3000/day guaranteed! No investment. DM for details. #earnmoney #workfromhome", ["8765432109"], []),
        ]
        posts = []
        for username, caption, phones, upis in SAMPLE[:2]:
            posts.append(InstagramPost(
                post_id=_random_id(),
                username=username,
                caption=caption,
                post_url=f"https://www.instagram.com/p/{_random_id()}/",
                timestamp=datetime.now().isoformat(),
                hashtags=re.findall(r"#(\w+)", caption),
                phones=phones,
                upi_ids=upis,
            ))
        return posts

    def _stub_page_posts(self, urls: List[str]) -> List[InstagramPost]:
        """Return synthetic page posts for demo/testing."""
        return []


def _random_id() -> str:
    import random, string
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=11))
