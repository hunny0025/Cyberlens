#!/usr/bin/env python3
"""
CyberLens — EfficientNet-B4 Deepfake Detector Training
=========================================================
Fine-tunes EfficientNet-B4 on synthetic deepfake data.
Auto-detects GPU and adjusts batch size.

Usage:
    python scripts/train_deepfake.py
    python scripts/train_deepfake.py --epochs 20 --lr 1e-4

Author: CyberLens Team — GPCSSI Internship
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms
from tqdm import tqdm
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "deepfake_training.log"),
    ],
)
logger = logging.getLogger("cyberlens.train_deepfake")


# ---------------------------------------------------------------------------
# GPU detection
# ---------------------------------------------------------------------------

def detect_gpu() -> dict:
    """Detect GPU and determine batch size."""
    config = {"device": "cpu", "batch_size": 8, "fp16": False}
    if torch.cuda.is_available():
        config["device"] = "cuda"
        props = torch.cuda.get_device_properties(0)
        vram_gb = props.total_mem / (1024 ** 3)
        config["fp16"] = True
        config["batch_size"] = 32 if vram_gb >= 8 else 8
        logger.info("GPU: %s (%.1f GB) -> batch=%d", props.name, vram_gb, config["batch_size"])
    else:
        logger.warning("No GPU — training on CPU")
    return config


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class DeepfakeDataset(Dataset):
    """Dataset for deepfake detection training."""

    TRANSFORM_TRAIN = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        transforms.RandomRotation(10),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    TRANSFORM_VAL = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    def __init__(self, root_dir: str, split: str = "train"):
        self.root = Path(root_dir) / split
        self.transform = self.TRANSFORM_TRAIN if split == "train" else self.TRANSFORM_VAL
        self.samples = []

        # Load real (label=0) and fake (label=1) images
        real_dir = self.root / "real"
        fake_dir = self.root / "fake"

        if real_dir.exists():
            for f in real_dir.iterdir():
                if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    self.samples.append((str(f), 0))

        if fake_dir.exists():
            for f in fake_dir.iterdir():
                if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    self.samples.append((str(f), 1))

        logger.info("Loaded %d samples from %s", len(self.samples), self.root)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        image = Image.open(path).convert("RGB")
        image = self.transform(image)
        return image, torch.tensor(label, dtype=torch.long)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(args):
    gpu_config = detect_gpu()
    device = torch.device(gpu_config["device"])
    batch_size = args.batch_size or gpu_config["batch_size"]

    data_dir = PROJECT_ROOT / args.data_dir
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check data exists
    if not (data_dir / "train").exists():
        logger.error("Training data not found at %s. Run prepare_deepfake_data.py first.", data_dir)
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("  CyberLens — Deepfake Detector Training")
    logger.info("  Model: EfficientNet-B4")
    logger.info("  Device: %s", device)
    logger.info("=" * 60)

    # Data
    train_dataset = DeepfakeDataset(str(data_dir), "train")
    val_dataset = DeepfakeDataset(str(data_dir), "val")

    if len(train_dataset) == 0:
        logger.error("No training images found. Run prepare_deepfake_data.py first.")
        sys.exit(1)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=0)

    # Model
    model = models.efficientnet_b4(weights=models.EfficientNet_B4_Weights.DEFAULT)
    num_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.4, inplace=True),
        nn.Linear(num_features, 2),
    )
    model = model.to(device)

    # Optimizer with differential learning rates
    backbone_params = [p for n, p in model.named_parameters() if "classifier" not in n]
    head_params = [p for n, p in model.named_parameters() if "classifier" in n]
    optimizer = AdamW([
        {"params": backbone_params, "lr": args.lr * 0.1},
        {"params": head_params, "lr": args.lr},
    ], weight_decay=0.01)

    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs)
    criterion = nn.CrossEntropyLoss()
    scaler = torch.amp.GradScaler("cuda") if gpu_config["fp16"] else None

    # Training loop
    best_auc = 0.0
    metrics_history = []

    for epoch in range(args.epochs):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{args.epochs}")
        for images, labels in pbar:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()

            if scaler:
                with torch.amp.autocast("cuda"):
                    outputs = model(images)
                    loss = criterion(outputs, labels)
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
            else:
                outputs = model(images)
                loss = criterion(outputs, labels)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()

            running_loss += loss.item()
            _, predicted = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
            pbar.set_postfix(loss=f"{loss.item():.4f}", acc=f"{correct/total:.4f}")

        scheduler.step()
        train_loss = running_loss / len(train_loader)
        train_acc = correct / total

        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        all_probs = []
        all_labels = []

        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                loss = criterion(outputs, labels)
                val_loss += loss.item()
                probs = torch.softmax(outputs, dim=1)[:, 1]
                all_probs.extend(probs.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())
                _, predicted = torch.max(outputs, 1)
                val_total += labels.size(0)
                val_correct += (predicted == labels).sum().item()

        val_loss /= max(len(val_loader), 1)
        val_acc = val_correct / max(val_total, 1)

        # Compute AUC
        try:
            from sklearn.metrics import roc_auc_score
            val_auc = roc_auc_score(all_labels, all_probs)
        except Exception:
            val_auc = val_acc  # Fallback

        epoch_metrics = {
            "epoch": epoch + 1,
            "train_loss": round(train_loss, 4),
            "train_acc": round(train_acc, 4),
            "val_loss": round(val_loss, 4),
            "val_acc": round(val_acc, 4),
            "val_auc": round(val_auc, 4),
        }
        metrics_history.append(epoch_metrics)

        logger.info(
            "Epoch %d/%d: train_loss=%.4f train_acc=%.4f val_loss=%.4f val_acc=%.4f val_auc=%.4f",
            epoch + 1, args.epochs, train_loss, train_acc, val_loss, val_acc, val_auc,
        )

        # Save best model
        if val_auc > best_auc:
            best_auc = val_auc
            torch.save(model.state_dict(), output_dir / "best_model.pth")
            logger.info("  -> New best model! AUC=%.4f", val_auc)

    # Save final metrics
    with open(output_dir / "training_metrics.json", "w") as f:
        json.dump(metrics_history, f, indent=2)

    # Save training curves
    _save_curves(metrics_history, output_dir)

    # ── Evaluation with confusion matrix and ROC ─────────────
    logger.info("Generating deepfake evaluation outputs...")
    _save_deepfake_evaluation(
        model, val_loader, device, output_dir,
        all_probs, all_labels,
    )

    logger.info("=" * 60)
    logger.info("  Training complete! Best AUC: %.4f", best_auc)
    logger.info("  Model saved to: %s", output_dir)
    logger.info("=" * 60)


def _save_curves(metrics, output_dir):
    """Save training curves plot."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        epochs = [m["epoch"] for m in metrics]

        fig, axes = plt.subplots(1, 3, figsize=(15, 4))

        # Loss
        axes[0].plot(epochs, [m["train_loss"] for m in metrics], label="Train")
        axes[0].plot(epochs, [m["val_loss"] for m in metrics], label="Val")
        axes[0].set_title("Loss")
        axes[0].legend()
        axes[0].set_xlabel("Epoch")

        # Accuracy
        axes[1].plot(epochs, [m["train_acc"] for m in metrics], label="Train")
        axes[1].plot(epochs, [m["val_acc"] for m in metrics], label="Val")
        axes[1].set_title("Accuracy")
        axes[1].legend()
        axes[1].set_xlabel("Epoch")

        # AUC
        axes[2].plot(epochs, [m["val_auc"] for m in metrics], label="Val AUC", color="green")
        axes[2].set_title("Validation AUC")
        axes[2].legend()
        axes[2].set_xlabel("Epoch")

        plt.tight_layout()
        plt.savefig(output_dir / "curves.png", dpi=150)
        plt.close()
        logger.info("Training curves saved -> %s", output_dir / "curves.png")
    except ImportError:
        logger.warning("matplotlib not available — skipping curves plot")


