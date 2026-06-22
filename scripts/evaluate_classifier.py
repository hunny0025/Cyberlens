#!/usr/bin/env python3
"""
CyberLens — Scam Classifier Evaluation on Test Set
=====================================================
Loads trained model from models/scam_classifier/ and evaluates on test.json.
Prints full classification report and saves results.

Usage:
    python scripts/evaluate_classifier.py
    python scripts/evaluate_classifier.py --model-dir models/scam_classifier --test-file data/synthetic/test.json

Author: CyberLens Team — GPCSSI Internship
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cyberlens.evaluate")


class TestDataset(Dataset):
    """Simple dataset for evaluation."""

    def __init__(self, data_path: Path, tokenizer, max_length: int = 256):
        with open(data_path, "r", encoding="utf-8") as f:
            self.records = json.load(f)
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> Dict:
        record = self.records[idx]
        encoding = self.tokenizer(
            record["text_content"],
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids": encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
            "label": record["label"],
            "id": record["id"],
        }


def evaluate(args: argparse.Namespace) -> None:
    """Run evaluation on test set."""
    model_dir = PROJECT_ROOT / args.model_dir
    test_file = PROJECT_ROOT / args.test_file
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    logger.info("=" * 60)
    logger.info("  CyberLens — Scam Classifier Evaluation")
    logger.info("  Model: %s", model_dir)
    logger.info("  Test file: %s", test_file)
    logger.info("  Device: %s", device)
    logger.info("=" * 60)

    # Load label map
    label_map_path = model_dir / "label_map.json"
    with open(label_map_path, "r") as f:
        label_map = json.load(f)

    # Load model & tokenizer
    logger.info("Loading model and tokenizer...")
    tokenizer_path = model_dir / "tokenizer"
    if tokenizer_path.exists():
        tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path))
    else:
        tokenizer = AutoTokenizer.from_pretrained(str(model_dir))

    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    model.to(device)
    model.eval()

    # Load test data
    dataset = TestDataset(test_file, tokenizer)
    logger.info("Loaded %d test samples", len(dataset))

    # Run predictions
    all_preds = []
    all_labels = []
    all_probs = []
    misclassified = []

    with torch.no_grad():
        for i in tqdm(range(len(dataset)), desc="Evaluating"):
            item = dataset[i]
            input_ids = item["input_ids"].unsqueeze(0).to(device)
            attention_mask = item["attention_mask"].unsqueeze(0).to(device)
            label = item["label"]

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            probs = torch.softmax(outputs.logits, dim=-1).cpu().numpy()[0]
            pred = int(np.argmax(probs))

            all_preds.append(pred)
            all_labels.append(label)
            all_probs.append(probs.tolist())

            if pred != label:
                misclassified.append({
                    "id": item["id"],
                    "true_label": label,
                    "predicted_label": pred,
                    "confidence": float(probs[pred]),
                })

    # Classification report
    class_names = [label_map[str(i)] for i in range(len(label_map))]
    report = classification_report(
        all_labels, all_preds,
        target_names=class_names,
        digits=4,
    )
    accuracy = accuracy_score(all_labels, all_preds)
    f1 = f1_score(all_labels, all_preds, average="weighted")

    print("\n" + "=" * 60)
    print("  CLASSIFICATION REPORT")
    print("=" * 60)
    print(report)
    print(f"  Overall Accuracy: {accuracy:.4f}")
    print(f"  Weighted F1:      {f1:.4f}")
    print(f"  Misclassified:    {len(misclassified)}/{len(dataset)}")
    print("=" * 60)

    # Confusion matrix
    cm = confusion_matrix(all_labels, all_preds)
    print("\nConfusion Matrix:")
    print(f"{'':>25}", end="")
    for name in class_names:
        print(f"{name[:15]:>16}", end="")
    print()
    for i, row in enumerate(cm):
        print(f"  {class_names[i]:>22}", end="")
        for val in row:
            print(f"{val:>16}", end="")
        print()

    # Save results
    results = {
        "accuracy": accuracy,
        "f1_weighted": f1,
        "total_samples": len(dataset),
        "misclassified_count": len(misclassified),
        "classification_report": classification_report(
            all_labels, all_preds, target_names=class_names,
            digits=4, output_dict=True,
        ),
        "confusion_matrix": cm.tolist(),
        "misclassified_samples": misclassified[:20],
    }

    results_path = model_dir / "test_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info("Results saved → %s", results_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CyberLens — Evaluate Scam Classifier on Test Set",
    )
    parser.add_argument("--model-dir", default="models/scam_classifier",
                        help="Path to trained model directory")
    parser.add_argument("--test-file", default="data/synthetic/test.json",
                        help="Path to test JSON file")
    return parser.parse_args()


if __name__ == "__main__":
    evaluate(parse_args())
