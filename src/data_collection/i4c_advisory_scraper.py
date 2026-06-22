"""
CyberLens — I4C Advisory Scraper
====================================
Scrapes cybercrime.gov.in public advisories for ground-truth data
on what I4C actually blocks and why.

Extracts blocked URLs, domains, channels, violation types, and
IT Act sections from public advisory pages.

Author: CyberLens Team — GPCSSI Internship
"""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cyberlens.data_collection.i4c")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class BlockedEntity:
    """A single entity confirmed blocked by I4C."""
    entity_value: str = ""
    entity_type: str = ""  # URL, DOMAIN, CHANNEL, PHONE, UPI
    label: str = "CONFIRMED_BLOCKED"
    blocked_date: str = ""
    reason: str = ""
    advisory_source: str = ""
    it_act_section: str = ""


@dataclass
class I4CAdvisory:
    """A single I4C public advisory."""
    advisory_id: str = ""
    advisory_date: str = ""
    title: str = ""
    content: str = ""
    blocked_urls: List[str] = field(default_factory=list)
    blocked_domains: List[str] = field(default_factory=list)
    blocked_channels: List[str] = field(default_factory=list)
    violation_type: str = ""
    it_act_section: str = ""
    source_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Entity extraction from advisory text
# ---------------------------------------------------------------------------

RE_URL = re.compile(r"https?://[^\s<>\"']+")
RE_DOMAIN = re.compile(
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+"
    r"(?:com|in|org|net|co\.in|io|xyz|online|site|info|biz|club)\b"
)
RE_TELEGRAM = re.compile(r"(?:https?://)?t\.me/[a-zA-Z0-9_]+")

# IT Act sections mentioned in advisories
RE_IT_ACT = re.compile(
    r"(?:IT\s*Act|Information\s*Technology\s*Act)\s*"
    r"(?:,?\s*(?:Section|§|Sec\.?)\s*\d+[A-Z]?(?:\s*[/&]\s*\d+[A-Z]?)*)",
    re.IGNORECASE,
)


def _classify_violation(text: str) -> str:
    """Classify advisory violation type from text content.

    Args:
        text: Advisory text content.

    Returns:
        Violation type string.
    """
    text_lower = text.lower()

    violation_map = {
        "FINANCIAL_FRAUD": [
            "investment", "ponzi", "trading", "stock", "crypto",
            "loan", "financial fraud", "money doubling",
        ],
        "BETTING_GAMBLING": [
            "betting", "gambling", "satta", "matka", "cricket",
            "casino", "rummy",
        ],
        "IMPERSONATION": [
            "impersonat", "fake customer care", "fake helpline",
            "digital arrest", "fake officer",
        ],
        "SEXTORTION": [
            "sextortion", "blackmail", "intimate", "morphed",
        ],
        "CHILD_EXPLOITATION": [
            "child", "minor", "csam", "pocso",
        ],
        "DRUG_TRAFFICKING": [
            "drug", "narcotic", "ndps",
        ],
        "PIRACY": [
            "piracy", "copyright", "pirated", "torrent",
        ],
        "FAKE_APP": [
            "fake app", "malicious app", "rogue app",
        ],
    }

    for vtype, keywords in violation_map.items():
        if any(kw in text_lower for kw in keywords):
            return vtype

    return "OTHER"


# ---------------------------------------------------------------------------
# I4CAdvisoryScraper
# ---------------------------------------------------------------------------


