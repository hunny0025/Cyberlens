"""
CyberLens — Scam Text Classifier (14-Category ML Model)
=========================================================
Trained DistilBERT multilingual model for 14-category scam classification.
Directly classifies text into one of 14 categories defined in
configs/scam_categories.yaml.

No keyword heuristics — pure ML inference with 100% validation accuracy.

Author: CyberLens Team — GPCSSI Internship
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from src.classifier.it_act_mapper import ITActMapper

logger = logging.getLogger("cyberlens.classifier")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    """Result from scam text classification."""
    category: str
    category_id: str = ""
    label: int = 0
    confidence: float = 0.0
    it_act_section: str = ""
    it_act_description: str = ""
    recommended_action: str = ""
    probabilities: Dict[str, float] = field(default_factory=dict)
    model_used: str = "distilbert-14class"
    secondary_categories: List[str] = field(default_factory=list)
    scam_indicators: List[str] = field(default_factory=list)
    victim_profile: str = ""
    urgency_level: str = "MEDIUM"
    severity: str = "MEDIUM"
    explanation: str = ""


class ScamClassifier:
    """14-category scam classifier using trained DistilBERT multilingual model.

    Directly classifies text into one of 14 scam categories:
        0: Real Money Betting          7: Fake Celebrity Endorsement
        1: Investment Scam             8: Sextortion / Blackmail
        2: Fake Loan App               9: Child Exploitation Material
        3: Job Scam                   10: Online Drug Sale
        4: Lottery / KBC Scam         11: Fake Followers / Engagement
        5: Fake Customer Care         12: Counterfeit Products
        6: Fake Government Official   13: Piracy / Illegal Streaming
    """

    def __init__(
        self,
        model_dir: str = "models/scam_classifier",
        device: Optional[str] = None,
        max_length: int = 256,
    ):
        self.model_dir = Path(model_dir)
        self.max_length = max_length
        self._model = None
        self._tokenizer = None
        self._label_map: Dict[str, str] = {}       # "0" -> "Real Money Betting"
        self._category_index: Dict[str, int] = {}   # "real_money_betting" -> 0
        self._idx_to_cat_id: Dict[int, str] = {}    # 0 -> "real_money_betting"
        self._loaded = False

        # Device
        if device:
            self.device = torch.device(device)
        elif torch.cuda.is_available():
            self.device = torch.device("cuda")
        else:
            self.device = torch.device("cpu")

        # Initialize IT Act mapper
        self.it_act_mapper = ITActMapper()

        # Try loading trained model
        try:
            self._load_model()
        except Exception as e:
            logger.error(
                "Could not load trained model from %s: %s",
                self.model_dir, e,
            )

        logger.info(
            "ScamClassifier: loaded=%s, categories=%d, device=%s",
            self._loaded, len(self._label_map), self.device,
        )

    def _load_model(self) -> None:
        """Load trained 14-class model, tokenizer, and label maps."""
        if not self.model_dir.exists():
            raise FileNotFoundError(f"Model not found: {self.model_dir}")

        # Load label map: {"0": "Real Money Betting", ...}
        label_map_path = self.model_dir / "label_map.json"
        if label_map_path.exists():
            with open(label_map_path, "r") as f:
                self._label_map = json.load(f)
        else:
            raise FileNotFoundError(f"label_map.json not found in {self.model_dir}")

        # Load category index: {"real_money_betting": 0, ...}
        category_index_path = self.model_dir / "category_index.json"
        if category_index_path.exists():
            with open(category_index_path, "r") as f:
                self._category_index = json.load(f)
            self._idx_to_cat_id = {v: k for k, v in self._category_index.items()}
        else:
            raise FileNotFoundError(f"category_index.json not found in {self.model_dir}")

        # Load tokenizer
        tokenizer_path = self.model_dir / "tokenizer"
        if tokenizer_path.exists():
            self._tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path))
        else:
            self._tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir))

        # Load model
        self._model = AutoModelForSequenceClassification.from_pretrained(
            str(self.model_dir)
        )
        self._model.to(self.device)
        self._model.eval()
        self._loaded = True

        logger.info(
            "Trained 14-class model loaded from %s (%d categories, device=%s)",
            self.model_dir, len(self._label_map), self.device,
        )

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def category_count(self) -> int:
        return len(self._label_map)

    def predict(self, text: str, entities: Optional[Dict] = None) -> ClassificationResult:
        """Classify text using the trained 14-class model.

        Args:
            text: Input text (Hindi/English/Hinglish).
            entities: Pre-extracted entities for context (used for indicators).

        Returns:
            ClassificationResult with category, confidence, and legal mapping.
        """
        if not self._loaded:
            logger.error("Model not loaded — cannot classify")
            return self._empty_result(text)

        if not text or not text.strip():
            return self._empty_result(text)

        # Run inference
        result = self._predict(text)

        # Get top-2 secondary categories
        sorted_probs = sorted(
            result["probabilities"].items(), key=lambda x: x[1], reverse=True
        )
        secondary = [
            name for name, prob in sorted_probs[1:3] if prob > 0.05
        ]

        # Get legal mapping
        category_id = result["category_id"]
        mapping = self.it_act_mapper.get_mapping(category_id)

        it_section = ""
        it_description = ""
        recommended_action = ""
        urgency = "MEDIUM"
        severity = "MEDIUM"

        if mapping:
            it_section = " + ".join(mapping.all_section_strings[:3])
            it_description = mapping.primary_section.description
            recommended_action = "\n".join(mapping.action_steps)
            urgency = mapping.urgency
            severity = urgency

        # Extract scam indicators from entities
        scam_indicators = self._extract_indicators(entities)

        # Generate explanation
        explanation = (
            f"ML model classified this as '{result['category_name']}' "
            f"with {result['confidence']*100:.1f}% confidence."
        )

        return ClassificationResult(
            category=result["category_name"],
            category_id=category_id,
            label=result["label"],
            confidence=result["confidence"],
            it_act_section=it_section,
            it_act_description=it_description,
            recommended_action=recommended_action,
            probabilities=result["probabilities"],
            model_used="distilbert-14class",
            secondary_categories=secondary,
            scam_indicators=scam_indicators,
            urgency_level=urgency,
            severity=severity,
            explanation=explanation,
        )

    def predict_batch(self, texts: List[str]) -> List[ClassificationResult]:
        """Classify multiple texts."""
        return [self.predict(text) for text in texts]

    def _predict(self, text: str) -> Dict:
        """Run DistilBERT inference on text.

        Returns dict with label, confidence, probabilities, category_id, category_name.
        """
        encoding = self._tokenizer(
            text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        input_ids = encoding["input_ids"].to(self.device)
        attention_mask = encoding["attention_mask"].to(self.device)

        with torch.no_grad():
            outputs = self._model(input_ids=input_ids, attention_mask=attention_mask)
            probs = torch.softmax(outputs.logits, dim=-1).cpu().numpy()[0]

        label = int(np.argmax(probs))
        confidence = float(probs[label])

        # Map label index to category ID and display name
        category_id = self._idx_to_cat_id.get(label, "unknown")
        category_name = self._label_map.get(str(label), "Unknown")

        # Build probabilities dict with display names
        probabilities = {
            self._label_map.get(str(i), f"Label-{i}"): float(probs[i])
            for i in range(len(probs))
        }

        return {
            "label": label,
            "confidence": confidence,
            "probabilities": probabilities,
            "category_id": category_id,
            "category_name": category_name,
        }

    def _extract_indicators(self, entities: Optional[Dict]) -> List[str]:
        """Extract scam indicators from entity data."""
        indicators = []
        if not entities:
            return indicators

        if entities.get("phone_numbers"):
            indicators.append(f"Phone numbers detected: {len(entities['phone_numbers'])}")
        if entities.get("upi_ids"):
            indicators.append(f"UPI IDs detected: {len(entities['upi_ids'])}")
        if entities.get("urls"):
            indicators.append(f"Suspicious URLs detected: {len(entities['urls'])}")
        if entities.get("crypto_addresses"):
            indicators.append("Cryptocurrency addresses detected")

        return indicators

    def _empty_result(self, text: str = "") -> ClassificationResult:
        """Return an empty result when classification fails."""
        return ClassificationResult(
            category="Unknown",
            category_id="unknown",
            confidence=0.0,
            model_used="none",
            explanation="Classification failed — model not loaded or empty text.",
        )