def _save_deepfake_evaluation(model, val_loader, device, output_dir, all_probs, all_labels):
    """Generate deepfake confusion matrix, ROC curve, and eval report.

    Args:
        model: Trained EfficientNet model.
        val_loader: Validation DataLoader.
        device: Torch device.
        output_dir: Output directory for plots and report.
        all_probs: Predicted probabilities for deepfake class.
        all_labels: Ground truth labels (0=real, 1=deepfake).
    """
    all_probs = np.array(all_probs)
    all_labels = np.array(all_labels)

    # Find optimal threshold (minimize FP while maintaining recall)
    best_threshold = 0.5
    best_score = -1.0
    for t in np.arange(0.3, 0.95, 0.01):
        preds = (all_probs >= t).astype(int)
        tp = np.sum((preds == 1) & (all_labels == 1))
        fp = np.sum((preds == 1) & (all_labels == 0))
        fn = np.sum((preds == 0) & (all_labels == 1))
        tn = np.sum((preds == 0) & (all_labels == 0))

        fpr = fp / max(fp + tn, 1)
        recall = tp / max(tp + fn, 1)
        # Optimize: high recall with low FPR (law enforcement priority)
        score = recall - 2.0 * fpr  # Penalize FP more
        if score > best_score:
            best_score = score
            best_threshold = float(t)

    # Compute metrics at recommended threshold
    preds = (all_probs >= best_threshold).astype(int)
    tp = int(np.sum((preds == 1) & (all_labels == 1)))
    fp = int(np.sum((preds == 1) & (all_labels == 0)))
    tn = int(np.sum((preds == 0) & (all_labels == 0)))
    fn = int(np.sum((preds == 0) & (all_labels == 1)))

    total = tp + fp + tn + fn
    fpr = fp / max(fp + tn, 1)
    fnr = fn / max(fn + tp, 1)

    # AUC
    try:
        from sklearn.metrics import roc_auc_score, roc_curve
        auc = float(roc_auc_score(all_labels, all_probs))
        fpr_curve, tpr_curve, _ = roc_curve(all_labels, all_probs)
    except Exception:
        auc = 0.0
        fpr_curve, tpr_curve = [0, 1], [0, 1]

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns

        # ── Confusion matrix with law enforcement framing ────
        cm = np.array([[tn, fp], [fn, tp]])
        fig, ax = plt.subplots(figsize=(10, 8))

        # Custom colors: FP = red, FN = orange, correct = blue
        colors = np.array([
            ["#4CAF50", "#F44336"],  # TN=green, FP=RED
            ["#FF9800", "#2196F3"],  # FN=ORANGE, TP=blue
        ])

        for i in range(2):
            for j in range(2):
                count = cm[i, j]
                pct = count / max(total, 1) * 100
                ax.add_patch(plt.Rectangle((j, i), 1, 1, fill=True,
                                           color=colors[i, j], alpha=0.3))
                ax.text(j + 0.5, i + 0.5, f"{count}\n({pct:.1f}%)",
                        ha="center", va="center", fontsize=16, fontweight="bold")

        ax.set_xlim(0, 2)
        ax.set_ylim(0, 2)
        ax.set_xticks([0.5, 1.5])
        ax.set_xticklabels(["Real Image", "Deepfake Suspected"], fontsize=12)
        ax.set_yticks([0.5, 1.5])
        ax.set_yticklabels(["Real Image", "Deepfake Suspected"], fontsize=12)
        ax.set_xlabel("Predicted", fontsize=13)
        ax.set_ylabel("Actual", fontsize=13)
        ax.set_title("Deepfake Detector — Binary Classification", fontsize=14, pad=15)
        ax.invert_yaxis()

        # Law enforcement impact text
        impact_text = (
            f"False Positive Rate: {fpr*100:.1f}% — Risk of wrongful content flagging\n"
            f"False Negative Rate: {fnr*100:.1f}% — Risk of missed deepfake\n"
            f"Recommended operating threshold: {best_threshold:.2f} (optimizes for low FP)"
        )
        fig.text(0.5, 0.02, impact_text, ha="center", fontsize=10,
                 style="italic", color="#333333",
                 bbox=dict(boxstyle="round", facecolor="#FFF9C4", alpha=0.8))

        plt.tight_layout(rect=[0, 0.1, 1, 1])
        fig.savefig(output_dir / "confusion_matrix.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        logger.info("Deepfake confusion matrix saved")

        # ── ROC Curve ────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.fill_between(fpr_curve, tpr_curve, alpha=0.2, color="#2196F3")
        ax.plot(fpr_curve, tpr_curve, linewidth=2, color="#2196F3",
                label=f"ROC (AUC = {auc:.4f})")
        ax.plot([0, 1], [0, 1], "k--", linewidth=1, label="Random")

        # Mark operating point
        op_fpr = fp / max(fp + tn, 1)
        op_tpr = tp / max(tp + fn, 1)
        ax.plot(op_fpr, op_tpr, "ro", markersize=12, label=f"Operating Point (t={best_threshold:.2f})")

        ax.set_xlabel("False Positive Rate", fontsize=12)
        ax.set_ylabel("True Positive Rate", fontsize=12)
        ax.set_title("Deepfake Detector — ROC Curve", fontsize=14)
        ax.legend(fontsize=11, loc="lower right")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        fig.savefig(output_dir / "roc_curve.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        logger.info("ROC curve saved")

    except ImportError:
        logger.warning("matplotlib/seaborn not available — skipping deepfake plots")

    # Save eval report
    eval_report = {
        "auc_roc": round(auc, 4),
        "false_positive_rate": round(fpr, 4),
        "false_negative_rate": round(fnr, 4),
        "recommended_threshold": round(best_threshold, 2),
        "confusion_matrix": [[tp, fp], [fn, tn]],
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "total_samples": total,
    }
    with open(output_dir / "eval_report.json", "w") as f:
        json.dump(eval_report, f, indent=2)
    logger.info("Deepfake eval report saved -> %s", output_dir / "eval_report.json")


def parse_args():
    parser = argparse.ArgumentParser(description="Train EfficientNet-B4 Deepfake Detector")
    parser.add_argument("--data-dir", default="data/deepfake")
    parser.add_argument("--output-dir", default="models/deepfake_detector")
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--batch-size", type=int, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    train(parse_args())
