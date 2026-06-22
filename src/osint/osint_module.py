"""
CyberLens — OSINT Module
============================
Open Source Intelligence enrichment for entities.

Modules:
  1. WHOIS lookup for suspicious domains
  2. Google Safe Browsing API for URL checking
  3. Phone number carrier lookup (via TRAI data)
  4. Domain age / reputation scoring

Author: CyberLens Team — GPCSSI India
"""

import json
import logging
import os
import re
import socket
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cyberlens.osint")


@dataclass
class WhoisResult:
    """WHOIS lookup result for a domain."""
    domain: str
    registrar: str
    creation_date: str
    expiration_date: str
    name_servers: List[str]
    registrant_country: str
    registrant_org: str
    domain_age_days: int
    suspicious_indicators: List[str]
    risk_score: float  # 0-100


@dataclass
class URLSafetyResult:
    """Google Safe Browsing API result."""
    url: str
    is_safe: bool
    threats: List[str]       # MALWARE / SOCIAL_ENGINEERING / UNWANTED_SOFTWARE
    checked_at: str
    source: str              # google_safe_browsing / local_heuristic


@dataclass
class PhoneLookupResult:
    """Phone number carrier and location info."""
    phone: str
    carrier: str
    circle: str              # Telecom circle (Mumbai, Delhi, etc.)
    operator: str
    number_type: str         # MOBILE / LANDLINE / VoIP
    risk_indicators: List[str]


