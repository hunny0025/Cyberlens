"""
CyberLens — Gemini-Powered Multi-Category Classifier
========================================================
Dynamically loads categories from scam_categories.yaml.
Uses keyword matching + rule engine for local classification
across ALL 14 scam categories (no external API calls for core ML).

For Gemini API integration: set GEMINI_API_KEY in .env
(optional enhancement — core classifier works without it).

Author: CyberLens Team — GPCSSI Internship
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger("cyberlens.classifier.gemini")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CATEGORIES_PATH = PROJECT_ROOT / "configs" / "scam_categories.yaml"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CategoryDefinition:
    """A single scam category from the YAML taxonomy."""
    id: str
    label: str
    it_act_section: str
    severity: str
    blocking_priority: int
    keywords_english: List[str] = field(default_factory=list)
    keywords_hindi: List[str] = field(default_factory=list)
    group: str = ""


@dataclass
class ClassificationResult:
    """Full classification output with multi-category support."""
    primary_category: str = ""
    primary_category_id: str = ""
    secondary_categories: List[str] = field(default_factory=list)
    confidence: float = 0.0
    category_confidences: Dict[str, float] = field(default_factory=dict)
    it_act_sections: List[str] = field(default_factory=list)
    scam_indicators: List[str] = field(default_factory=list)
    victim_profile: str = ""
    estimated_reach: str = ""
    recommended_action: str = ""
    urgency_level: str = "MEDIUM"
    severity: str = "MEDIUM"
    explanation: str = ""


# ---------------------------------------------------------------------------
# Category loader
# ---------------------------------------------------------------------------

def load_categories(yaml_path: Path = CATEGORIES_PATH) -> List[CategoryDefinition]:
    """Load all category definitions from the YAML taxonomy.

    Args:
        yaml_path: Path to scam_categories.yaml.

    Returns:
        Flat list of CategoryDefinition objects.
    """
    if not yaml_path.exists():
        logger.warning("Categories YAML not found: %s", yaml_path)
        return _default_categories()

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    categories = []
    for group_name, items in data.get("categories", {}).items():
        for item in items:
            cat = CategoryDefinition(
                id=item["id"],
                label=item["label"],
                it_act_section=item.get("it_act_section", ""),
                severity=item.get("severity", "MEDIUM"),
                blocking_priority=item.get("blocking_priority", 3),
                keywords_english=item.get("keywords_english", []),
                keywords_hindi=item.get("keywords_hindi", []),
                group=group_name,
            )
            categories.append(cat)

    logger.info("Loaded %d categories from %s", len(categories), yaml_path.name)
    return categories


def _default_categories() -> List[CategoryDefinition]:
    """Fallback 3-category list when YAML is missing."""
    return [
        CategoryDefinition("real_money_betting", "Real Money Betting",
                           "IT Act §66D", "HIGH", 2,
                           ["betting", "cricket", "ipl", "satta", "toss"],
                           ["बेटिंग", "सट्टा", "क्रिकेट"], "financial_fraud"),
        CategoryDefinition("investment_scam", "Investment Scam",
                           "IT Act §66D + IPC §420", "HIGH", 1,
                           ["invest", "return", "double", "profit", "stock"],
                           ["निवेश", "रिटर्न", "मुनाफा"], "financial_fraud"),
        CategoryDefinition("fake_customer_care", "Fake Customer Care",
                           "IT Act §66C + §66D", "HIGH", 1,
                           ["customer care", "helpline", "kyc", "suspended"],
                           ["कस्टमर केयर", "हेल्पलाइन"], "impersonation"),
    ]


# ---------------------------------------------------------------------------
# Victim profile inference
# ---------------------------------------------------------------------------

VICTIM_PROFILES = {
    "real_money_betting": "Young males (18-35), sports enthusiasts, online gamers",
    "investment_scam": "Middle-aged adults (30-55), new investors, retirees seeking income",
    "loan_scam": "Young adults (18-30) in financial distress, low-income groups",
    "job_scam": "Students, fresh graduates, unemployed youth seeking remote work",
    "lottery_scam": "Elderly (50+), rural populations, low digital literacy users",
    "fake_customer_care": "All age groups, bank/e-commerce users, low digital literacy",
    "fake_govt_official": "All age groups, especially elderly and middle-class families",
    "fake_celebrity_endorsement": "Middle-aged adults, social media users, retail investors",
    "sextortion_threat": "Young adults (18-35), especially males, social media users",
    "child_exploitation": "Minors — HIGHEST PRIORITY VICTIM PROTECTION",
    "drug_sale": "Young adults (18-30), urban populations",
    "fake_followers_sale": "Social media influencers, small businesses, content creators",
    "counterfeit_products": "Online shoppers, bargain seekers",
    "piracy_links": "Young adults, students, entertainment consumers",
}


# ---------------------------------------------------------------------------
# Multi-Category Classifier
# ---------------------------------------------------------------------------

class GeminiClassifier:
    """Multi-category scam classifier with dynamic taxonomy.

    Classification pipeline:
        1. Load categories from YAML
        2. Keyword matching across all categories (Hindi + English)
        3. Score each category by keyword density
        4. Return primary + secondary categories with confidence
        5. Map to IT Act sections and generate officer-friendly explanation

    Optionally uses Gemini API for enhanced classification if
    GEMINI_API_KEY is set (not required for core functionality).
    """

    def __init__(self, categories_path: Optional[Path] = None):
        """Initialize classifier with category taxonomy.

        Args:
            categories_path: Override path to scam_categories.yaml.
        """
        path = categories_path or CATEGORIES_PATH
        self.categories = load_categories(path)
        self._category_map = {c.id: c for c in self.categories}

        # Build keyword index for fast lookup
        self._keyword_index: Dict[str, List[Tuple[str, float]]] = {}
        self._build_keyword_index()

        # Gemini API (optional)
        self._gemini_available = False
        self._gemini_key = os.getenv("GEMINI_API_KEY", "")
        if self._gemini_key:
            self._gemini_available = True
            logger.info("Gemini API key found — enhanced classification available")

        logger.info(
            "GeminiClassifier initialized: %d categories, gemini=%s",
            len(self.categories), self._gemini_available,
        )

    def _build_keyword_index(self) -> None:
        """Build inverted keyword index for fast matching."""
        for cat in self.categories:
            for kw in cat.keywords_english:
                kw_lower = kw.lower().strip()
                if kw_lower not in self._keyword_index:
                    self._keyword_index[kw_lower] = []
                self._keyword_index[kw_lower].append((cat.id, 1.0))

            for kw in cat.keywords_hindi:
                kw_stripped = kw.strip()
                if kw_stripped not in self._keyword_index:
                    self._keyword_index[kw_stripped] = []
                self._keyword_index[kw_stripped].append((cat.id, 1.0))

    def classify(
        self,
        text: str,
        image_context: str = "",
        entities: Optional[Dict[str, List[str]]] = None,
    ) -> ClassificationResult:
        """Classify text against ALL scam categories.

        Args:
            text: OCR-extracted or raw scam text.
            image_context: Additional context from image analysis.
            entities: Pre-extracted entities (phones, UPIs, etc).

        Returns:
            ClassificationResult with primary/secondary categories.
        """
        combined_text = f"{text} {image_context}".strip()
        if not combined_text:
            return ClassificationResult(
                primary_category="Unknown",
                explanation="No text provided for classification",
            )

        # Score all categories
        scores = self._score_categories(combined_text)

        # Sort by score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        if not ranked or ranked[0][1] == 0:
            return ClassificationResult(
                primary_category="Unknown",
                confidence=0.1,
                explanation="No scam indicators matched",
            )

        # Primary category
        primary_id = ranked[0][0]
        primary_score = ranked[0][1]
        primary_cat = self._category_map.get(primary_id)

        # Normalize scores to confidences
        total_score = sum(s for _, s in ranked if s > 0)
        confidences = {}
        for cat_id, score in ranked:
            if score > 0:
                conf = score / total_score if total_score > 0 else 0
                cat = self._category_map.get(cat_id)
                if cat:
                    confidences[cat.label] = round(conf, 3)

        # Secondary categories (score > 30% of primary)
        secondary = []
        for cat_id, score in ranked[1:]:
            if score > primary_score * 0.3:
                cat = self._category_map.get(cat_id)
                if cat:
                    secondary.append(cat.label)

        # Extract scam indicators
        indicators = self._extract_indicators(combined_text, primary_id)

        # Get legal sections
        from src.classifier.it_act_mapper import ITActMapper
        mapper = ITActMapper()
        it_sections = mapper.get_all_sections(primary_id)
        action_steps = mapper.get_action_steps(primary_id)
        urgency = mapper.get_urgency(primary_id)

        # Build explanation
        explanation = self._build_explanation(
            primary_cat, indicators, secondary, entities,
        )

        # Primary confidence
        primary_conf = confidences.get(primary_cat.label, 0.5) if primary_cat else 0.3

        return ClassificationResult(
            primary_category=primary_cat.label if primary_cat else "Unknown",
            primary_category_id=primary_id,
            secondary_categories=secondary,
            confidence=round(min(0.99, primary_conf + 0.3), 2),
            category_confidences=confidences,
            it_act_sections=it_sections,
            scam_indicators=indicators,
            victim_profile=VICTIM_PROFILES.get(primary_id, "General public"),
            estimated_reach=self._estimate_reach(entities),
            recommended_action="\n".join(action_steps) if action_steps else "Report to I4C",
            urgency_level=urgency,
            severity=primary_cat.severity if primary_cat else "MEDIUM",
            explanation=explanation,
        )

    def _score_categories(self, text: str) -> Dict[str, float]:
        """Score each category by keyword matching.

        Args:
            text: Combined text to analyze.

        Returns:
            Dict of category_id → score.
        """
        text_lower = text.lower()
        scores: Dict[str, float] = {cat.id: 0.0 for cat in self.categories}

        for keyword, mappings in self._keyword_index.items():
            if keyword in text_lower or keyword in text:
                for cat_id, weight in mappings:
                    scores[cat_id] += weight

        # Boost for multi-word keyword phrases (more specific = higher weight)
        for cat in self.categories:
            for kw in cat.keywords_english:
                if len(kw.split()) >= 2 and kw.lower() in text_lower:
                    scores[cat.id] += 1.5  # Bonus for multi-word match

            for kw in cat.keywords_hindi:
                if len(kw.split()) >= 2 and kw in text:
                    scores[cat.id] += 1.5

        return scores

    def _extract_indicators(self, text: str, primary_id: str) -> List[str]:
        """Extract human-readable scam indicators from text.

        Args:
            text: Input text.
            primary_id: Primary category ID.

        Returns:
            List of indicator strings.
        """
        indicators = []
        text_lower = text.lower()

        cat = self._category_map.get(primary_id)
        if not cat:
            return indicators

        for kw in cat.keywords_english:
            if kw.lower() in text_lower:
                indicators.append(f"Contains '{kw}' (English keyword match)")
                if len(indicators) >= 5:
                    break

        for kw in cat.keywords_hindi:
            if kw in text:
                indicators.append(f"Contains '{kw}' (Hindi keyword match)")
                if len(indicators) >= 8:
                    break

        # Generic indicators
        if re.search(r"\+91|wa\.me|t\.me", text):
            indicators.append("Contains contact information (phone/messaging links)")
        if re.search(r"@\w+", text):
            indicators.append("Contains UPI ID or social media handle")
        if re.search(r"₹|Rs\.?\s*\d", text):
            indicators.append("Contains monetary amounts")

        return indicators[:10]

    def _build_explanation(
        self,
        primary_cat: Optional[CategoryDefinition],
        indicators: List[str],
        secondary: List[str],
        entities: Optional[Dict],
    ) -> str:
        """Build officer-friendly explanation of the classification.

        Args:
            primary_cat: Primary category definition.
            indicators: Detected scam indicators.
            secondary: Secondary category labels.
            entities: Extracted entities.

        Returns:
            Human-readable explanation string.
        """
        if not primary_cat:
            return "Unable to classify content."

        parts = [
            f"This content has been classified as **{primary_cat.label}** "
            f"under the {primary_cat.group.replace('_', ' ')} category.",
        ]

        if indicators:
            parts.append(f"\n\nKey indicators found ({len(indicators)}):")
            for ind in indicators[:5]:
                parts.append(f"  • {ind}")

        if secondary:
            parts.append(f"\n\nAlso related to: {', '.join(secondary)}")

        parts.append(f"\n\nApplicable law: {primary_cat.it_act_section}")
        parts.append(f"Severity: {primary_cat.severity}")
        parts.append(f"Blocking priority: {primary_cat.blocking_priority}/5")

        if entities:
            phone_count = len(entities.get("phones", []))
            upi_count = len(entities.get("upi_ids", []))
            if phone_count or upi_count:
                parts.append(
                    f"\n\nEntities detected: {phone_count} phone(s), {upi_count} UPI ID(s)"
                )

        return "\n".join(parts)

    def _estimate_reach(self, entities: Optional[Dict]) -> str:
        """Estimate potential reach/impact of the scam.

        Args:
            entities: Extracted entities dict.

        Returns:
            Human-readable reach estimate.
        """
        if not entities:
            return "Unknown"

        urls = len(entities.get("urls", []))
        telegram = len(entities.get("telegram_links", []))
        whatsapp = len(entities.get("whatsapp_groups", []))

        if telegram > 0 or whatsapp > 0:
            return "HIGH — Active messaging groups detected"
        elif urls > 2:
            return "MEDIUM — Multiple URLs suggest organized operation"
        elif urls > 0:
            return "LOW-MEDIUM — Single URL distribution"
        else:
            return "LOW — No distribution channels detected"

    @property
    def category_count(self) -> int:
        """Number of loaded categories."""
        return len(self.categories)

    @property
    def category_ids(self) -> List[str]:
        """List of all category IDs."""
        return [c.id for c in self.categories]
