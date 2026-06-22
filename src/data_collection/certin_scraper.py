"""
CyberLens — CERT-In Alert Scraper
=====================================
Scrapes cert-in.org.in public alerts for ground-truth
malicious infrastructure data.

Extracts domains, IPs, UPI patterns, and infrastructure
indicators from CERT-In public advisories and alerts.

Author: CyberLens Team — GPCSSI Internship
"""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cyberlens.data_collection.certin")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CERTInAlert:
    """A single CERT-In public alert."""
    alert_id: str = ""
    alert_date: str = ""
    title: str = ""
    severity: str = ""  # HIGH, MEDIUM, LOW, CRITICAL
    content: str = ""
    domains: List[str] = field(default_factory=list)
    ips: List[str] = field(default_factory=list)
    upi_patterns: List[str] = field(default_factory=list)
    infrastructure_indicators: List[str] = field(default_factory=list)
    cve_ids: List[str] = field(default_factory=list)
    label: str = "CONFIRMED_MALICIOUS"
    source: str = "CERT-In"
    source_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Extraction regexes
# ---------------------------------------------------------------------------

RE_DOMAIN = re.compile(
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+"
    r"(?:com|in|org|net|co\.in|io|xyz|online|site|info|biz|club|tech|top)\b"
)

RE_IP = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)

RE_UPI = re.compile(
    r"[a-zA-Z0-9._\-]+@(?:upi|paytm|oksbi|okaxis|okicici|okhdfcbank|"
    r"ybl|ibl|axl|sbi|icici|hdfc|kotak|apl|boi|citi|indus|"
    r"freecharge|phonepe|gpay|amazonpay)\b",
    re.IGNORECASE,
)

RE_CVE = re.compile(r"CVE-\d{4}-\d{4,}", re.IGNORECASE)

RE_URL = re.compile(r"https?://[^\s<>\"']+")

# Severity keywords
SEVERITY_MAP = {
    "CRITICAL": ["critical", "urgent", "emergency", "zero-day", "0-day"],
    "HIGH": ["high", "important", "severe"],
    "MEDIUM": ["medium", "moderate"],
    "LOW": ["low", "informational"],
}


def _detect_severity(text: str) -> str:
    """Detect alert severity from text.

    Args:
        text: Alert text content.

    Returns:
        Severity level string.
    """
    text_lower = text.lower()
    for level, keywords in SEVERITY_MAP.items():
        if any(kw in text_lower for kw in keywords):
            return level
    return "MEDIUM"


# ---------------------------------------------------------------------------
# CERTInScraper
# ---------------------------------------------------------------------------


class CERTInScraper:
    """Scrapes CERT-In public alerts for malicious infrastructure data.

    Uses Playwright to navigate cert-in.org.in public pages and
    extract domains, IPs, UPI patterns, and IOCs.

    Attributes:
        output_path: Path to save ground truth JSON.
    """

    ALERT_URLS = [
        "https://www.cert-in.org.in/s2cMainServlet?pageid=PUBVLNOTES01",
        "https://www.cert-in.org.in/s2cMainServlet?pageid=PUBADVS01",
    ]

    def __init__(
        self,
        output_path: str = "data/ground_truth/certin_alerts.json",
    ):
        """Initialize the scraper.

        Args:
            output_path: Path to save scraped alerts.
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

    async def scrape_alerts(self) -> List[CERTInAlert]:
        """Scrape CERT-In public alerts.

        Returns:
            List of CERTInAlert with extracted IOCs.
        """
        if not self._available:
            logger.error("Playwright not available — cannot scrape CERT-In")
            return []

        from playwright.async_api import async_playwright

        alerts: List[CERTInAlert] = []

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

            for url in self.ALERT_URLS:
                try:
                    logger.info("Scraping CERT-In page: %s", url)
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(3000)

                    # Try multiple selectors for alert list items
                    selectors = [
                        "table tbody tr",
                        ".alert-item",
                        ".advisory-item",
                        "div[class*='vuln']",
                        "div[class*='advisory']",
                        "article",
                        "li",
                    ]

                    elements = []
                    for sel in selectors:
                        elements = await page.query_selector_all(sel)
                        if len(elements) > 2:
                            break

                    if not elements:
                        # Fallback: extract from full page text
                        body_text = await page.inner_text("body")
                        if body_text and len(body_text.strip()) > 100:
                            alert = self._parse_text_alert(body_text, url, 0)
                            if alert:
                                alerts.append(alert)
                        continue

                    for idx, el in enumerate(elements[:100]):
                        try:
                            text = await el.inner_text()
                            if text and len(text.strip()) > 20:
                                alert = self._parse_text_alert(
                                    text, url, idx
                                )
                                if alert:
                                    alerts.append(alert)
                        except Exception:
                            continue

                    logger.info(
                        "Extracted %d alerts from %s",
                        len(alerts), url,
                    )

                except Exception as e:
                    logger.error("Failed to scrape %s: %s", url, e)

            await browser.close()

        # Save
        self._save(alerts)
        logger.info("Total CERT-In alerts collected: %d", len(alerts))
        return alerts

    def _parse_text_alert(
        self, text: str, source_url: str, idx: int
    ) -> Optional[CERTInAlert]:
        """Parse alert text into CERTInAlert.

        Args:
            text: Raw text from the alert element.
            source_url: Source page URL.
            idx: Element index.

        Returns:
            CERTInAlert or None if insufficient content.
        """
        text = text.strip()
        if len(text) < 20:
            return None

        # Extract IOCs
        domains = list(set(RE_DOMAIN.findall(text)))
        ips = list(set(RE_IP.findall(text)))
        upis = list(set(RE_UPI.findall(text)))
        urls = list(set(RE_URL.findall(text)))
        cves = list(set(RE_CVE.findall(text)))

        # Filter out CERT-In's own domains
        domains = [
            d for d in domains
            if "cert-in.org" not in d
            and "gov.in" not in d
            and "nic.in" not in d
        ]

        # Build infrastructure indicators
        indicators = []
        for d in domains[:20]:
            indicators.append(f"domain:{d}")
        for ip in ips[:20]:
            indicators.append(f"ip:{ip}")
        for u in urls[:10]:
            indicators.append(f"url:{u}")

        severity = _detect_severity(text)

        # Title: first line
        lines = text.split("\n")
        title = lines[0].strip()[:200] if lines else text[:200]

        return CERTInAlert(
            alert_id=f"CERTIN-{idx:04d}",
            alert_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            title=title,
            severity=severity,
            content=text[:3000],
            domains=domains[:50],
            ips=ips[:50],
            upi_patterns=upis[:20],
            infrastructure_indicators=indicators[:50],
            cve_ids=cves[:10],
            source_url=source_url,
        )

    def _save(self, alerts: List[CERTInAlert]) -> None:
        """Save alerts to JSON.

        Args:
            alerts: List of parsed alerts.
        """
        data = [a.to_dict() for a in alerts]
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Saved %d alerts -> %s", len(data), self.output_path)
