#!/usr/bin/env python3
"""
CyberLens — Siamese Fingerprinter Training Script
=====================================================
Trains the Siamese network on behavioral fingerprint pairs
for operator attribution.

Generates confusion matrix, threshold sweep plot, and
full evaluation report.

Usage:
    python scripts/train_fingerprinter.py
    python scripts/train_fingerprinter.py --epochs 50 --lr 1e-3

Author: CyberLens Team — GPCSSI Internship
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "fingerprinter_training.log"),
    ],
)
logger = logging.getLogger("cyberlens.train_fingerprinter")


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class SiamesePairDataset(Dataset):
    """Dataset of fingerprint pairs for Siamese training."""

    def __init__(self, pairs: list):
        self.pairs = pairs

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, idx):
        p = self.pairs[idx]
        fp1 = torch.tensor(p["fp1_vector"], dtype=torch.float32)
        fp2 = torch.tensor(p["fp2_vector"], dtype=torch.float32)
        label = torch.tensor(p["label"], dtype=torch.float32)
        return fp1, fp2, label


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_model(model, dataloader, device, threshold=0.75):
    """Evaluate model and compute metrics at a given threshold.

    Returns:
        Dict with TP, FP, TN, FN, precision, recall, f1, all_scores, all_labels.
    """
    model.eval()
    all_scores = []
    all_labels = []

    with torch.no_grad():
        for fp1, fp2, labels in dataloader:
            fp1, fp2 = fp1.to(device), fp2.to(device)
            scores = model(fp1, fp2).cpu().numpy()
            all_scores.extend(scores.tolist())
            all_labels.extend(labels.numpy().tolist())

    all_scores = np.array(all_scores)
    all_labels = np.array(all_labels)
    preds = (all_scores >= threshold).astype(int)

    tp = int(np.sum((preds == 1) & (all_labels == 1)))
    fp = int(np.sum((preds == 1) & (all_labels == 0)))
    tn = int(np.sum((preds == 0) & (all_labels == 0)))
    fn = int(np.sum((preds == 0) & (all_labels == 1)))

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-8)
    fpr = fp / max(fp + tn, 1)

    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "all_scores": all_scores,
        "all_labels": all_labels,
    }


def threshold_sweep(all_scores, all_labels):
    """Sweep thresholds and compute P/R/F1 at each.

    Returns:
        List of dicts with threshold, precision, recall, f1.
    """
    results = []
    for t in np.arange(0.1, 1.0, 0.01):
        preds = (all_scores >= t).astype(int)
        tp = np.sum((preds == 1) & (all_labels == 1))
        fp = np.sum((preds == 1) & (all_labels == 0))
        fn = np.sum((preds == 0) & (all_labels == 1))

        p = tp / max(tp + fp, 1)
        r = tp / max(tp + fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)
        results.append({"threshold": round(float(t), 2), "precision": p, "recall": r, "f1": f1})
    return results


def compute_auc(all_scores, all_labels):
    """Compute AUC-ROC."""
    try:
        from sklearn.metrics import roc_auc_score
        return round(float(roc_auc_score(all_labels, all_scores)), 4)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def save_confusion_matrix(metrics, output_dir):
    """Generate and save confusion matrix heatmap."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        logger.warning("matplotlib/seaborn not available — skipping plots")
        return

    cm = np.array([
        [metrics["tn"], metrics["fp"]],
        [metrics["fn"], metrics["tp"]],
    ])
    total = cm.sum()
    labels_text = np.array([
        [f"{cm[0,0]}\n({cm[0,0]/total*100:.1f}%)", f"{cm[0,1]}\n({cm[0,1]/total*100:.1f}%)"],
        [f"{cm[1,0]}\n({cm[1,0]/total*100:.1f}%)", f"{cm[1,1]}\n({cm[1,1]/total*100:.1f}%)"],
    ])

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        cm, annot=labels_text, fmt="", cmap="Blues",
        xticklabels=["Different Operator", "Same Operator"],
        yticklabels=["Different Operator", "Same Operator"],
        ax=ax, annot_kws={"size": 14, "fontweight": "bold"},
    )
    ax.set_xlabel("Predicted", fontsize=12)
    ax.set_ylabel("Actual", fontsize=12)
    ax.set_title("Siamese Fingerprinter — Operator Attribution", fontsize=14, pad=15)

    plt.tight_layout()
    path = output_dir / "confusion_matrix.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Confusion matrix -> %s", path)