class OSINTModule:
    """Open Source Intelligence enrichment."""

    def __init__(self):
        self._safe_browsing_key = os.getenv("GOOGLE_SAFE_BROWSING_KEY", "")

    def whois_lookup(self, domain: str) -> WhoisResult:
        """WHOIS lookup for a domain.

        Args:
            domain: Domain name to look up.

        Returns:
            WhoisResult with registration info and risk score.
        """
        # Clean domain
        domain = domain.lower().strip()
        if domain.startswith("http"):
            domain = domain.split("//")[-1].split("/")[0]

        try:
            import whois
            w = whois.whois(domain)

            creation = w.creation_date
            if isinstance(creation, list):
                creation = creation[0]
            expiration = w.expiration_date
            if isinstance(expiration, list):
                expiration = expiration[0]

            age = (datetime.now() - creation).days if creation else 0
            ns = w.name_servers or []
            if isinstance(ns, str):
                ns = [ns]

            indicators = []
            risk = 0.0

            # Suspicious indicators
            if age < 30:
                indicators.append("Domain less than 30 days old")
                risk += 30
            if age < 90:
                indicators.append("Domain less than 90 days old")
                risk += 15
            if w.registrar and "privacy" in str(w.registrar).lower():
                indicators.append("Privacy-protected registrant")
                risk += 10
            if w.registrant_country and w.registrant_country not in ("IN", "India"):
                indicators.append(f"Registered outside India ({w.registrant_country})")
                risk += 15
            if any(kw in domain for kw in ["invest", "money", "earn", "win", "bet", "stock"]):
                indicators.append("Scam keywords in domain name")
                risk += 20

            return WhoisResult(
                domain=domain,
                registrar=str(w.registrar or "Unknown"),
                creation_date=str(creation) if creation else "Unknown",
                expiration_date=str(expiration) if expiration else "Unknown",
                name_servers=[str(s) for s in ns],
                registrant_country=str(w.registrant_country or "Unknown"),
                registrant_org=str(getattr(w, "org", "") or "Unknown"),
                domain_age_days=age,
                suspicious_indicators=indicators,
                risk_score=min(100, risk),
            )

        except ImportError:
            logger.info("python-whois not installed — using socket DNS fallback")
            return self._dns_fallback(domain)
        except Exception as e:
            logger.warning("WHOIS lookup failed for %s: %s", domain, e)
            return self._dns_fallback(domain)

    def check_url_safety(self, url: str) -> URLSafetyResult:
        """Check URL against Google Safe Browsing API.

        Args:
            url: Full URL to check.

        Returns:
            URLSafetyResult with threat information.
        """
        now = datetime.now().isoformat()

        if self._safe_browsing_key:
            try:
                import requests as http
                payload = {
                    "client": {"clientId": "cyberlens", "clientVersion": "3.0"},
                    "threatInfo": {
                        "threatTypes": [
                            "MALWARE", "SOCIAL_ENGINEERING",
                            "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION",
                        ],
                        "platformTypes": ["ANY_PLATFORM"],
                        "threatEntryTypes": ["URL"],
                        "threatEntries": [{"url": url}],
                    },
                }
                resp = http.post(
                    f"https://safebrowsing.googleapis.com/v4/threatMatches:find"
                    f"?key={self._safe_browsing_key}",
                    json=payload,
                    timeout=10,
                )
                data = resp.json()
                matches = data.get("matches", [])
                threats = [m.get("threatType", "") for m in matches]

                return URLSafetyResult(
                    url=url, is_safe=len(matches) == 0,
                    threats=threats, checked_at=now,
                    source="google_safe_browsing",
                )
            except Exception as e:
                logger.warning("Safe Browsing API failed: %s", e)

        # Fallback: heuristic check
        return self._heuristic_url_check(url, now)

    def phone_lookup(self, phone: str) -> PhoneLookupResult:
        """Look up phone number carrier and telecom circle.

        Args:
            phone: Indian mobile number (+91XXXXXXXXXX).

        Returns:
            PhoneLookupResult with carrier and risk info.
        """
        # Normalize
        phone = phone.replace(" ", "").replace("-", "")
        if phone.startswith("+91"):
            phone_digits = phone[3:]
        elif phone.startswith("91") and len(phone) > 10:
            phone_digits = phone[2:]
        else:
            phone_digits = phone

        if len(phone_digits) != 10:
            return PhoneLookupResult(
                phone=phone, carrier="Unknown", circle="Unknown",
                operator="Unknown", number_type="UNKNOWN",
                risk_indicators=["Invalid phone number format"],
            )

        # Prefix-based carrier detection (Indian mobile numbering plan)
        prefix = phone_digits[:4]
        first_digit = phone_digits[0]

        carrier, operator = self._detect_carrier(prefix, first_digit)
        circle = self._detect_circle(prefix)
        risk = []

        # Check for known scam patterns
        if circle in ("Jharkhand", "Bihar"):
            risk.append(f"High-risk telecom circle: {circle} (Jamtara belt)")
        if carrier == "VoIP":
            risk.append("VoIP number — commonly used in scam operations")

        return PhoneLookupResult(
            phone=phone, carrier=carrier, circle=circle,
            operator=operator,
            number_type="MOBILE" if first_digit in "6789" else "LANDLINE",
            risk_indicators=risk,
        )

    def enrich_entity(self, value: str, entity_type: str) -> Dict[str, Any]:
        """One-stop entity enrichment.

        Args:
            value: Entity value (phone/domain/URL/UPI).
            entity_type: PHONE / DOMAIN / URL / UPI.

        Returns:
            Enrichment results dict.
        """
        if entity_type == "PHONE":
            result = self.phone_lookup(value)
            return {"type": "phone", "result": result.__dict__}
        elif entity_type == "DOMAIN":
            result = self.whois_lookup(value)
            return {"type": "domain", "result": result.__dict__}
        elif entity_type == "URL":
            safety = self.check_url_safety(value)
            # Also WHOIS the domain
            domain = value.split("//")[-1].split("/")[0] if "//" in value else value
            whois_r = self.whois_lookup(domain)
            return {
                "type": "url",
                "safety": safety.__dict__,
                "whois": whois_r.__dict__,
            }
        elif entity_type == "UPI":
            bank = self._detect_upi_bank(value)
            return {"type": "upi", "bank": bank, "value": value}
        else:
            return {"type": entity_type, "value": value, "enrichment": "not_available"}

    # ── Private helpers ───────────────────────────────────────────────

    def _dns_fallback(self, domain: str) -> WhoisResult:
        """Basic DNS-based domain check when whois is unavailable."""
        indicators = []
        risk = 0.0
        try:
            ip = socket.gethostbyname(domain)
            indicators.append(f"Resolves to {ip}")
        except socket.gaierror:
            indicators.append("Domain does not resolve (possibly dead)")
            risk += 20

        if any(kw in domain for kw in ["invest", "money", "earn", "win", "bet"]):
            indicators.append("Scam keywords in domain")
            risk += 25

        return WhoisResult(
            domain=domain, registrar="Unknown (whois unavailable)",
            creation_date="Unknown", expiration_date="Unknown",
            name_servers=[], registrant_country="Unknown",
            registrant_org="Unknown", domain_age_days=0,
            suspicious_indicators=indicators, risk_score=min(100, risk),
        )

    def _heuristic_url_check(self, url: str, now: str) -> URLSafetyResult:
        """Heuristic URL safety check (no API key needed)."""
        threats = []

        # Check for URL shorteners
        shorteners = ["bit.ly", "tinyurl.com", "is.gd", "goo.gl", "t.co", "rb.gy", "shorturl.at"]
        domain = url.split("//")[-1].split("/")[0].lower()
        if domain in shorteners:
            threats.append("URL_SHORTENER")

        # Scam keywords
        url_lower = url.lower()
        scam_words = ["invest", "earn", "money", "withdraw", "profit", "guaranteed", "double"]
        if any(w in url_lower for w in scam_words):
            threats.append("SCAM_KEYWORDS")

        # Suspicious TLDs
        if domain.endswith((".xyz", ".top", ".work", ".click", ".buzz", ".gq", ".ml")):
            threats.append("SUSPICIOUS_TLD")

        # Excessive subdomains
        if domain.count(".") > 3:
            threats.append("EXCESSIVE_SUBDOMAINS")

        return URLSafetyResult(
            url=url, is_safe=len(threats) == 0,
            threats=threats, checked_at=now,
            source="local_heuristic",
        )

    @staticmethod
    def _detect_carrier(prefix: str, first_digit: str) -> tuple:
        """Detect carrier from number prefix (simplified)."""
        jio_prefixes = {"6000", "6001", "6002", "6003", "6004", "6005", "7000", "7001"}
        airtel_starts = {"70", "73", "74", "75", "80", "81"}
        vi_starts = {"62", "63", "77", "78", "82", "83", "84", "85", "86", "87"}

        p2 = prefix[:2]
        if prefix in jio_prefixes or p2 in ("60", "61", "71"):
            return "Jio", "Reliance Jio"
        elif p2 in airtel_starts:
            return "Airtel", "Bharti Airtel"
        elif p2 in vi_starts:
            return "Vi", "Vodafone Idea"
        elif p2 in ("90", "91", "92", "93", "94", "95"):
            return "BSNL/MTNL", "BSNL/MTNL"
        return "Unknown", "Unknown"

    @staticmethod
    def _detect_circle(prefix: str) -> str:
        """Detect telecom circle from prefix (simplified mapping)."""
        circle_map = {
            "98": "Delhi", "99": "Delhi", "70": "Mumbai",
            "80": "Karnataka", "94": "Tamil Nadu",
            "63": "Jharkhand", "83": "Bihar",
        }
        return circle_map.get(prefix[:2], "Unknown")

    @staticmethod
    def _detect_upi_bank(upi_id: str) -> str:
        handle = upi_id.split("@")[-1].lower() if "@" in upi_id else ""
        bank_map = {
            "paytm": "Paytm Payments Bank", "gpay": "Google Pay",
            "oksbi": "SBI", "okaxis": "Axis Bank", "ybl": "PhonePe",
            "okhdfcbank": "HDFC Bank", "okicici": "ICICI Bank",
        }
        return bank_map.get(handle, f"Unknown ({handle})")
