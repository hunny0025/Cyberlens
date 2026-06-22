"""
CyberLens — Siamese Training Data Builder
=============================================
Generates positive (same-operator) and negative (different-operator)
pairs from behavioral fingerprints for training the Siamese network.

Positive pairs: channels confirmed to be from the same operator
(same category scam channels share similar behavioral patterns).

Negative pairs: channels from different operators
(scam vs legitimate, different scam categories).

Author: CyberLens Team — GPCSSI Internship
"""

import itertools
import json
import logging
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("cyberlens.fingerprinting.training_data")


@dataclass
class FingerprintPair:
    """A training pair for the Siamese network."""
    fp1_channel: str
    fp2_channel: str
    fp1_vector: List[float]
    fp2_vector: List[float]
    label: int  # 1 = same operator, 0 = different operator
    pair_type: str  # "same_category", "cross_category", "scam_vs_legit"


class TrainingDataBuilder:
    """Builds training pairs for the Siamese network from fingerprints.

    Generates positive pairs (same operator → same category scams) and
    negative pairs (different operators → cross-category or scam vs legit).

    Attributes:
        fingerprint_dir: Directory containing fingerprint JSON files.
        labeled_channels_path: Path to labeled_channels.json.
    """

    def __init__(
        self,
        fingerprint_dir: str = "data/processed/fingerprints",
        labeled_channels_path: str = "data/ground_truth/labeled_channels.json",
        output_path: str = "data/processed/siamese_pairs.json",
    ):
        """Initialize the builder.

        Args:
            fingerprint_dir: Directory with fingerprint JSON files.
            labeled_channels_path: Path to labeled_channels.json.
            output_path: Path for output pairs JSON.
        """
        self.fingerprint_dir = Path(fingerprint_dir)
        self.labeled_channels_path = Path(labeled_channels_path)
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_fingerprints(self) -> Dict[str, Dict[str, Any]]:
        """Load all fingerprint files from disk.

        Returns:
            Dict mapping channel_name → fingerprint dict.
        """
        fingerprints = {}
        if not self.fingerprint_dir.exists():
            logger.warning("Fingerprint dir not found: %s", self.fingerprint_dir)
            return fingerprints

        for fp_file in self.fingerprint_dir.glob("*.json"):
            try:
                with open(fp_file, "r") as f:
                    data = json.load(f)
                channel = data.get("channel_name", fp_file.stem)
                if "feature_vector" in data:
                    fingerprints[channel] = data
            except Exception as e:
                logger.warning("Could not load %s: %s", fp_file, e)

        logger.info("Loaded %d fingerprints from %s", len(fingerprints), self.fingerprint_dir)
        return fingerprints

    def _load_labels(self) -> Dict[str, Dict[str, str]]:
        """Load channel labels and categories.

        Returns:
            Dict mapping channel_name → {label, category}.
        """
        if not self.labeled_channels_path.exists():
            logger.warning("Labeled channels not found: %s", self.labeled_channels_path)
            return {}

        with open(self.labeled_channels_path, "r") as f:
            channels = json.load(f)

        labels = {}
        for ch in channels:
            labels[ch["channel"]] = {
                "label": ch["label"],
                "category": ch.get("category", "unknown"),
            }
        return labels

    def build_same_operator_pairs(
        self,
        fingerprints: Optional[Dict] = None,
        labels: Optional[Dict] = None,
        min_pairs: int = 200,
    ) -> List[FingerprintPair]:
        """Build positive (same-operator) pairs.

        Same-category scam channels are treated as coming from the same
        operator archetype. Pairs within the same category are positive.

        To reach min_pairs, we also add augmented copies with small noise.

        Args:
            fingerprints: Pre-loaded fingerprints (optional).
            labels: Pre-loaded labels (optional).
            min_pairs: Minimum number of positive pairs to generate.

        Returns:
            List of positive FingerprintPair (label=1).
        """
        if fingerprints is None:
            fingerprints = self._load_fingerprints()
        if labels is None:
            labels = self._load_labels()

        # Group channels by category
        category_groups: Dict[str, List[str]] = {}
        for channel, info in labels.items():
            if channel in fingerprints and info["label"] == "CONFIRMED_SCAM":
                cat = info["category"]
                category_groups.setdefault(cat, []).append(channel)

        pairs: List[FingerprintPair] = []

        # Natural pairs within same category
        for cat, channels in category_groups.items():
            if len(channels) < 2:
                continue
            for ch1, ch2 in itertools.combinations(channels, 2):
                fp1 = fingerprints[ch1]["feature_vector"]
                fp2 = fingerprints[ch2]["feature_vector"]
                pairs.append(FingerprintPair(
                    fp1_channel=ch1,
                    fp2_channel=ch2,
                    fp1_vector=fp1,
                    fp2_vector=fp2,
                    label=1,
                    pair_type="same_category",
                ))

        # Augment with noisy copies to reach min_pairs
        if len(pairs) < min_pairs:
            augmented = self._augment_pairs(
                pairs, fingerprints, min_pairs - len(pairs)
            )
            pairs.extend(augmented)

        logger.info("Built %d positive (same-operator) pairs", len(pairs))
        return pairs

    def build_different_operator_pairs(
        self,
        fingerprints: Optional[Dict] = None,
        labels: Optional[Dict] = None,
        min_pairs: int = 400,
    ) -> List[FingerprintPair]:
        """Build negative (different-operator) pairs.

        Cross-category scam channels and scam-vs-legitimate pairs
        are treated as different operators.

        Args:
            fingerprints: Pre-loaded fingerprints (optional).
            labels: Pre-loaded labels (optional).
            min_pairs: Minimum number of negative pairs.

        Returns:
            List of negative FingerprintPair (label=0).
        """
        if fingerprints is None:
            fingerprints = self._load_fingerprints()
        if labels is None:
            labels = self._load_labels()

        scam_channels = [
            ch for ch, info in labels.items()
            if ch in fingerprints and info["label"] == "CONFIRMED_SCAM"
        ]
        legit_channels = [
            ch for ch, info in labels.items()
            if ch in fingerprints and info["label"] == "CONFIRMED_LEGITIMATE"
        ]

        pairs: List[FingerprintPair] = []

        # Cross-category scam pairs
        category_map = {
            ch: labels[ch]["category"] for ch in scam_channels
        }
        for ch1, ch2 in itertools.combinations(scam_channels, 2):
            if category_map.get(ch1) != category_map.get(ch2):
                fp1 = fingerprints[ch1]["feature_vector"]
                fp2 = fingerprints[ch2]["feature_vector"]
                pairs.append(FingerprintPair(
                    fp1_channel=ch1,
                    fp2_channel=ch2,
                    fp1_vector=fp1,
                    fp2_vector=fp2,
                    label=0,
                    pair_type="cross_category",
                ))

        # Scam vs legitimate pairs
        for scam_ch in scam_channels:
            for legit_ch in legit_channels:
                if scam_ch in fingerprints and legit_ch in fingerprints:
                    fp1 = fingerprints[scam_ch]["feature_vector"]
                    fp2 = fingerprints[legit_ch]["feature_vector"]
                    pairs.append(FingerprintPair(
                        fp1_channel=scam_ch,
                        fp2_channel=legit_ch,
                        fp1_vector=fp1,
                        fp2_vector=fp2,
                        label=0,
                        pair_type="scam_vs_legit",
                    ))

        # Shuffle and limit
        random.shuffle(pairs)
        if len(pairs) > min_pairs * 2:
            pairs = pairs[:min_pairs * 2]

        # Augment if needed
        if len(pairs) < min_pairs:
            augmented = self._augment_pairs(
                pairs, fingerprints, min_pairs - len(pairs),
            )
            pairs.extend(augmented)

        logger.info("Built %d negative (different-operator) pairs", len(pairs))
        return pairs

    def _augment_pairs(
        self,
        existing_pairs: List[FingerprintPair],
        fingerprints: Dict,
        needed: int,
    ) -> List[FingerprintPair]:
        """Generate augmented pairs by adding small Gaussian noise.

        Args:
            existing_pairs: Pairs to augment from.
            fingerprints: All fingerprints.
            needed: Number of augmented pairs to generate.

        Returns:
            List of augmented FingerprintPair.
        """
        if not existing_pairs:
            # Generate self-pairs with noise from available fingerprints
            augmented = []
            fp_list = list(fingerprints.items())
            for _ in range(needed):
                ch, fp_data = random.choice(fp_list)
                vec = fp_data["feature_vector"]
                noisy = [v + random.gauss(0, 0.05) for v in vec]
                augmented.append(FingerprintPair(
                    fp1_channel=ch,
                    fp2_channel=f"{ch}_aug",
                    fp1_vector=vec,
                    fp2_vector=noisy,
                    label=1,
                    pair_type="augmented_self",
                ))
            return augmented

        augmented = []
        for _ in range(needed):
            base = random.choice(existing_pairs)
            noise1 = [v + random.gauss(0, 0.03) for v in base.fp1_vector]
            noise2 = [v + random.gauss(0, 0.03) for v in base.fp2_vector]
            augmented.append(FingerprintPair(
                fp1_channel=f"{base.fp1_channel}_aug",
                fp2_channel=f"{base.fp2_channel}_aug",
                fp1_vector=noise1,
                fp2_vector=noise2,
                label=base.label,
                pair_type=f"augmented_{base.pair_type}",
            ))
        return augmented

    def build_all(self) -> Tuple[List[FingerprintPair], List[FingerprintPair]]:
        """Build all positive and negative pairs.

        Returns:
            Tuple of (positive_pairs, negative_pairs).
        """
        fingerprints = self._load_fingerprints()
        labels = self._load_labels()

        positive = self.build_same_operator_pairs(fingerprints, labels)
        negative = self.build_different_operator_pairs(fingerprints, labels)

        return positive, negative

    def save_pairs(
        self,
        positive: Optional[List[FingerprintPair]] = None,
        negative: Optional[List[FingerprintPair]] = None,
    ) -> None:
        """Save all pairs to JSON.

        Args:
            positive: Positive pairs (built if None).
            negative: Negative pairs (built if None).
        """
        if positive is None or negative is None:
            positive, negative = self.build_all()

        all_pairs = [asdict(p) for p in positive + negative]
        random.shuffle(all_pairs)

        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump({
                "total_pairs": len(all_pairs),
                "positive_pairs": len(positive),
                "negative_pairs": len(negative),
                "pairs": all_pairs,
            }, f, indent=2)

        logger.info(
            "Saved %d pairs (%d pos, %d neg) → %s",
            len(all_pairs), len(positive), len(negative), self.output_path,
        )
