"""
CyberLens — Social Media Scraper Pipeline
=============================================
Playwright-based scrapers for Instagram, Facebook, and Telegram
public content. Monitors scam-related hashtags and keywords across
platforms to feed the CyberLens detection pipeline.

Scrapers:
    - InstagramScraper: Public posts by hashtag
    - FacebookScraper: Public pages by keyword
    - TelegramScraper: Public channels via Telethon
    - SocialScraperManager: Orchestrator with deduplication

All scrapers operate on PUBLIC content only — no login required.
Rate-limited with rotating user agents for responsible scraping.

Author: CyberLens Team — GPCSSI Internship
"""

import asyncio
import hashlib
import json
import logging
import os
import random
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger("cyberlens.crawler.social")

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------

RAW_IMAGES_DIR = Path("data/raw/images")
RAW_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

SCRAPED_OUTPUT = Path("data/raw/scraped_posts.json")
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configure file logging for scraper
_file_handler = logging.FileHandler(LOG_DIR / "scraper.log", encoding="utf-8")
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
)
logger.addHandler(_file_handler)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ScrapedPost:
    """A single scraped social media post."""

    id: str = ""
    source: str = ""  # INSTAGRAM, FACEBOOK, TELEGRAM
    post_url: str = ""
    image_url: str = ""
    image_local_path: str = ""
    caption_text: str = ""
    username: str = ""
    timestamp: str = ""
    scrape_timestamp: str = ""
    likes_count: int = 0
    comments_count: int = 0
    processed: bool = False

    def __post_init__(self):
        if not self.id:
            self.id = f"SP-{uuid.uuid4().hex[:10].upper()}"
        if not self.scrape_timestamp:
            self.scrape_timestamp = datetime.now().isoformat()

    def url_hash(self) -> str:
        """SHA256 hash of post_url for deduplication."""
        return hashlib.sha256(self.post_url.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict:
        """Convert to serializable dict."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Rotating user agents
# ---------------------------------------------------------------------------

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]


def _random_ua() -> str:
    """Return a random user agent string."""
    return random.choice(USER_AGENTS)


# ---------------------------------------------------------------------------
# Instagram Scraper
# ---------------------------------------------------------------------------

INSTAGRAM_HASHTAGS_HINDI = [
    "investment", "doublemoney", "stocktips", "cricketbetting",
    "customersupport", "helpline", "earnmoney", "workfromhome",
]

INSTAGRAM_HASHTAGS_ENGLISH = [
    "investmenttips", "stockmarket", "cricket", "ipl", "betting",
]

ALL_INSTAGRAM_HASHTAGS = INSTAGRAM_HASHTAGS_HINDI + INSTAGRAM_HASHTAGS_ENGLISH


class InstagramScraper:
    """Scrapes public Instagram posts by hashtag using Playwright.

    Targets scam-related hashtags in Hindi and English.
    Downloads images to data/raw/images/ for OCR processing.

    Attributes:
        hashtags: List of hashtags to monitor.
        delay: Seconds between requests for rate limiting.
    """

    BASE_URL = "https://www.instagram.com/explore/tags/{hashtag}/"

    def __init__(
        self,
        hashtags: Optional[List[str]] = None,
        delay: float = 2.0,
    ):
        """Initialize Instagram scraper.

        Args:
            hashtags: Custom hashtag list (defaults to built-in scam tags).
            delay: Delay in seconds between page loads.
        """
        self.hashtags = hashtags or ALL_INSTAGRAM_HASHTAGS
        self.delay = delay
        self._available = False

        try:
            from playwright.async_api import async_playwright  # noqa: F401
            self._available = True
        except ImportError:
            logger.warning(
                "Playwright not installed. Install with: "
                "pip install playwright && playwright install chromium"
            )

    @property
    def is_available(self) -> bool:
        return self._available

    async def scrape_public_posts(
        self,
        hashtags: Optional[List[str]] = None,
        limit_per_tag: int = 5,
    ) -> List[ScrapedPost]:
        """Scrape public Instagram posts for given hashtags.

        Args:
            hashtags: Hashtags to search (without #). Defaults to built-in list.
            limit_per_tag: Max posts to extract per hashtag.

        Returns:
            List of ScrapedPost from Instagram.
        """
        if not self._available:
            logger.warning("Instagram scraper unavailable — Playwright not installed")
            return []

        tags = hashtags or self.hashtags
        all_posts: List[ScrapedPost] = []

        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=_random_ua(),
                viewport={"width": 1280, "height": 900},
                locale="en-IN",
            )
            # Block heavy resources for speed
            await context.route(
                "**/*.{mp4,webm,ogg,wav,mp3,avi}",
                lambda route: route.abort(),
            )

            page = await context.new_page()

            for tag in tags:
                try:
                    posts = await self._scrape_tag(page, tag, limit_per_tag)
                    all_posts.extend(posts)
                    logger.info(
                        "Instagram #%s → %d posts scraped", tag, len(posts)
                    )
                except Exception as e:
                    logger.error("Instagram #%s scrape failed: %s", tag, e)

                # Rate limit
                await asyncio.sleep(self.delay)

            await browser.close()

        logger.info("Instagram total: %d posts from %d hashtags",
                     len(all_posts), len(tags))
        return all_posts

    async def _scrape_tag(
        self, page, tag: str, limit: int
    ) -> List[ScrapedPost]:
        """Scrape posts from a single hashtag page.

        Args:
            page: Playwright page instance.
            tag: Hashtag (without #).
            limit: Max posts to extract.

        Returns:
            List of ScrapedPost.
        """
        url = self.BASE_URL.format(hashtag=tag)
        posts: List[ScrapedPost] = []

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)
        except Exception as e:
            logger.debug("Failed to load Instagram #%s: %s", tag, e)
            return posts

        # Extract post links from the grid
        try:
            links = await page.eval_on_selector_all(
                'a[href*="/p/"]',
                "els => els.map(el => el.href).slice(0, arguments[0])",
                limit,
            )
        except Exception:
            # Fallback: try extracting from article elements
            links = await page.eval_on_selector_all(
                "article a[href*='/p/']",
                "els => els.map(el => el.href)",
            )
            links = links[:limit]

        # Deduplicate
        links = list(dict.fromkeys(links))[:limit]

        for post_url in links:
            try:
                post = await self._extract_post(page, post_url, tag)
                if post:
                    posts.append(post)
            except Exception as e:
                logger.debug("Failed to extract Instagram post %s: %s", post_url, e)

            await asyncio.sleep(self.delay)

        return posts

    async def _extract_post(
        self, page, post_url: str, tag: str
    ) -> Optional[ScrapedPost]:
        """Navigate to a post and extract its data.

        Args:
            page: Playwright page instance.
            post_url: Full post URL.
            tag: Source hashtag.

        Returns:
            ScrapedPost or None on failure.
        """
        try:
            await page.goto(post_url, wait_until="domcontentloaded", timeout=12000)
            await page.wait_for_timeout(1500)
        except Exception:
            return None

        # Extract image URL
        image_url = ""
        try:
            img_el = await page.query_selector("article img[src*='instagram']")
            if img_el:
                image_url = await img_el.get_attribute("src") or ""
        except Exception:
            pass

        # Extract caption
        caption = ""
        try:
            # Instagram captions are typically in spans within the first comment
            caption_el = await page.query_selector(
                "article div[role='presentation'] span, "
                "article h1 + div span, "
                "article ul li span"
            )
            if caption_el:
                caption = (await caption_el.inner_text()) or ""
        except Exception:
            pass

        # Extract username
        username = ""
        try:
            user_el = await page.query_selector(
                "article header a[href*='/'], "
                "article a[role='link'][href*='/']"
            )
            if user_el:
                href = await user_el.get_attribute("href") or ""
                username = href.strip("/").split("/")[-1] if href else ""
        except Exception:
            pass

        # Extract engagement counts
        likes = 0
        comments = 0
        try:
            likes_el = await page.query_selector(
                "section span[class*='like'], button span"
            )
            if likes_el:
                likes_text = await likes_el.inner_text()
                likes = _parse_count(likes_text)
        except Exception:
            pass

        # Download image
        image_local = ""
        if image_url:
            image_local = await self._download_image(page, image_url, tag)

        if not caption and not image_url:
            return None

        return ScrapedPost(
            source="INSTAGRAM",
            post_url=post_url,
            image_url=image_url,
            image_local_path=image_local,
            caption_text=caption[:2000],
            username=username,
            timestamp=datetime.now().isoformat(),
            likes_count=likes,
            comments_count=comments,
        )

    async def _download_image(
        self, page, image_url: str, tag: str
    ) -> str:
        """Download post image to local storage.

        Args:
            page: Playwright page.
            image_url: Remote image URL.
            tag: Source hashtag (used in filename).

        Returns:
            Local file path or empty string on failure.
        """
        try:
            response = await page.context.request.get(image_url, timeout=10000)
            if response.ok:
                filename = f"ig_{tag}_{uuid.uuid4().hex[:8]}.jpg"
                filepath = RAW_IMAGES_DIR / filename
                with open(filepath, "wb") as f:
                    f.write(await response.body())
                return str(filepath)
        except Exception as e:
            logger.debug("Image download failed: %s", e)
        return ""


# ---------------------------------------------------------------------------
# Facebook Scraper
# ---------------------------------------------------------------------------

FACEBOOK_KEYWORDS = [
    "investment tips india",
    "earn money online india",
    "customer care helpline",
    "cricket betting tips",
    "guaranteed returns india",
    "stock market tips free",
    "work from home jobs india",
]


class FacebookScraper:
    """Scrapes public Facebook pages/posts by keyword using Playwright.

    Targets financial scam and fake helpline pages visible without login.

    Attributes:
        keywords: Search keywords to monitor.
        delay: Seconds between requests.
    """

    SEARCH_URL = "https://www.facebook.com/search/posts/?q={query}"

    def __init__(
        self,
        keywords: Optional[List[str]] = None,
        delay: float = 2.0,
    ):
        """Initialize Facebook scraper.

        Args:
            keywords: Search keywords. Defaults to built-in scam terms.
            delay: Rate limit delay in seconds.
        """
        self.keywords = keywords or FACEBOOK_KEYWORDS
        self.delay = delay
        self._available = False

        try:
            from playwright.async_api import async_playwright  # noqa: F401
            self._available = True
        except ImportError:
            logger.warning("Playwright not installed for Facebook scraper")

    @property
    def is_available(self) -> bool:
        return self._available

    async def scrape_public_pages(
        self,
        page_keywords: Optional[List[str]] = None,
        limit_per_keyword: int = 5,
    ) -> List[ScrapedPost]:
        """Scrape public Facebook posts matching keywords.

        Facebook aggressively blocks unauthenticated scraping, so this
        scraper extracts whatever is visible on the public search page.
        Falls back gracefully if blocked.

        Args:
            page_keywords: Keywords to search. Defaults to built-in list.
            limit_per_keyword: Max posts per keyword.

        Returns:
            List of ScrapedPost from Facebook.
        """
        if not self._available:
            logger.warning("Facebook scraper unavailable — Playwright not installed")
            return []

        keywords = page_keywords or self.keywords
        all_posts: List[ScrapedPost] = []

        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=_random_ua(),
                viewport={"width": 1280, "height": 900},
                locale="en-IN",
            )
            page = await context.new_page()

            for keyword in keywords:
                try:
                    posts = await self._search_keyword(page, keyword, limit_per_keyword)
                    all_posts.extend(posts)
                    logger.info(
                        "Facebook '%s' → %d posts scraped", keyword, len(posts)
                    )
                except Exception as e:
                    logger.error("Facebook '%s' scrape failed: %s", keyword, e)

                await asyncio.sleep(self.delay)

            await browser.close()

        logger.info("Facebook total: %d posts from %d keywords",
                     len(all_posts), len(keywords))
        return all_posts

    async def _search_keyword(
        self, page, keyword: str, limit: int
    ) -> List[ScrapedPost]:
        """Search Facebook for a keyword and extract visible posts.

        Args:
            page: Playwright page instance.
            keyword: Search term.
            limit: Max posts to extract.

        Returns:
            List of ScrapedPost.
        """
        query = keyword.replace(" ", "%20")
        url = self.SEARCH_URL.format(query=query)
        posts: List[ScrapedPost] = []

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)
        except Exception as e:
            logger.debug("Failed to load Facebook search for '%s': %s", keyword, e)
            return posts

        # Facebook may show a login wall — try to extract whatever is visible
        try:
            # Look for post-like content divs
            post_elements = await page.query_selector_all(
                "div[data-ad-preview], div[role='article'], "
                "div[class*='userContent'], div[dir='auto']"
            )

            for el in post_elements[:limit]:
                try:
                    text_content = await el.inner_text()
                    if text_content and len(text_content.strip()) > 20:
                        # Try to find a link
                        link_el = await el.query_selector("a[href*='facebook.com']")
                        post_url = ""
                        if link_el:
                            post_url = await link_el.get_attribute("href") or ""

                        # Extract image if present
                        img_el = await el.query_selector("img[src*='fbcdn']")
                        image_url = ""
                        if img_el:
                            image_url = await img_el.get_attribute("src") or ""

                        post = ScrapedPost(
                            source="FACEBOOK",
                            post_url=post_url or f"https://facebook.com/search?q={query}",
                            image_url=image_url,
                            caption_text=text_content.strip()[:2000],
                            username="facebook_public",
                            timestamp=datetime.now().isoformat(),
                        )
                        posts.append(post)
                except Exception:
                    continue

        except Exception as e:
            logger.debug("Facebook content extraction failed: %s", e)

        return posts


# ---------------------------------------------------------------------------
# Telegram Scraper
# ---------------------------------------------------------------------------

TELEGRAM_KEYWORDS = [
    "betting", "investment", "helpline", "scam",
    "ipl betting", "stock tips", "earn money",
    "customer care", "guaranteed return",
]


class TelegramScraper:
    """Scrapes public Telegram channels using Telethon.

    Monitors public channels for scam-related keywords.
    Requires NO authentication for public channels — uses
    the Telegram web preview endpoint as fallback.

    Attributes:
        keywords: Keywords to search for in channel messages.
        delay: Rate limit delay in seconds.
    """

    # Well-known public scam channel name patterns (for discovery)
    CHANNEL_PATTERNS = [
        "betting_tips", "ipl_prediction", "investment_india",
        "earn_money_online", "stock_tips_free", "crypto_signals",
        "customer_care", "helpline_india",
    ]

    WEB_PREVIEW_URL = "https://t.me/s/{channel}"

    def __init__(
        self,
        keywords: Optional[List[str]] = None,
        delay: float = 2.0,
    ):
        """Initialize Telegram scraper.

        Args:
            keywords: Keywords to filter messages. Defaults to built-in list.
            delay: Rate limit delay in seconds.
        """
        self.keywords = keywords or TELEGRAM_KEYWORDS
        self.delay = delay
        self._telethon_available = False
        self._playwright_available = False

        try:
            from telethon import TelegramClient  # noqa: F401
            self._telethon_available = True
        except ImportError:
            logger.info("Telethon not installed — using web preview fallback")

        try:
            from playwright.async_api import async_playwright  # noqa: F401
            self._playwright_available = True
        except ImportError:
            pass

    @property
    def is_available(self) -> bool:
        return self._telethon_available or self._playwright_available

    async def scrape_public_channels(
        self,
        channel_keywords: Optional[List[str]] = None,
        limit_per_channel: int = 10,
    ) -> List[ScrapedPost]:
        """Scrape public Telegram channels for scam content.

        Uses Telethon if available, otherwise falls back to scraping
        the t.me/s/ web preview pages via Playwright.

        Args:
            channel_keywords: Channel name patterns to check.
            limit_per_channel: Max messages per channel.

        Returns:
            List of ScrapedPost from Telegram.
        """
        if self._telethon_available:
            return await self._scrape_via_telethon(channel_keywords, limit_per_channel)
        elif self._playwright_available:
            return await self._scrape_via_web_preview(channel_keywords, limit_per_channel)
        else:
            logger.warning("Telegram scraper unavailable — no Telethon or Playwright")
            return []

    async def _scrape_via_telethon(
        self,
        channel_keywords: Optional[List[str]],
        limit: int,
    ) -> List[ScrapedPost]:
        """Scrape using Telethon client (public channels only).

        Requires TELEGRAM_API_ID and TELEGRAM_API_HASH env vars.
        Falls back to web preview if credentials aren't set.
        """
        api_id = os.getenv("TELEGRAM_API_ID")
        api_hash = os.getenv("TELEGRAM_API_HASH")

        if not api_id or not api_hash:
            logger.info(
                "TELEGRAM_API_ID/HASH not set — falling back to web preview"
            )
            if self._playwright_available:
                return await self._scrape_via_web_preview(channel_keywords, limit)
            return []

        from telethon import TelegramClient
        from telethon.tl.functions.contacts import SearchRequest

        posts: List[ScrapedPost] = []
        keywords = channel_keywords or self.keywords

        session_path = Path("data/.telethon_session")
        session_path.parent.mkdir(parents=True, exist_ok=True)

        client = TelegramClient(
            str(session_path), int(api_id), api_hash
        )

        try:
            await client.start()

            for keyword in keywords:
                try:
                    # Search for public channels
                    result = await client(SearchRequest(
                        q=keyword,
                        limit=3,
                    ))

                    for chat in (result.chats or []):
                        try:
                            async for msg in client.iter_messages(
                                chat, limit=limit
                            ):
                                if msg.text and any(
                                    kw.lower() in msg.text.lower()
                                    for kw in self.keywords
                                ):
                                    post = ScrapedPost(
                                        source="TELEGRAM",
                                        post_url=f"https://t.me/{getattr(chat, 'username', 'channel')}/{msg.id}",
                                        caption_text=msg.text[:2000],
                                        username=getattr(chat, "username", "") or getattr(chat, "title", ""),
                                        timestamp=(msg.date.isoformat() if msg.date else datetime.now().isoformat()),
                                    )
                                    posts.append(post)
                        except Exception as e:
                            logger.debug("Telegram channel read error: %s", e)

                    await asyncio.sleep(self.delay)

                except Exception as e:
                    logger.debug("Telegram search for '%s' failed: %s", keyword, e)

        except Exception as e:
            logger.error("Telethon client error: %s", e)
        finally:
            await client.disconnect()

        logger.info("Telegram (Telethon): %d posts scraped", len(posts))
        return posts

    async def _scrape_via_web_preview(
        self,
        channel_keywords: Optional[List[str]],
        limit: int,
    ) -> List[ScrapedPost]:
        """Scrape Telegram via public web preview pages (t.me/s/).

        No authentication required — works on any public channel
        that has web preview enabled.
        """
        from playwright.async_api import async_playwright

        channels = channel_keywords or self.CHANNEL_PATTERNS
        posts: List[ScrapedPost] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=_random_ua(),
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()

            for channel in channels:
                url = self.WEB_PREVIEW_URL.format(channel=channel)

                try:
                    resp = await page.goto(
                        url, wait_until="domcontentloaded", timeout=12000
                    )
                    if resp and resp.status == 200:
                        await page.wait_for_timeout(2000)

                        # Extract message divs
                        messages = await page.query_selector_all(
                            ".tgme_widget_message_text, "
                            ".tgme_widget_message_wrap"
                        )

                        for msg_el in messages[:limit]:
                            try:
                                text = await msg_el.inner_text()
                                if text and len(text.strip()) > 10:
                                    # Check keyword relevance
                                    text_lower = text.lower()
                                    if any(kw.lower() in text_lower for kw in self.keywords):
                                        # Try to get message link
                                        link_el = await msg_el.query_selector(
                                            "a.tgme_widget_message_date"
                                        )
                                        msg_url = ""
                                        if link_el:
                                            msg_url = await link_el.get_attribute("href") or ""

                                        # Try to get image
                                        img_el = await msg_el.query_selector(
                                            "a.tgme_widget_message_photo_wrap"
                                        )
                                        image_url = ""
                                        if img_el:
                                            style = await img_el.get_attribute("style") or ""
                                            # Extract URL from background-image style
                                            if "url(" in style:
                                                start = style.index("url(") + 5
                                                end = style.index(")", start) - 1
                                                image_url = style[start:end].strip("'\"")

                                        post = ScrapedPost(
                                            source="TELEGRAM",
                                            post_url=msg_url or url,
                                            image_url=image_url,
                                            caption_text=text.strip()[:2000],
                                            username=channel,
                                            timestamp=datetime.now().isoformat(),
                                        )
                                        posts.append(post)
                            except Exception:
                                continue

                    logger.info("Telegram web preview @%s → %d relevant msgs",
                                channel, sum(1 for p in posts if p.username == channel))

                except Exception as e:
                    logger.debug("Telegram web preview @%s failed: %s", channel, e)

                await asyncio.sleep(self.delay)

            await browser.close()

        logger.info("Telegram (web preview): %d posts scraped", len(posts))
        return posts


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _parse_count(text: str) -> int:
    """Parse engagement count strings like '1.2K', '5M', '432'."""
    text = text.strip().replace(",", "").lower()
    try:
        if "k" in text:
            return int(float(text.replace("k", "")) * 1000)
        elif "m" in text:
            return int(float(text.replace("m", "")) * 1_000_000)
        else:
            return int(text)
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------------------
# Manager — Orchestrator
# ---------------------------------------------------------------------------

class SocialScraperManager:
    """Orchestrates all social media scrapers with deduplication.

    Runs Instagram, Facebook, and Telegram scrapers, merges results,
    deduplicates by URL hash, and persists to disk.

    Attributes:
        instagram: InstagramScraper instance.
        facebook: FacebookScraper instance.
        telegram: TelegramScraper instance.
    """

    def __init__(self, delay: float = 2.0):
        """Initialize all sub-scrapers.

        Args:
            delay: Rate limit delay in seconds (passed to all scrapers).
        """
        self.instagram = InstagramScraper(delay=delay)
        self.facebook = FacebookScraper(delay=delay)
        self.telegram = TelegramScraper(delay=delay)
        self._seen_hashes: Set[str] = set()
        self._all_posts: List[ScrapedPost] = []

        # Load previously scraped posts for deduplication
        self._load_existing()

        logger.info(
            "SocialScraperManager initialized — "
            "IG=%s FB=%s TG=%s (%d existing posts loaded)",
            self.instagram.is_available,
            self.facebook.is_available,
            self.telegram.is_available,
            len(self._seen_hashes),
        )

    def _load_existing(self) -> None:
        """Load previously scraped posts for dedup tracking."""
        if SCRAPED_OUTPUT.exists():
            try:
                with open(SCRAPED_OUTPUT, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                for item in existing:
                    h = hashlib.sha256(
                        item.get("post_url", "").encode()
                    ).hexdigest()[:16]
                    self._seen_hashes.add(h)
                logger.info("Loaded %d existing post hashes for dedup", len(self._seen_hashes))
            except Exception as e:
                logger.debug("Could not load existing scraped posts: %s", e)

    async def fetch_all(
        self,
        limit_per_source: int = 20,
    ) -> List[ScrapedPost]:
        """Run all scrapers and merge results with deduplication.

        Args:
            limit_per_source: Max posts from each platform.

        Returns:
            Deduplicated list of ScrapedPost across all sources.
        """
        all_posts: List[ScrapedPost] = []
        errors: List[str] = []

        # Instagram
        if self.instagram.is_available:
            try:
                ig_posts = await self.instagram.scrape_public_posts(
                    limit_per_tag=max(1, limit_per_source // len(ALL_INSTAGRAM_HASHTAGS)),
                )
                all_posts.extend(ig_posts)
                logger.info("Instagram: %d posts", len(ig_posts))
            except Exception as e:
                errors.append(f"Instagram: {e}")
                logger.error("Instagram scraper failed: %s", e)

        # Facebook
        if self.facebook.is_available:
            try:
                fb_posts = await self.facebook.scrape_public_pages(
                    limit_per_keyword=max(1, limit_per_source // len(FACEBOOK_KEYWORDS)),
                )
                all_posts.extend(fb_posts)
                logger.info("Facebook: %d posts", len(fb_posts))
            except Exception as e:
                errors.append(f"Facebook: {e}")
                logger.error("Facebook scraper failed: %s", e)

        # Telegram
        if self.telegram.is_available:
            try:
                tg_posts = await self.telegram.scrape_public_channels(
                    limit_per_channel=max(1, limit_per_source // len(TELEGRAM_KEYWORDS)),
                )
                all_posts.extend(tg_posts)
                logger.info("Telegram: %d posts", len(tg_posts))
            except Exception as e:
                errors.append(f"Telegram: {e}")
                logger.error("Telegram scraper failed: %s", e)

        # Deduplicate
        unique_posts = self._deduplicate(all_posts)

        # Save
        self._save(unique_posts)

        if errors:
            logger.warning("Scraper errors: %s", "; ".join(errors))

        logger.info(
            "SocialScraperManager: %d total → %d unique (dedup removed %d)",
            len(all_posts), len(unique_posts), len(all_posts) - len(unique_posts),
        )
        return unique_posts

    def _deduplicate(self, posts: List[ScrapedPost]) -> List[ScrapedPost]:
        """Remove duplicate posts by URL hash.

        Args:
            posts: Raw list of scraped posts.

        Returns:
            Deduplicated list.
        """
        unique = []
        for post in posts:
            h = post.url_hash()
            if h not in self._seen_hashes:
                self._seen_hashes.add(h)
                unique.append(post)
        return unique

    def _save(self, posts: List[ScrapedPost]) -> None:
        """Persist scraped posts to JSON file.

        Args:
            posts: List of new posts to append.
        """
        if not posts:
            return

        # Load existing
        existing: List[dict] = []
        if SCRAPED_OUTPUT.exists():
            try:
                with open(SCRAPED_OUTPUT, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass

        # Append new
        existing.extend([p.to_dict() for p in posts])

        # Write
        SCRAPED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with open(SCRAPED_OUTPUT, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        logger.info("Saved %d new posts → %s (total: %d)",
                     len(posts), SCRAPED_OUTPUT, len(existing))

    @property
    def total_scraped(self) -> int:
        """Total unique posts seen."""
        return len(self._seen_hashes)

    @property
    def sources_available(self) -> Dict[str, bool]:
        """Which scrapers are available."""
        return {
            "instagram": self.instagram.is_available,
            "facebook": self.facebook.is_available,
            "telegram": self.telegram.is_available,
        }

    def get_recent_posts(self, limit: int = 20) -> List[ScrapedPost]:
        """Get recently scraped posts from the saved file.

        Args:
            limit: Max posts to return.

        Returns:
            List of ScrapedPost (most recent first).
        """
        if not SCRAPED_OUTPUT.exists():
            return []

        try:
            with open(SCRAPED_OUTPUT, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Return most recent first
            recent = data[-limit:][::-1]
            return [ScrapedPost(**item) for item in recent]
        except Exception as e:
            logger.error("Failed to read recent posts: %s", e)
            return []
