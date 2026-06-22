"""
CyberLens — Scam Deepfake Analyzer (Upgraded)
=================================================
Specialized deepfake analysis for Rakshit Tandon's 3 priority cases:
1. Celebrity endorsement scams (investment fraud)
2. Sextortion with deepfake intimate content
3. Digital arrest (fake govt official deepfakes)

Author: CyberLens Team — GPCSSI Internship
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.deepfake.celebrity_db import CelebrityDatabase, CelebrityProfile

logger = logging.getLogger("cyberlens.deepfake.intent")


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

@dataclass
class CelebrityScamResult:
    """Result from celebrity endorsement scam analysis."""
    celebrity_detected: bool = False
    celebrities_found: List[str] = field(default_factory=list)
    investment_claim: bool = False
    investment_text: str = ""
    celebrity_category: str = ""
    it_act_section: str = ""
    confidence: float = 0.0
    explanation: str = ""
    urgency: str = "HIGH"


@dataclass
class SextortionResult:
    """Result from sextortion/blackmail analysis."""
    ncii_suspected: bool = False  # Non-Consensual Intimate Images
    threat_detected: bool = False
    threat_text: str = ""
    payment_demand: bool = False
    urgency: str = "CRITICAL"
    it_act_sections: List[str] = field(default_factory=list)
    victim_support_info: str = ""
    explanation: str = ""
    confidence: float = 0.0


@dataclass
class DigitalArrestResult:
    """Result from digital arrest scam analysis."""
    govt_impersonation_suspected: bool = False
    dept_impersonated: str = ""
    arrest_language_detected: bool = False
    uniform_indicators: bool = False
    official_props: List[str] = field(default_factory=list)
    it_act_sections: List[str] = field(default_factory=list)
    urgency: str = "CRITICAL"
    explanation: str = ""
    confidence: float = 0.0


@dataclass
class IntentAnalysisResult:
    """Combined intent analysis result."""
    intent_category: str = ""
    confidence: float = 0.0
    reasoning: List[str] = field(default_factory=list)
    urgency_level: str = "MEDIUM"
    celebrity_result: Optional[CelebrityScamResult] = None
    sextortion_result: Optional[SextortionResult] = None
    digital_arrest_result: Optional[DigitalArrestResult] = None

    def to_dict(self) -> Dict:
        result = {
            "intent_category": self.intent_category,
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning,
            "urgency_level": self.urgency_level,
        }
        if self.celebrity_result and self.celebrity_result.celebrity_detected:
            result["celebrity_scam"] = {
                "celebrities": self.celebrity_result.celebrities_found,
                "investment_claim": self.celebrity_result.investment_claim,
                "it_act_section": self.celebrity_result.it_act_section,
            }
        if self.sextortion_result and self.sextortion_result.ncii_suspected:
            result["sextortion"] = {
                "threat_detected": self.sextortion_result.threat_detected,
                "payment_demand": self.sextortion_result.payment_demand,
                "it_act_sections": self.sextortion_result.it_act_sections,
            }
        if self.digital_arrest_result and self.digital_arrest_result.govt_impersonation_suspected:
            result["digital_arrest"] = {
                "dept_impersonated": self.digital_arrest_result.dept_impersonated,
                "official_props": self.digital_arrest_result.official_props,
                "it_act_sections": self.digital_arrest_result.it_act_sections,
            }
        return result


# ---------------------------------------------------------------------------
# Keyword patterns
# ---------------------------------------------------------------------------

INVESTMENT_KEYWORDS = [
    "invest", "return", "profit", "double", "guaranteed",
    "stock", "mutual fund", "forex", "crypto", "trading",
    "scheme", "plan", "earn", "income", "लाभ", "निवेश",
    "मुनाफा", "रिटर्न", "कमाई", "पैसा दुगना",
]

SEXTORTION_KEYWORDS_EN = [
    "viral your video", "leak your photos", "send money",
    "blackmail", "intimate content", "morphed", "nude",
    "expose you", "private video", "pay or else",
    "screenshot saved", "recorded you", "share everywhere",
]

SEXTORTION_KEYWORDS_HI = [
    "वीडियो वायरल कर दूंगा", "फोटो लीक", "पैसे भेजो",
    "ब्लैकमेल", "अश्लील", "payment karo", "paisa bhejo",
    "viral kar dunga", "nahi toh", "expose",
]

DIGITAL_ARREST_KEYWORDS = [
    "digital arrest", "arrest warrant", "fir registered",
    "court order", "summons", "digital custody",
    "verification pending", "case registered",
    "money laundering", "suspicious transaction",
    "parcel seized", "drug found", "aadhaar linked",
    "डिजिटल अरेस्ट", "गिरफ़्तारी वारंट", "FIR दर्ज",
    "कोर्ट ऑर्डर", "सम्मन", "पार्सल सीज़",
]

GOVT_DEPARTMENT_PATTERNS = {
    "CBI": ["cbi", "central bureau", "investigation bureau"],
    "ED": ["enforcement directorate", "ed ", "ed notice", "ecir"],
    "Police": ["police", "cyber crime", "crime branch", "thana", "sho"],
    "Income Tax": ["income tax", "it department", "tax notice", "itr"],
    "Customs": ["customs", "excise", "parcel", "courier seized"],
    "TRAI": ["trai", "telecom", "sim deactivate", "mobile number"],
    "RBI": ["rbi", "reserve bank", "banking fraud"],
    "Court": ["court", "judge", "magistrate", "judicial"],
    "NIA": ["nia", "national investigation"],
    "NCB": ["ncb", "narcotics"],
}

OFFICIAL_PROPS = [
    "badge", "uniform", "id card", "office background",
    "government seal", "emblem", "flag", "desk",
    "ashoka pillar", "national emblem",
]


class ScamDeepfakeAnalyzer:
    """Specialized analyzer for the 3 priority deepfake scam types.

    Provides targeted analysis for:
        1. Celebrity investment endorsement scams
        2. Sextortion with deepfake/morphed content
        3. Digital arrest (fake govt officer) scams
    """

    def __init__(self):
        self.celeb_db = CelebrityDatabase()
        logger.info(
            "ScamDeepfakeAnalyzer initialized: %d celebrity profiles",
            self.celeb_db.total_profiles,
        )

    def analyze_full(
        self,
        ocr_text: str = "",
        deepfake_probability: float = 0.0,
    ) -> IntentAnalysisResult:
        """Run all 3 specialized analyses and return combined result.

        Args:
            ocr_text: OCR-extracted text from the image.
            deepfake_probability: Pre-computed deepfake probability.

        Returns:
            IntentAnalysisResult with the most relevant sub-result populated.
        """
        celeb_result = self.analyze_celebrity_scam(ocr_text)
        sextortion_result = self.analyze_sextortion(ocr_text)
        arrest_result = self.analyze_digital_arrest(ocr_text)

        # Determine primary intent
        candidates = []

        if celeb_result.celebrity_detected and celeb_result.investment_claim:
            candidates.append(("CELEBRITY_INVESTMENT_SCAM", celeb_result.confidence, "CRITICAL"))
        elif celeb_result.celebrity_detected:
            candidates.append(("FAKE_ENDORSEMENT", celeb_result.confidence * 0.7, "HIGH"))

        if sextortion_result.ncii_suspected or sextortion_result.threat_detected:
            candidates.append(("SEXTORTION", sextortion_result.confidence, "CRITICAL"))

        if arrest_result.govt_impersonation_suspected:
            candidates.append(("DIGITAL_ARREST", arrest_result.confidence, "CRITICAL"))

        if not candidates:
            return IntentAnalysisResult(
                intent_category="GENERIC_CONTENT",
                confidence=0.3,
                reasoning=["No specific scam pattern detected"],
                urgency_level="LOW",
            )

        # Sort by confidence
        candidates.sort(key=lambda x: x[1], reverse=True)
        primary = candidates[0]

        reasoning = []
        if celeb_result.celebrity_detected:
            reasoning.append(f"Celebrity detected: {', '.join(celeb_result.celebrities_found)}")
        if sextortion_result.threat_detected:
            reasoning.append(f"Threat language: {sextortion_result.threat_text[:100]}")
        if arrest_result.govt_impersonation_suspected:
            reasoning.append(f"Dept impersonated: {arrest_result.dept_impersonated}")

        return IntentAnalysisResult(
            intent_category=primary[0],
            confidence=primary[1],
            reasoning=reasoning,
            urgency_level=primary[2],
            celebrity_result=celeb_result if celeb_result.celebrity_detected else None,
            sextortion_result=sextortion_result if sextortion_result.ncii_suspected or sextortion_result.threat_detected else None,
            digital_arrest_result=arrest_result if arrest_result.govt_impersonation_suspected else None,
        )

    # ── Celebrity Scam Analysis ───────────────────────────────────────

    def analyze_celebrity_scam(
        self,
        ocr_text: str,
    ) -> CelebrityScamResult:
        """Detect if content uses celebrity likeness for investment scam.

        Args:
            ocr_text: OCR text from the image.

        Returns:
            CelebrityScamResult with detection details.
        """
        result = CelebrityScamResult()
        text_lower = ocr_text.lower()

        # Search for celebrity mentions
        matched = self.celeb_db.search(ocr_text)
        if matched:
            result.celebrity_detected = True
            result.celebrities_found = [m.name for m in matched]
            result.celebrity_category = matched[0].category
            result.it_act_section = matched[0].it_act_if_impersonated
            result.confidence = 0.7

        # Check for investment claims near celebrity mention
        invest_score = sum(
            1 for kw in INVESTMENT_KEYWORDS
            if kw.lower() in text_lower or kw in ocr_text
        )

        if invest_score >= 2:
            result.investment_claim = True
            result.investment_text = self._extract_investment_claim(text_lower)
            result.confidence = min(0.95, result.confidence + invest_score * 0.05)

        if result.celebrity_detected and result.investment_claim:
            result.explanation = (
                f"⚠️ FAKE CELEBRITY ENDORSEMENT DETECTED\n"
                f"Celebrity: {', '.join(result.celebrities_found)}\n"
                f"Investment claim found: {result.investment_text[:150]}\n"
                f"This appears to be a fraudulent investment scheme "
                f"using a celebrity's name/image without authorization.\n"
                f"Applicable: {result.it_act_section}"
            )
            result.urgency = "CRITICAL"
        elif result.celebrity_detected:
            result.explanation = (
                f"Celebrity mention detected: {', '.join(result.celebrities_found)}. "
                f"No investment claim found — may be legitimate content."
            )

        return result

    def _extract_investment_claim(self, text: str) -> str:
        """Extract the specific investment claim text."""
        patterns = [
            r"(?:invest|earn|return|profit|guaranteed).{0,100}",
            r"(?:₹|Rs\.?|INR)\s*\d[\d,]*.*?(?:return|profit|daily|monthly)",
            r"\d+\s*%\s*(?:return|profit|interest)",
            r"double\s+your\s+money.{0,50}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group().strip()
        return ""

    # ── Sextortion Analysis ───────────────────────────────────────────

    def analyze_sextortion(
        self,
        threat_text: str,
    ) -> SextortionResult:
        """Detect sextortion/blackmail patterns in text.

        Args:
            threat_text: OCR text or threat message.

        Returns:
            SextortionResult with threat analysis.
        """
        result = SextortionResult()
        text_lower = threat_text.lower()

        # English threat keywords
        en_score = sum(
            1 for kw in SEXTORTION_KEYWORDS_EN
            if kw.lower() in text_lower
        )

        # Hindi threat keywords
        hi_score = sum(
            1 for kw in SEXTORTION_KEYWORDS_HI
            if kw.lower() in text_lower or kw in threat_text
        )

        total_score = en_score + hi_score

        if total_score >= 2:
            result.ncii_suspected = True
            result.threat_detected = True
            result.confidence = min(0.95, 0.5 + total_score * 0.1)

            # Extract threat text
            for kw in SEXTORTION_KEYWORDS_EN + SEXTORTION_KEYWORDS_HI:
                if kw.lower() in text_lower or kw in threat_text:
                    result.threat_text = kw
                    break

        # Check for payment demand
        payment_patterns = [
            r"(?:send|pay|transfer|bhejo)\s*(?:₹|Rs\.?|INR)?\s*\d",
            r"(?:₹|Rs\.?|INR)\s*\d[\d,]*\s*(?:send|pay|transfer|bhejo)",
            r"(?:upi|paytm|gpay|phonpe|bank)",
        ]
        for pattern in payment_patterns:
            if re.search(pattern, text_lower):
                result.payment_demand = True
                break

        result.it_act_sections = [
            "IT Act §66E — Violation of privacy",
            "BNS §77 — Criminal intimidation",
            "IT Act §67 — Publishing obscene material",
        ]

        if result.ncii_suspected:
            result.victim_support_info = (
                "🆘 VICTIM SUPPORT:\n"
                "• National Cyber Crime Helpline: 1930\n"
                "• cybercrime.gov.in — File complaint online\n"
                "• StopNCII.org — Report for hash-matching removal\n"
                "• Women Helpline: 181\n"
                "• Do NOT pay the blackmailer"
            )
            result.explanation = (
                "⚠️ SEXTORTION / BLACKMAIL DETECTED\n"
                f"Threat indicators: {total_score} keyword matches\n"
                f"Payment demand: {'Yes' if result.payment_demand else 'No'}\n"
                f"URGENCY: CRITICAL — Victim may be in distress\n"
                f"Applicable: IT Act §66E, BNS §77, IT Act §67"
            )

        return result

    # ── Digital Arrest Analysis ───────────────────────────────────────

    def analyze_digital_arrest(
        self,
        audio_text: str,
    ) -> DigitalArrestResult:
        """Detect fake govt official / digital arrest scam.

        Args:
            audio_text: OCR text or transcribed audio from the content.

        Returns:
            DigitalArrestResult with impersonation analysis.
        """
        result = DigitalArrestResult()
        text_lower = audio_text.lower()

        # Check for arrest/legal language
        arrest_score = sum(
            1 for kw in DIGITAL_ARREST_KEYWORDS
            if kw.lower() in text_lower or kw in audio_text
        )

        # Detect which department is being impersonated
        for dept, keywords in GOVT_DEPARTMENT_PATTERNS.items():
            if any(kw in text_lower for kw in keywords):
                result.dept_impersonated = dept
                result.govt_impersonation_suspected = True
                break

        # Check for official props in text
        found_props = []
        for prop in OFFICIAL_PROPS:
            if prop in text_lower:
                found_props.append(prop)
        result.official_props = found_props
        if found_props:
            result.uniform_indicators = True

        if arrest_score >= 2 or result.govt_impersonation_suspected:
            result.arrest_language_detected = True
            result.confidence = min(0.95, 0.4 + arrest_score * 0.1)

            if result.govt_impersonation_suspected:
                result.confidence += 0.2

        result.it_act_sections = [
            f"IPC §170 / BNS §204 — Impersonating {result.dept_impersonated or 'public servant'}",
            "IT Act §66D — Cheating by personation",
            "BNS §351 — Criminal intimidation",
        ]

        if result.govt_impersonation_suspected:
            result.explanation = (
                f"⚠️ DIGITAL ARREST SCAM DETECTED\n"
                f"Department impersonated: {result.dept_impersonated}\n"
                f"Arrest language indicators: {arrest_score} matches\n"
                f"Official props detected: {', '.join(found_props) if found_props else 'None'}\n"
                f"URGENCY: CRITICAL — Victim may be under psychological coercion\n"
                f"Applicable: IPC §170, IT Act §66D, BNS §204"
            )

        return result


# ---------------------------------------------------------------------------
# Legacy IntentAnalyzer (backward compatible wrapper)
# ---------------------------------------------------------------------------

class IntentAnalyzer:
    """Legacy wrapper — delegates to ScamDeepfakeAnalyzer."""

    def __init__(self):
        self._analyzer = ScamDeepfakeAnalyzer()

    def analyze(
        self,
        ocr_text: str = "",
        deepfake_probability: float = 0.0,
    ) -> IntentAnalysisResult:
        """Analyze intent from OCR text and deepfake probability."""
        return self._analyzer.analyze_full(ocr_text, deepfake_probability)
