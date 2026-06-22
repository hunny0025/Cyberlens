"""
CyberLens — Hindi/Devanagari Text Cleaner
=============================================
Cleans common OCR errors in Hindi/Devanagari text, normalizes
mixed Hindi-English (Hinglish), and maps common OCR misreads.

Author: CyberLens Team — GPCSSI Internship
"""

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Tuple

logger = logging.getLogger("cyberlens.ocr.hindi_cleaner")


@dataclass
class CleanedTextResult:
    """Result from Hindi text cleaning."""
    original: str
    cleaned: str
    corrections_made: int
    confidence_boost: float  # Estimated OCR confidence improvement
    language_detected: str   # HINDI, ENGLISH, HINGLISH


# ---------------------------------------------------------------------------
# Common OCR misreads
# ---------------------------------------------------------------------------

# Latin character → Devanagari misreads (in Hindi text context)
LATIN_TO_DEVANAGARI: Dict[str, str] = {
    "3fl": "इ",
    "31": "उ",
    "37": "ऊ",
}

# Devanagari character-level OCR corrections
DEVANAGARI_CORRECTIONS: Dict[str, str] = {
    "ाी": "ी",        # Double matra fix
    "ंं": "ं",        # Double anusvara
    "ंा": "ां",      # Anusvara + matra order
    "ाे": "ो",       # aa + e = o
    "ाै": "ौ",       # aa + ai = au
    "ि्": "ि",       # Invalid halant after short-i
}

# Common OCR misreads in Latin characters (in Hinglish context)
LATIN_OCR_FIXES: Dict[str, str] = {
    "rn": "m",       # rn → m (very common)
    "cl": "d",       # cl → d
    "vv": "w",       # vv → w
    "ii": "u",       # ii → u sometimes
}

# Number/letter confusion in mixed text
NUMBER_LETTER_FIXES: List[Tuple[re.Pattern, str]] = [
    # 0 ↔ O in numeric context (surrounded by digits)
    (re.compile(r"(\d)O(\d)"), r"\g<1>0\g<2>"),
    (re.compile(r"(\d)o(\d)"), r"\g<1>0\g<2>"),
    # 1 ↔ I/l in numeric context
    (re.compile(r"(\d)[Il](\d)"), r"\g<1>1\g<2>"),
    # 5 ↔ S in numeric context
    (re.compile(r"(\d)S(\d)"), r"\g<1>5\g<2>"),
    # 8 ↔ B in numeric context
    (re.compile(r"(\d)B(\d)"), r"\g<1>8\g<2>"),
]

# Common Hindi scam-related word corrections
HINDI_WORD_CORRECTIONS: Dict[str, str] = {
    # Common OCR errors in scam text
    "पेसे": "पैसे",           # Money
    "कमाई्": "कमाई",          # Earnings
    "इन्वेस्टमेन्ट": "इन्वेस्टमेंट",  # Investment
    "गॅरन्टी": "गारंटी",       # Guarantee
    "प्राॅफिट": "प्रॉफिट",     # Profit
    "कस्टमर्": "कस्टमर",       # Customer
    "हेल्पलाइन्": "हेल्पलाइन",  # Helpline
    "बेटिंग्": "बेटिंग",        # Betting
}

# Hinglish normalization (common transliterations)
HINGLISH_NORMALIZE: Dict[str, str] = {
    "paisa": "पैसा",
    "kamao": "कमाओ",
    "jeetlo": "जीत लो",
    "lagao": "लगाओ",
    "bhaejo": "भेजो",
    "munafa": "मुनाफा",
    "faayda": "फायदा",
}