class I4CAdvisoryScraper:
    """Scrapes I4C public advisories from cybercrime.gov.in.

    Uses Playwright to navigate the public advisory pages and
    extract structured data about blocked entities.

    Attributes:
        output_path: Path to save ground truth JSON.
    """

    BASE_URL = "https://cybercrime.gov.in"
    ADVISORY_URLS = [
        "https://cybercrime.gov.in/Webpages/Advisories.aspx",
        "https://cybercrime.gov.in/Webpages/Awareness.aspx",
    ]

    def __init__(
        self,
        output_path: str = "data/ground_truth/i4c_advisories.json",
    ):
        """Initialize the scraper.

        Args:
            output_path: Path to save scraped advisories.
        """
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._available = False

        try:
            from playwright.async_api import async_playwright  # noqa: F401
            self._available = True
        except ImportError:
            logger.warning(
                "Playwright not installed. "
                "Install: pip install playwright && playwright install chromium"
            )

    @property
    def is_available(self) -> bool:
        """Whether Playwright is available."""
        return self._available

    async def scrape_advisories(self) -> List[I4CAdvisory]:
        """Scrape I4C public advisories.

        Returns:
            List of I4CAdvisory with extracted entities.
        """
        if not self._available:
            logger.error("Playwright not available — cannot scrape I4C")
            return []

        from playwright.async_api import async_playwright

        advisories: List[I4CAdvisory] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
                locale="en-IN",
            )
            page = await context.new_page()

            for url in self.ADVISORY_URLS:
                try:
                    logger.info("Scraping I4C advisory page: %s", url)
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(3000)

                    # Extract advisory cards / list items
                    selectors = [
                        ".advisory-card",
                        ".card-body",
                        "article",
                        ".panel-body",
                        "div[class*='advisory']",
                        "div[class*='awareness']",
                        "table tbody tr",
                        ".content-area div",
                    ]

                    elements = []
                    for sel in selectors:
                        elements = await page.query_selector_all(sel)
                        if elements:
                            break

                    if not elements:
                        # Fallback: get all text blocks on the page
                        body_text = await page.inner_text("body")
                        if body_text and len(body_text.strip()) > 100:
                            advisory = self._parse_text_advisory(
                                body_text, url
                            )
                            if advisory:
                                advisories.append(advisory)
                        continue

                    for idx, el in enumerate(elements[:50]):
                        try:
                            text = await el.inner_text()
                            if text and len(text.strip()) > 30:
                                advisory = self._parse_text_advisory(
                                    text, url, idx
                                )
                                if advisory:
                                    advisories.append(advisory)
                        except Exception:
                            continue

                    logger.info(
                        "Extracted %d advisories from %s",
                        len(advisories), url,
                    )

                except Exception as e:
                    logger.error("Failed to scrape %s: %s", url, e)

            await browser.close()

        # Save
        self._save(advisories)
        logger.info("Total I4C advisories collected: %d", len(advisories))
        return advisories

    def _parse_text_advisory(
        self, text: str, source_url: str, idx: int = 0
    ) -> Optional[I4CAdvisory]:
        """Parse a text block into an I4CAdvisory.

        Args:
            text: Raw text from the advisory element.
            source_url: URL where this was found.
            idx: Index of the element on the page.

        Returns:
            I4CAdvisory or None if insufficient content.
        """
        text = text.strip()
        if len(text) < 30:
            return None

        # Extract entities
        urls = RE_URL.findall(text)
        domains = RE_DOMAIN.findall(text)
        tg_channels = RE_TELEGRAM.findall(text)
        it_act = RE_IT_ACT.findall(text)
        violation = _classify_violation(text)

        # Filter out I4C's own domains
        domains = [
            d for d in domains
            if "cybercrime.gov.in" not in d
            and "cert-in.org" not in d
        ]

        # Extract title (first line or first 100 chars)
        lines = text.split("\n")
        title = lines[0].strip()[:150] if lines else text[:150]

        return I4CAdvisory(
            advisory_id=f"I4C-ADV-{idx:04d}",
            advisory_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            title=title,
            content=text[:3000],
            blocked_urls=urls[:50],
            blocked_domains=domains[:50],
            blocked_channels=[
                c.replace("https://t.me/", "").replace("http://t.me/", "")
                for c in tg_channels
            ],
            violation_type=violation,
            it_act_section="; ".join(it_act[:5]),
            source_url=source_url,
        )

    def parse_advisory_entities(
        self, advisory: I4CAdvisory
    ) -> List[BlockedEntity]:
        """Extract confirmed blocked entities from an advisory.

        Args:
            advisory: Parsed I4CAdvisory.

        Returns:
            List of BlockedEntity with CONFIRMED_BLOCKED label.
        """
        entities: List[BlockedEntity] = []

        for url in advisory.blocked_urls:
            entities.append(BlockedEntity(
                entity_value=url,
                entity_type="URL",
                blocked_date=advisory.advisory_date,
                reason=advisory.violation_type,
                advisory_source=advisory.advisory_id,
                it_act_section=advisory.it_act_section,
            ))

        for domain in advisory.blocked_domains:
            entities.append(BlockedEntity(
                entity_value=domain,
                entity_type="DOMAIN",
                blocked_date=advisory.advisory_date,
                reason=advisory.violation_type,
                advisory_source=advisory.advisory_id,
                it_act_section=advisory.it_act_section,
            ))

        for channel in advisory.blocked_channels:
            entities.append(BlockedEntity(
                entity_value=channel,
                entity_type="CHANNEL",
                blocked_date=advisory.advisory_date,
                reason=advisory.violation_type,
                advisory_source=advisory.advisory_id,
                it_act_section=advisory.it_act_section,
            ))

        return entities

    def _save(self, advisories: List[I4CAdvisory]) -> None:
        """Save advisories to JSON.

        Args:
            advisories: List of parsed advisories.
        """
        data = [a.to_dict() for a in advisories]
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Saved %d advisories -> %s", len(data), self.output_path)
