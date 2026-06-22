#!/usr/bin/env python3
"""
CyberLens — IndicBERT Scam Text Classifier Training Pipeline
================================================================
Fine-tunes ai4bharat/indic-bert for multi-class scam classification
on real public data from the CyberLens data collection pipeline.

Supports all 14 dynamic categories from scam_categories.yaml.
Generates 3 confusion matrices (counts, recall, precision),
calibration plot, and full classification report.

Usage:
    python scripts/train_classifier.py
    python scripts/train_classifier.py --epochs 15 --lr 3e-5

Author: CyberLens Team — GPCSSI Internship
"""

import argparse
import json
import logging
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
import yaml
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "training.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("cyberlens.train")

# Multilingual DistilBERT — supports 104 languages including Hindi/English
MODEL_NAME = "distilbert-base-multilingual-cased"


# ---------------------------------------------------------------------------
# Load dynamic categories from YAML
# ---------------------------------------------------------------------------

def load_categories() -> Tuple[Dict[str, str], Dict[int, str], int]:
    """Load scam categories from scam_categories.yaml.

    Returns:
        Tuple of (id_to_label, idx_to_label, num_labels).
    """
    yaml_path = PROJECT_ROOT / "configs" / "scam_categories.yaml"
    if not yaml_path.exists():
        logger.error("scam_categories.yaml not found at %s", yaml_path)
        sys.exit(1)

    with open(yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    id_to_label: Dict[str, str] = {}
    idx = 0
    for group_name, items in config.get("categories", {}).items():
        for item in items:
            cat_id = item["id"]
            cat_label = item["label"]
            id_to_label[cat_id] = cat_label
            idx += 1

    idx_to_label = {i: label for i, label in enumerate(id_to_label.values())}
    num_labels = len(id_to_label)

    logger.info("Loaded %d categories from scam_categories.yaml", num_labels)
    return id_to_label, idx_to_label, num_labels


# Category ID to numeric index mapping
def build_category_index(id_to_label: Dict[str, str]) -> Dict[str, int]:
    """Build category_id → numeric index mapping."""
    return {cat_id: idx for idx, cat_id in enumerate(id_to_label.keys())}


# ---------------------------------------------------------------------------
# GPU detection
# ---------------------------------------------------------------------------

def detect_gpu_config() -> Dict:
    """Detect GPU availability and set safe batch size."""
    config = {"device": "cpu", "batch_size": 8, "fp16": False, "gpu_name": None, "vram_gb": 0}

    if torch.cuda.is_available():
        config["device"] = "cuda"
        gpu_props = torch.cuda.get_device_properties(0)
        config["gpu_name"] = gpu_props.name
        config["vram_gb"] = gpu_props.total_mem / (1024 ** 3)
        config["fp16"] = True
        config["batch_size"] = 32 if config["vram_gb"] >= 8 else (16 if config["vram_gb"] >= 4 else 8)
        logger.info("GPU: %s (%.1f GB) -> batch=%d", config["gpu_name"], config["vram_gb"], config["batch_size"])
    else:
        logger.warning("No GPU detected. Training on CPU (slow).")

    return config


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class ScamTextDataset(Dataset):
    """PyTorch Dataset for multi-class scam text classification."""

    def __init__(self, records: List[Dict], tokenizer, category_index: Dict[str, int], max_length: int = 256):
        self.records = records
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.category_index = category_index
        logger.info("Dataset: %d records", len(self.records))

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        record = self.records[idx]
        text = record.get("text_content", "") or record.get("text", "")
        category = record.get("category", record.get("ground_truth_category", "unknown"))
        label = self.category_index.get(category, 0)

        encoding = self.tokenizer(
            text, max_length=self.max_length, padding="max_length",
            truncation=True, return_tensors="pt",
        )

        return {
            "input_ids": encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
            "labels": torch.tensor(label, dtype=torch.long),
        }


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_training_data(data_dir: Path, category_index: Dict[str, int]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Load training data from processed directory.

    Supports both old format (train.json/val.json) and new unified format.

    Returns:
        Tuple of (train_records, val_records, test_records).
    """
    # Try new unified format first
    unified_path = data_dir / "training_dataset.json"
    if unified_path.exists():
        with open(unified_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        channels = data.get("channels", [])
        records = []
        for ch in channels:
            category = ch.get("ground_truth_category", "unknown")
            if category not in category_index:
                continue
            for post in ch.get("posts", []):
                text = post.get("text", "")
                if text and len(text.strip()) > 10:
                    records.append({"text_content": text, "category": category})

        if not records:
            logger.warning("No text records extracted from unified dataset")
        else:
            logger.info("Extracted %d text records from unified dataset", len(records))

        # Split 80/10/10
        import random
        random.shuffle(records)
        n = len(records)
        train_end = int(0.8 * n)
        val_end = int(0.9 * n)
        return records[:train_end], records[train_end:val_end], records[val_end:]

    # Fallback to old format
    train_path = data_dir / "train.json"
    val_path = data_dir / "val.json"

    if train_path.exists():
        with open(train_path, "r", encoding="utf-8") as f:
            train_records = json.load(f)
        with open(val_path, "r", encoding="utf-8") as f:
            val_records = json.load(f)

        # Split val into val + test
        mid = len(val_records) // 2
        return train_records, val_records[:mid], val_records[mid:]

    logger.error("No training data found in %s", data_dir)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(eval_pred) -> Dict:
    """Compute accuracy, F1, precision, recall for Trainer."""
    predictions, labels = eval_pred
    preds = np.argmax(predictions, axis=1)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average="weighted", zero_division=0)
    acc = accuracy_score(labels, preds)
    return {"accuracy": acc, "f1": f1, "precision": precision, "recall": recall}


# ---------------------------------------------------------------------------
# Confusion matrix generation
# ---------------------------------------------------------------------------

def save_confusion_matrices(trainer, test_dataset, idx_to_label, output_dir):
    """Generate and save 3 confusion matrix visualizations + classification report."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        logger.warning("matplotlib/seaborn not installed — skipping plots")
        return

    predictions = trainer.predict(test_dataset)
    preds = np.argmax(predictions.predictions, axis=1)
    labels = predictions.label_ids
    probs = torch.softmax(torch.tensor(predictions.predictions), dim=-1).numpy()

    class_names = [idx_to_label.get(i, f"Class-{i}") for i in range(len(idx_to_label))]
    # Only include classes present in the test set
    present_classes = sorted(set(labels) | set(preds))
    present_names = [class_names[i] for i in present_classes]

    cm = confusion_matrix(labels, preds, labels=present_classes)
    num_classes = len(present_classes)

    # 1. Raw counts
    fig, ax = plt.subplots(figsize=(max(10, num_classes), max(8, num_classes * 0.8)))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=present_names,
                yticklabels=present_names, ax=ax, annot_kws={"size": 10})
    ax.set_xlabel("Predicted", fontsize=12)
    ax.set_ylabel("Actual", fontsize=12)
    ax.set_title("Scam Classifier — Raw Prediction Counts", fontsize=14, pad=15)
    plt.xticks(rotation=45, ha="right", fontsize=8)
    plt.yticks(fontsize=8)
    plt.tight_layout()
    fig.savefig(output_dir / "confusion_matrix_counts.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 2. Recall-normalized (per row)
    cm_recall = cm.astype(float) / np.maximum(cm.sum(axis=1, keepdims=True), 1)
    fig, ax = plt.subplots(figsize=(max(10, num_classes), max(8, num_classes * 0.8)))
    sns.heatmap(cm_recall, annot=True, fmt=".2f", cmap="Blues", xticklabels=present_names,
                yticklabels=present_names, ax=ax, vmin=0, vmax=1)
    ax.set_xlabel("Predicted", fontsize=12)
    ax.set_ylabel("Actual", fontsize=12)
    ax.set_title("Scam Classifier — Recall Per Category", fontsize=14, pad=15)
    plt.xticks(rotation=45, ha="right", fontsize=8)
    plt.yticks(fontsize=8)
    plt.tight_layout()
    fig.savefig(output_dir / "confusion_matrix_recall.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 3. Precision-normalized (per column)
    cm_prec = cm.astype(float) / np.maximum(cm.sum(axis=0, keepdims=True), 1)
    fig, ax = plt.subplots(figsize=(max(10, num_classes), max(8, num_classes * 0.8)))
    sns.heatmap(cm_prec, annot=True, fmt=".2f", cmap="Blues", xticklabels=present_names,
                yticklabels=present_names, ax=ax, vmin=0, vmax=1)
    ax.set_xlabel("Predicted", fontsize=12)
    ax.set_ylabel("Actual", fontsize=12)
    ax.set_title("Scam Classifier — Precision Per Category", fontsize=14, pad=15)
    plt.xticks(rotation=45, ha="right", fontsize=8)
    plt.yticks(fontsize=8)
    plt.tight_layout()
    fig.savefig(output_dir / "confusion_matrix_precision.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Classification report
    report = classification_report(labels, preds, target_names=present_names, output_dict=True, zero_division=0)

    # Most confused pairs
    confused_pairs = []
    for i in range(num_classes):
        for j in range(num_classes):
            if i != j and cm[i, j] > 0:
                confused_pairs.append({
                    "actual": present_names[i],
                    "predicted": present_names[j],
                    "count": int(cm[i, j]),
                })
    confused_pairs.sort(key=lambda x: x["count"], reverse=True)

    eval_report = {
        "per_class": {
            name: {
                "precision": round(report[name]["precision"], 4),
                "recall": round(report[name]["recall"], 4),
                "f1": round(report[name]["f1-score"], 4),
                "support": int(report[name]["support"]),
            }
            for name in present_names if name in report
        },
        "macro_f1": round(report.get("macro avg", {}).get("f1-score", 0), 4),
        "weighted_f1": round(report.get("weighted avg", {}).get("f1-score", 0), 4),
        "accuracy": round(report.get("accuracy", 0), 4),
        "most_confused_pairs": [
            f"{p['actual']} ↔ {p['predicted']}: confused {p['count']} times"
            for p in confused_pairs[:5]
        ],
        "confusion_matrix": cm.tolist(),
    }

    with open(output_dir / "eval_report.json", "w") as f:
        json.dump(eval_report, f, indent=2)
    logger.info("Eval report saved -> %s", output_dir / "eval_report.json")

    # 4. Calibration plot
    _save_calibration_plot(probs, labels, present_classes, output_dir)

    logger.info("All confusion matrices saved to %s", output_dir)


def _save_calibration_plot(probs, labels, present_classes, output_dir):
    """Generate per-class confidence calibration plot."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    # Get predicted class confidence
    max_probs = np.max(probs, axis=1)
    preds = np.argmax(probs, axis=1)
    correct = (preds == labels).astype(int)

    bins = np.arange(0.0, 1.1, 0.1)
    bin_centers = []
    bin_accuracies = []

    for i in range(len(bins) - 1):
        mask = (max_probs >= bins[i]) & (max_probs < bins[i + 1])
        if mask.sum() > 0:
            bin_centers.append((bins[i] + bins[i + 1]) / 2)
            bin_accuracies.append(correct[mask].mean())

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.plot([0, 1], [0, 1], "k--", label="Perfectly Calibrated", linewidth=1.5)
    ax.plot(bin_centers, bin_accuracies, "o-", label="Model", linewidth=2, color="#2196F3", markersize=8)
    ax.set_xlabel("Predicted Confidence", fontsize=12)
    ax.set_ylabel("Actual Accuracy", fontsize=12)
    ax.set_title("Scam Classifier — Confidence Calibration", fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    plt.tight_layout()
    fig.savefig(output_dir / "calibration_plot.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Calibration plot saved")


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(args):
    """Run the full training pipeline."""
    data_dir = PROJECT_ROOT / args.data_dir
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    gpu_config = detect_gpu_config()

    # Load categories
    id_to_label, idx_to_label, num_labels = load_categories()
    category_index = build_category_index(id_to_label)
    label_map = {str(i): label for i, label in idx_to_label.items()}

    logger.info("=" * 60)
    logger.info("  CyberLens — IndicBERT Scam Classifier Training")
    logger.info("  Model: %s", MODEL_NAME)
    logger.info("  Categories: %d", num_labels)
    logger.info("  Device: %s", gpu_config["device"])
    logger.info("=" * 60)

    # Load tokenizer and model
    logger.info("Loading tokenizer and model: %s", MODEL_NAME)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=num_labels,
        id2label={str(i): idx_to_label[i] for i in range(num_labels)},
        label2id={v: k for k, v in idx_to_label.items()},
    )

    # Load data
    train_records, val_records, test_records = load_training_data(data_dir, category_index)

    train_dataset = ScamTextDataset(train_records, tokenizer, category_index, args.max_length)
    val_dataset = ScamTextDataset(val_records, tokenizer, category_index, args.max_length)
    test_dataset = ScamTextDataset(test_records, tokenizer, category_index, args.max_length)

    # Training
    batch_size = args.batch_size or gpu_config["batch_size"]
    training_args = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size * 2,
        learning_rate=args.lr,
        warmup_ratio=0.1,
        weight_decay=0.01,
        fp16=gpu_config["fp16"],
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        save_total_limit=3,
        report_to="none",
        dataloader_num_workers=0 if sys.platform == "win32" else 2,
        disable_tqdm=False,
    )

    trainer = Trainer(
        model=model, args=training_args,
        train_dataset=train_dataset, eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=args.patience)],
    )

    logger.info("Training — %d epochs, batch=%d, lr=%.1e", args.epochs, batch_size, args.lr)
    train_result = trainer.train()

    # Save model
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir / "tokenizer"))
    with open(output_dir / "label_map.json", "w") as f:
        json.dump(label_map, f, indent=2)
    with open(output_dir / "category_index.json", "w") as f:
        json.dump(category_index, f, indent=2)

    # Evaluate
    eval_results = trainer.evaluate()
    logger.info("Validation: %s", eval_results)

    # Save training metrics
    with open(output_dir / "training_metrics.json", "w") as f:
        json.dump({
            "train_loss": train_result.training_loss,
            "eval_accuracy": eval_results.get("eval_accuracy", 0),
            "eval_f1": eval_results.get("eval_f1", 0),
            "model": MODEL_NAME,
            "epochs": args.epochs,
            "num_categories": num_labels,
            "gpu": gpu_config["gpu_name"],
        }, f, indent=2)

    # Generate confusion matrices on TEST set
    logger.info("Generating confusion matrices on test set...")
    save_confusion_matrices(trainer, test_dataset, idx_to_label, output_dir)

    logger.info("=" * 60)
    logger.info("  Training complete!")
    logger.info("  Model: %s -> %s", MODEL_NAME, output_dir)
    logger.info("  F1: %.4f | Acc: %.4f", eval_results.get("eval_f1", 0), eval_results.get("eval_accuracy", 0))
    logger.info("=" * 60)


def parse_args():
    parser = argparse.ArgumentParser(description="CyberLens — Train IndicBERT Scam Classifier")
    parser.add_argument("--data-dir", default="data/processed", help="Directory with training data")
    parser.add_argument("--output-dir", default="models/scam_classifier")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--patience", type=int, default=3)
    return parser.parse_args()


if __name__ == "__main__":
    train(parse_args())