class HindiTextCleaner:
    """Cleans and normalizes OCR output for Hindi/Hinglish text.

    Handles:
        - Devanagari character corrections (matra fixes)
        - Latin ↔ Devanagari confusion
        - Number/letter substitution in numeric context
        - Common Hindi word OCR errors
        - Hinglish text normalization
        - Unicode normalization (NFC)
    """

    def clean(self, text: str) -> CleanedTextResult:
        """Clean OCR text and return corrected version.

        Args:
            text: Raw OCR output text.

        Returns:
            CleanedTextResult with cleaned text and metadata.
        """
        original = text
        corrections = 0

        # Detect language mix
        lang = self._detect_language(text)

        # Step 1: Unicode normalization
        text = unicodedata.normalize("NFC", text)

        # Step 2: Fix Devanagari character-level errors
        if lang in ("HINDI", "HINGLISH"):
            text, n = self._fix_devanagari(text)
            corrections += n

        # Step 3: Fix number/letter confusion
        text, n = self._fix_number_letter(text)
        corrections += n

        # Step 4: Fix common Hindi word errors
        if lang in ("HINDI", "HINGLISH"):
            text, n = self._fix_hindi_words(text)
            corrections += n

        # Step 5: Fix Latin OCR errors in Hinglish
        if lang in ("ENGLISH", "HINGLISH"):
            text, n = self._fix_latin_ocr(text)
            corrections += n

        # Step 6: Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\n\s*\n+", "\n\n", text)

        # Estimate confidence boost
        boost = min(0.15, corrections * 0.01)

        result = CleanedTextResult(
            original=original,
            cleaned=text,
            corrections_made=corrections,
            confidence_boost=boost,
            language_detected=lang,
        )

        if corrections > 0:
            logger.info(
                "Hindi cleaner: %d corrections, confidence boost +%.2f, lang=%s",
                corrections, boost, lang,
            )

        return result

    def _detect_language(self, text: str) -> str:
        """Detect if text is Hindi, English, or Hinglish."""
        devanagari_count = sum(
            1 for c in text if "\u0900" <= c <= "\u097F"
        )
        latin_count = sum(1 for c in text if c.isascii() and c.isalpha())
        total = devanagari_count + latin_count

        if total == 0:
            return "ENGLISH"

        devanagari_ratio = devanagari_count / total

        if devanagari_ratio > 0.6:
            return "HINDI"
        elif devanagari_ratio > 0.1:
            return "HINGLISH"
        else:
            return "ENGLISH"

    def _fix_devanagari(self, text: str) -> Tuple[str, int]:
        """Fix Devanagari character-level OCR errors."""
        count = 0
        for wrong, right in DEVANAGARI_CORRECTIONS.items():
            occurrences = text.count(wrong)
            if occurrences > 0:
                text = text.replace(wrong, right)
                count += occurrences
        return text, count

    def _fix_number_letter(self, text: str) -> Tuple[str, int]:
        """Fix number/letter confusion in numeric context."""
        count = 0
        for pattern, replacement in NUMBER_LETTER_FIXES:
            new_text = pattern.sub(replacement, text)
            if new_text != text:
                count += len(pattern.findall(text))
                text = new_text
        return text, count

    def _fix_hindi_words(self, text: str) -> Tuple[str, int]:
        """Fix common Hindi word OCR errors."""
        count = 0
        for wrong, right in HINDI_WORD_CORRECTIONS.items():
            occurrences = text.count(wrong)
            if occurrences > 0:
                text = text.replace(wrong, right)
                count += occurrences
        return text, count

    def _fix_latin_ocr(self, text: str) -> Tuple[str, int]:
        """Fix Latin character OCR errors (rn→m, etc).

        Only applies fixes in word context (not in URLs, codes, etc).
        """
        count = 0
        words = text.split()
        fixed_words = []

        for word in words:
            # Skip URLs, email-like, codes
            if any(c in word for c in "@://."):
                fixed_words.append(word)
                continue

            new_word = word
            for wrong, right in LATIN_OCR_FIXES.items():
                if wrong in new_word.lower():
                    # Only fix in word context (surrounded by letters)
                    new_word = re.sub(
                        rf"(?<=[a-zA-Z]){re.escape(wrong)}(?=[a-zA-Z])",
                        right, new_word,
                    )

            if new_word != word:
                count += 1
            fixed_words.append(new_word)

        return " ".join(fixed_words), count