def save_threshold_sweep_plot(sweep_results, optimal_threshold, output_dir):
    """Generate threshold sweep plot with P/R/F1 curves."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    thresholds = [r["threshold"] for r in sweep_results]
    precisions = [r["precision"] for r in sweep_results]
    recalls = [r["recall"] for r in sweep_results]
    f1s = [r["f1"] for r in sweep_results]

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.plot(thresholds, precisions, label="Precision", linewidth=2, color="#2196F3")
    ax.plot(thresholds, recalls, label="Recall", linewidth=2, color="#4CAF50")
    ax.plot(thresholds, f1s, label="F1 Score", linewidth=2, color="#FF9800")
    ax.axvline(x=optimal_threshold, color="red", linestyle="--", linewidth=1.5,
               label=f"Optimal: {optimal_threshold:.2f}")
    ax.set_xlabel("Threshold", fontsize=12)
    ax.set_ylabel("Score", fontsize=12)
    ax.set_title("Siamese Fingerprinter — Threshold Sweep", fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = output_dir / "threshold_sweep.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Threshold sweep -> %s", path)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(args):
    """Run the full Siamese network training pipeline."""
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    pairs_path = PROJECT_ROOT / args.pairs_path

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    logger.info("=" * 60)
    logger.info("  CyberLens — Siamese Fingerprinter Training")
    logger.info("  Device: %s", device)
    logger.info("=" * 60)

    # Load pairs
    if pairs_path.exists():
        with open(pairs_path, "r") as f:
            data = json.load(f)
        all_pairs = data.get("pairs", [])
    else:
        logger.info("No pairs file found — building from fingerprints...")
        from src.fingerprinting.training_data_builder import TrainingDataBuilder
        builder = TrainingDataBuilder()
        positive, negative = builder.build_all()
        builder.save_pairs(positive, negative)
        with open(builder.output_path, "r") as f:
            data = json.load(f)
        all_pairs = data.get("pairs", [])

    if not all_pairs:
        logger.error("No training pairs available. Run collect_training_data.py first.")
        sys.exit(1)

    logger.info("Total pairs: %d", len(all_pairs))

    # Split: 80/10/10
    import random
    random.shuffle(all_pairs)
    n = len(all_pairs)
    train_end = int(0.8 * n)
    val_end = int(0.9 * n)

    train_pairs = all_pairs[:train_end]
    val_pairs = all_pairs[train_end:val_end]
    test_pairs = all_pairs[val_end:]

    logger.info("Split: train=%d, val=%d, test=%d", len(train_pairs), len(val_pairs), len(test_pairs))

    train_dataset = SiamesePairDataset(train_pairs)
    val_dataset = SiamesePairDataset(val_pairs)
    test_dataset = SiamesePairDataset(test_pairs)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size)

    # Model
    from src.fingerprinting.siamese_network import SiameseNetwork, ContrastiveLoss

    model = SiameseNetwork(input_dim=28, embed_dim=16).to(device)
    criterion = ContrastiveLoss(margin=0.5)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    best_f1 = 0.0

    for epoch in range(args.epochs):
        model.train()
        total_loss = 0.0

        for fp1, fp2, labels in train_loader:
            fp1, fp2, labels = fp1.to(device), fp2.to(device), labels.to(device)
            optimizer.zero_grad()
            similarity = model(fp1, fp2)
            loss = criterion(similarity, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        avg_loss = total_loss / max(len(train_loader), 1)

        # Validate
        val_metrics = evaluate_model(model, val_loader, device, threshold=0.75)

        logger.info(
            "Epoch %d/%d: loss=%.4f | P=%.3f R=%.3f F1=%.3f FPR=%.3f",
            epoch + 1, args.epochs, avg_loss,
            val_metrics["precision"], val_metrics["recall"],
            val_metrics["f1"], val_metrics["false_positive_rate"],
        )

        if val_metrics["f1"] > best_f1:
            best_f1 = val_metrics["f1"]
            torch.save(model.state_dict(), output_dir / "best_model.pth")
            logger.info("  -> New best model! F1=%.4f", best_f1)

    # Load best model for evaluation
    model.load_state_dict(torch.load(output_dir / "best_model.pth", map_location=device))

    # Final evaluation on test set
    logger.info("Running final evaluation on test set...")
    test_metrics = evaluate_model(model, test_loader, device, threshold=0.75)

    # Threshold sweep
    sweep = threshold_sweep(test_metrics["all_scores"], test_metrics["all_labels"])
    optimal_idx = max(range(len(sweep)), key=lambda i: sweep[i]["f1"])
    optimal_threshold = sweep[optimal_idx]["threshold"]

    # Re-evaluate at optimal threshold
    opt_metrics = evaluate_model(model, test_loader, device, threshold=optimal_threshold)
    auc = compute_auc(test_metrics["all_scores"], test_metrics["all_labels"])

    # Generate plots
    save_confusion_matrix(opt_metrics, output_dir)
    save_threshold_sweep_plot(sweep, optimal_threshold, output_dir)

    # Save evaluation report
    eval_report = {
        "precision": opt_metrics["precision"],
        "recall": opt_metrics["recall"],
        "f1": opt_metrics["f1"],
        "auc": auc,
        "false_positive_rate": opt_metrics["false_positive_rate"],
        "optimal_threshold": optimal_threshold,
        "confusion_matrix": [
            [opt_metrics["tn"], opt_metrics["fp"]],
            [opt_metrics["fn"], opt_metrics["tp"]],
        ],
        "at_default_threshold_0.75": {
            "tp": test_metrics["tp"],
            "fp": test_metrics["fp"],
            "tn": test_metrics["tn"],
            "fn": test_metrics["fn"],
            "f1": test_metrics["f1"],
        },
        "total_test_pairs": len(test_pairs),
    }

    with open(output_dir / "eval_report.json", "w") as f:
        json.dump(eval_report, f, indent=2)

    logger.info("=" * 60)
    logger.info("  Training complete!")
    logger.info("  Best F1: %.4f | AUC: %.4f", opt_metrics["f1"], auc)
    logger.info("  Optimal threshold: %.2f", optimal_threshold)
    logger.info("  FPR: %.4f", opt_metrics["false_positive_rate"])
    logger.info("  Model: %s", output_dir)
    logger.info("=" * 60)


def parse_args():
    parser = argparse.ArgumentParser(description="Train Siamese Fingerprinter")
    parser.add_argument("--pairs-path", default="data/processed/siamese_pairs.json")
    parser.add_argument("--output-dir", default="models/fingerprinter")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--batch-size", type=int, default=32)
    return parser.parse_args()


if __name__ == "__main__":
    train(parse_args())
