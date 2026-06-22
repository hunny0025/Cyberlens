"""
CyberLens — Entity Parser (Upgraded)
========================================
Extracts structured entities from OCR text with advanced patterns
for disguised numbers, word-form numbers, Telegram/WhatsApp links,
and investment promise detection in Hindi/English.

Author: CyberLens Team — GPCSSI Internship
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

logger = logging.getLogger("cyberlens.ocr.entity_parser")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PhoneNumber:
    """Parsed phone number with metadata."""
    raw: str
    normalized: str  # +91-XXXXXXXXXX
    format_type: str  # STANDARD, DISGUISED, WORD_FORM, WHATSAPP_LINK
    confidence: float = 1.0

    def __str__(self) -> str:
        return self.normalized


@dataclass
class InvestmentPromise:
    """Detected investment/scam promise."""
    text: str
    promise_type: str  # RETURN_PERCENT, DOUBLE_MONEY, GUARANTEED, DAILY_EARNING
    language: str  # ENGLISH, HINDI, HINGLISH


@dataclass
class EntityResult:
    """Structured entities extracted from OCR text."""
    phones: List[str] = field(default_factory=list)
    phone_details: List[PhoneNumber] = field(default_factory=list)
    upi_ids: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    bank_accounts: List[str] = field(default_factory=list)
    ifsc_codes: List[str] = field(default_factory=list)
    amounts: List[str] = field(default_factory=list)
    telegram_links: List[str] = field(default_factory=list)
    whatsapp_groups: List[str] = field(default_factory=list)
    investment_promises: List[str] = field(default_factory=list)
    promise_details: List[InvestmentPromise] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Word-form number mapping
# ---------------------------------------------------------------------------

WORD_TO_DIGIT: Dict[str, str] = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    # Hindi
    "shunya": "0", "ek": "1", "do": "2", "teen": "3", "char": "4",
    "paanch": "5", "panch": "5", "chhah": "6", "chhe": "6", "saat": "7",
    "sat": "7", "aath": "8", "aat": "8", "nau": "9", "noh": "9",
    # Common OCR misreads
    "o": "0", "oh": "0", "l": "1", "i": "1",
}


class EntityParser:
    """Extracts Indian-format entities from OCR-extracted text.

    Handles standard and disguised formats designed to bypass moderation.
    """

    # ── Phone patterns ────────────────────────────────────────────────────

    # Standard Indian phone: +91/91/0 prefix + 10 digits
    PHONE_STANDARD = re.compile(
        r"""
        (?:
            (?:\+91|91|0)       # Country/trunk prefix
            [-.\s]?             # Optional separator
        )?
        [6-9]\d{9}              # 10-digit mobile (starts 6-9)
        """,
        re.VERBOSE,
    )

    # Disguised phone: 98+OO+12+34+56 or 98 OO 12 34 56
    PHONE_DISGUISED = re.compile(
        r"""
        [6-9]                       # Starts with 6-9
        [\d\sOoIl+\-_.]{10,25}      # Mix of digits, O/I substitutions, separators
        """,
        re.VERBOSE,
    )

    # WhatsApp link: wa.me/91XXXXXXXXXX
    PHONE_WHATSAPP = re.compile(
        r"wa\.me/(?:91)?(\d{10})",
        re.IGNORECASE,
    )

    # Word-form: "call nine eight zero zero..."
    PHONE_WORD_TRIGGER = re.compile(
        r"(?:call|dial|contact|whatsapp|number|phone|no\.?|num)\s*[:.]?\s*",
        re.IGNORECASE,
    )

    # ── UPI patterns ──────────────────────────────────────────────────────

    UPI_PATTERN = re.compile(
        r"[a-zA-Z0-9._-]+@[a-zA-Z]{2,}",
    )

    VALID_UPI_HANDLES: Set[str] = {
        "paytm", "ybl", "oksbi", "okaxis", "okicici", "okhdfcbank",
        "upi", "apl", "axisbank", "sbi", "ibl", "boi", "kotak",
        "hsbc", "citi", "icici", "hdfc", "pnb", "bob", "unionbank",
        "canara", "idfcfirst", "rbl", "idbi", "federal", "indus",
        "kbl", "kvb", "dbs", "sc", "cub", "tmb", "dcb", "jkb",
        "equitas", "bandhan", "fino", "airtel", "jio", "freecharge",
        "mobikwik", "olamoney", "postbank", "gpay", "phonepe",
        "amazonpay", "slice", "jupiter", "fi", "niyox",
    }

    # ── URL patterns ──────────────────────────────────────────────────────

    URL_PATTERN = re.compile(
        r"""
        (?:https?://[^\s<>"']+)       # Full URL
        |
        (?:                            # Shortlink domains
            (?:bit\.ly|t\.me|wa\.me|goo\.gl|tinyurl\.com|
               is\.gd|cutt\.ly|rb\.gy|short\.io)
            /[a-zA-Z0-9_-]+
        )
        """,
        re.VERBOSE | re.IGNORECASE,
    )

    # ── Telegram patterns ─────────────────────────────────────────────────

    TELEGRAM_LINK = re.compile(
        r"(?:https?://)?t\.me/([a-zA-Z0-9_]+(?:/\d+)?)",
        re.IGNORECASE,
    )
    TELEGRAM_MENTION = re.compile(r"@([a-zA-Z][a-zA-Z0-9_]{4,})")

    # ── WhatsApp group patterns ───────────────────────────────────────────

    WHATSAPP_GROUP = re.compile(
        r"(?:https?://)?chat\.whatsapp\.com/([a-zA-Z0-9]{15,})",
        re.IGNORECASE,
    )

    # ── Bank / IFSC / Amount ──────────────────────────────────────────────

    BANK_KEYWORDS = re.compile(
        r"(?:account|a/c|acc|bank|deposit|transfer|neft|rtgs|imps)",
        re.IGNORECASE,
    )
    BANK_ACCOUNT_PATTERN = re.compile(r"\b(\d{9,18})\b")
    IFSC_PATTERN = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")

    AMOUNT_PATTERN = re.compile(
        r"""
        (?:₹|Rs\.?|INR|rs\.?|inr)\s*(\d[\d,]*(?:\.\d{1,2})?)
        |
        (\d[\d,]*(?:\.\d{1,2})?)\s*(?:₹|Rs\.?|INR|rupees?)
        """,
        re.VERBOSE | re.IGNORECASE,
    )

    # ── Investment promise patterns ───────────────────────────────────────

    PROMISE_ENGLISH = [
        (re.compile(r"(\d+)\s*%\s*(?:return|profit|interest|earning)", re.I), "RETURN_PERCENT"),
        (re.compile(r"(?:guaranteed|pakka|100%)\s*(?:return|profit|income|earning)", re.I), "GUARANTEED"),
        (re.compile(r"double\s*(?:your)?\s*(?:money|investment|amount)\s*(?:in)?\s*(\d+)?\s*(?:day|hour|week|month)?", re.I), "DOUBLE_MONEY"),
        (re.compile(r"(?:earn|make|get)\s*(?:₹|Rs\.?|INR|rs\.?)?\s*(\d[\d,]*)\s*(?:per|every|daily|monthly|per\s*day)", re.I), "DAILY_EARNING"),
        (re.compile(r"(?:minimum|min)\s*(?:₹|Rs\.?)?\s*(\d[\d,]*)\s*(?:return|profit|income)", re.I), "DAILY_EARNING"),
        (re.compile(r"(?:invest|deposit)\s*(?:₹|Rs\.?)?\s*(\d[\d,]*)\s*(?:and|&)\s*(?:get|earn|receive)\s*(?:₹|Rs\.?)?\s*(\d[\d,]*)", re.I), "RETURN_PERCENT"),
        (re.compile(r"(\d+)x\s*(?:return|profit|growth)", re.I), "RETURN_PERCENT"),
    ]

    PROMISE_HINDI = [
        (re.compile(r"(\d+)\s*(?:गुना|guna)\s*(?:return|profit|munafa|फ़ायदा|फायदा|लाभ)", re.I), "RETURN_PERCENT"),
        (re.compile(r"(?:guaranteed|pakka|पक्का)\s*(?:munafa|फ़ायदा|फायदा|लाभ|कमाई|income)", re.I), "GUARANTEED"),
        (re.compile(r"(?:paisa|पैसा|money)\s*(?:double|दुगना|dugna|दोगुना|doguna)", re.I), "DOUBLE_MONEY"),
        (re.compile(r"(?:roz|daily|रोज़|हर\s*दिन)\s*(?:₹|Rs\.?)?\s*(\d[\d,]*)\s*(?:kamao|कमाओ|earn|income)", re.I), "DAILY_EARNING"),
        (re.compile(r"(?:sirf|only|बस)\s*(?:₹|Rs\.?)?\s*(\d[\d,]*)\s*(?:invest|lagao|लगाओ)", re.I), "DAILY_EARNING"),
    ]

    # ──────────────────────────────────────────────────────────────────────

    def parse(self, text: str) -> EntityResult:
        """Extract all entities from text.

        Args:
            text: OCR-extracted text (Hindi/English/Hinglish).

        Returns:
            EntityResult with all detected entities.
        """
        result = EntityResult()

        result.phone_details = self.extract_phone_numbers(text)
        result.phones = [p.normalized for p in result.phone_details]
        result.upi_ids = self.extract_upi_ids(text)
        result.urls = self._extract_urls(text)
        result.bank_accounts = self._extract_bank_accounts(text)
        result.ifsc_codes = self._extract_ifsc_codes(text)
        result.amounts = self._extract_amounts(text)
        result.telegram_links = self.extract_telegram_links(text)
        result.whatsapp_groups = self.extract_whatsapp_groups(text)
        result.promise_details = self.extract_investment_promises(text)
        result.investment_promises = [p.text for p in result.promise_details]

        total = (
            len(result.phones) + len(result.upi_ids) + len(result.urls)
            + len(result.bank_accounts) + len(result.ifsc_codes)
            + len(result.amounts) + len(result.telegram_links)
            + len(result.whatsapp_groups) + len(result.investment_promises)
        )
        logger.info(
            "Parsed %d entities: %d phones, %d UPIs, %d URLs, "
            "%d Telegram, %d WhatsApp, %d promises",
            total, len(result.phones), len(result.upi_ids),
            len(result.urls), len(result.telegram_links),
            len(result.whatsapp_groups), len(result.investment_promises),
        )
        return result

    # ── Phone number extraction ───────────────────────────────────────────

    def extract_phone_numbers(self, text: str) -> List[PhoneNumber]:
        """Extract ALL Indian phone number formats including disguised.

        Handles:
            - +91-XXXXXXXXXX, 91XXXXXXXXXX, 0XX-XXXXXXXX
            - wa.me/91XXXXXXXXXX
            - Disguised: 98+OO+12+34+56 (O→0, I→1 substitution)
            - Word form: "call nine eight zero zero..."
        """
        results: List[PhoneNumber] = []
        seen: Set[str] = set()

        # 1. Standard format
        for match in self.PHONE_STANDARD.finditer(text):
            num = self._normalize_phone(match.group())
            if num and num not in seen:
                seen.add(num)
                results.append(PhoneNumber(
                    raw=match.group(), normalized=num,
                    format_type="STANDARD",
                ))

        # 2. WhatsApp links
        for match in self.PHONE_WHATSAPP.finditer(text):
            digits = match.group(1)
            num = f"+91-{digits}"
            if num not in seen and digits[0] in "6789":
                seen.add(num)
                results.append(PhoneNumber(
                    raw=match.group(), normalized=num,
                    format_type="WHATSAPP_LINK",
                ))

        # 3. Disguised format (O→0, I→1, separators)
        for match in self.PHONE_DISGUISED.finditer(text):
            raw = match.group()
            cleaned = self._clean_disguised(raw)
            if cleaned:
                num = f"+91-{cleaned}"
                if num not in seen:
                    seen.add(num)
                    results.append(PhoneNumber(
                        raw=raw, normalized=num,
                        format_type="DISGUISED", confidence=0.7,
                    ))

        # 4. Word form
        word_phones = self._extract_word_form_phones(text)
        for raw, digits in word_phones:
            num = f"+91-{digits}"
            if num not in seen:
                seen.add(num)
                results.append(PhoneNumber(
                    raw=raw, normalized=num,
                    format_type="WORD_FORM", confidence=0.6,
                ))

        return results

    def _normalize_phone(self, raw: str) -> str:
        """Normalize phone number to +91-XXXXXXXXXX."""
        digits = re.sub(r"[^\d]", "", raw)
        if len(digits) >= 10:
            digits = digits[-10:]
            if digits[0] in "6789":
                return f"+91-{digits}"
        return ""

    def _clean_disguised(self, raw: str) -> str:
        """Clean disguised phone number (O→0, I→1, etc)."""
        cleaned = raw.upper()
        cleaned = cleaned.replace("O", "0").replace("I", "1").replace("L", "1")
        digits = re.sub(r"[^\d]", "", cleaned)
        if len(digits) >= 10:
            digits = digits[-10:]
            if digits[0] in "6789":
                return digits
        return ""

    def _extract_word_form_phones(self, text: str) -> List[Tuple[str, str]]:
        """Extract phone numbers written as words.

        E.g., 'call nine eight zero zero one two three four five six'
        """
        results = []
        text_lower = text.lower()

        for trigger_match in self.PHONE_WORD_TRIGGER.finditer(text_lower):
            after = text_lower[trigger_match.end():trigger_match.end() + 200]
            words = re.findall(r"[a-z]+", after)

            digits = []
            raw_words = []
            for word in words:
                if word in WORD_TO_DIGIT:
                    digits.append(WORD_TO_DIGIT[word])
                    raw_words.append(word)
                elif len(digits) >= 5:
                    break  # Stop after a non-number word if we already have some
                elif len(digits) > 0:
                    break
                # Skip non-number words before the sequence

            if len(digits) == 10 and digits[0] in "6789":
                phone_str = "".join(digits)
                raw = " ".join(raw_words)
                results.append((raw, phone_str))

        return results

    # ── UPI extraction ────────────────────────────────────────────────────

    def extract_upi_ids(self, text: str) -> List[str]:
        """Extract UPI IDs (xxx@bankname format)."""
        matches = self.UPI_PATTERN.findall(text)
        upi_ids = set()
        for match in matches:
            if any(d in match.lower() for d in
                   ["gmail", "yahoo", "hotmail", "outlook", "email", "proton"]):
                continue
            handle = match.split("@")[1].lower()
            if handle in self.VALID_UPI_HANDLES or len(handle) <= 10:
                upi_ids.add(match.lower())
        return sorted(upi_ids)

    # ── Telegram extraction ───────────────────────────────────────────────

    def extract_telegram_links(self, text: str) -> List[str]:
        """Extract Telegram links and @mentions."""
        links = set()

        for match in self.TELEGRAM_LINK.finditer(text):
            channel = match.group(1)
            links.add(f"t.me/{channel}")

        for match in self.TELEGRAM_MENTION.finditer(text):
            username = match.group(1)
            if username.lower() not in {"gmail", "yahoo", "hotmail", "email"}:
                links.add(f"@{username}")

        return sorted(links)

    # ── WhatsApp group extraction ─────────────────────────────────────────

    def extract_whatsapp_groups(self, text: str) -> List[str]:
        """Extract WhatsApp group invite links."""
        groups = set()
        for match in self.WHATSAPP_GROUP.finditer(text):
            invite_code = match.group(1)
            groups.add(f"chat.whatsapp.com/{invite_code}")
        return sorted(groups)

    # ── Investment promise extraction ─────────────────────────────────────

    def extract_investment_promises(self, text: str) -> List[InvestmentPromise]:
        """Extract investment/scam promises in English and Hindi."""
        promises = []
        seen_texts = set()

        for pattern, ptype in self.PROMISE_ENGLISH:
            for match in pattern.finditer(text):
                matched_text = match.group().strip()
                if matched_text not in seen_texts:
                    seen_texts.add(matched_text)
                    promises.append(InvestmentPromise(
                        text=matched_text, promise_type=ptype, language="ENGLISH",
                    ))

        for pattern, ptype in self.PROMISE_HINDI:
            for match in pattern.finditer(text):
                matched_text = match.group().strip()
                if matched_text not in seen_texts:
                    seen_texts.add(matched_text)
                    promises.append(InvestmentPromise(
                        text=matched_text, promise_type=ptype, language="HINDI",
                    ))

        return promises

    # ── Standard extractors ───────────────────────────────────────────────

    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs and shortlinks."""
        matches = self.URL_PATTERN.findall(text)
        urls = set()
        for url in matches:
            url = url.strip(".,;:!?)]}>\"'")
            if len(url) > 8:
                urls.add(url)
        return sorted(urls)

    def _extract_bank_accounts(self, text: str) -> List[str]:
        """Extract bank account numbers (near banking keywords)."""
        accounts = set()
        if not self.BANK_KEYWORDS.search(text):
            return []
        matches = self.BANK_ACCOUNT_PATTERN.findall(text)
        for num in matches:
            if 9 <= len(num) <= 18 and num[-10:][0] not in "6789":
                accounts.add(num)
        return sorted(accounts)

    def _extract_ifsc_codes(self, text: str) -> List[str]:
        """Extract IFSC codes."""
        matches = self.IFSC_PATTERN.findall(text)
        return sorted(set(matches))

    def _extract_amounts(self, text: str) -> List[str]:
        """Extract monetary amounts with ₹/Rs/INR prefix/suffix."""
        amounts = set()
        for match in self.AMOUNT_PATTERN.finditer(text):
            num_str = match.group(1) or match.group(2)
            if num_str:
                clean_num = num_str.replace(",", "")
                try:
                    value = float(clean_num)
                    if value > 0:
                        amounts.add(f"₹{clean_num}")
                except ValueError:
                    pass
        return sorted(amounts)
