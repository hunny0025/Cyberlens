#!/usr/bin/env python3
"""
CyberLens — Unified Model Evaluation Script
================================================
Runs evaluation on ALL CyberLens models and generates
a unified evaluation report with confusion matrices,
ROC curves, and comparative metrics.

Output:
    reports/model_evaluation/unified_eval_report.json
    reports/model_evaluation/decision_confusion_matrix.png
    reports/model_evaluation/decision_binary_matrix.png
    reports/model_evaluation/summary_table.png

Usage:
    python scripts/evaluate_all_models.py
    python scripts/evaluate_all_models.py --models fingerprinter,classifier

Author: CyberLens Team — GPCSSI Internship
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "model_evaluation.log"),
    ],
)
logger = logging.getLogger("cyberlens.evaluate")

REPORT_DIR = PROJECT_ROOT / "reports" / "model_evaluation"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Model evaluation loaders
# ---------------------------------------------------------------------------

def load_fingerprinter_eval() -> Dict[str, Any]:
    """Load fingerprinter evaluation report."""
    path = PROJECT_ROOT / "models" / "fingerprinter" / "eval_report.json"
    if path.exists():
        with open(path, "r") as f:
            data = json.load(f)
        data["model_name"] = "Siamese Fingerprinter"
        data["model_type"] = "binary"
        data["status"] = "evaluated"
        return data
    return {"model_name": "Siamese Fingerprinter", "status": "not_trained"}


def load_classifier_eval() -> Dict[str, Any]:
    """Load classifier evaluation report."""
    path = PROJECT_ROOT / "models" / "scam_classifier" / "eval_report.json"
    if path.exists():
        with open(path, "r") as f:
            data = json.load(f)
        data["model_name"] = "IndicBERT Scam Classifier"
        data["model_type"] = "multiclass"
        data["status"] = "evaluated"
        return data
    return {"model_name": "IndicBERT Scam Classifier", "status": "not_trained"}


def load_deepfake_eval() -> Dict[str, Any]:
    """Load deepfake detector evaluation report."""
    path = PROJECT_ROOT / "models" / "deepfake_detector" / "eval_report.json"
    if path.exists():
        with open(path, "r") as f:
            data = json.load(f)
        data["model_name"] = "EfficientNet-B4 Deepfake Detector"
        data["model_type"] = "binary"
        data["status"] = "evaluated"
        return data
    return {"model_name": "EfficientNet-B4 Deepfake Detector", "status": "not_trained"}


def run_decision_engine_eval() -> Dict[str, Any]:
    """Run decision engine evaluation on test data.

    Uses the training dataset to evaluate decision engine scoring.

    Returns:
        Dict with eval metrics.
    """
    dataset_path = PROJECT_ROOT / "data" / "processed" / "training_dataset.json"

    if not dataset_path.exists():
        return {"model_name": "Decision Scoring Engine", "status": "no_data"}

    try:
        from src.decision.scoring_engine import DecisionScoringEngine
    except ImportError:
        return {"model_name": "Decision Scoring Engine", "status": "import_error"}

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    channels = data.get("channels", [])
    if not channels:
        return {"model_name": "Decision Scoring Engine", "status": "no_channels"}

    engine = DecisionScoringEngine()
    decision_classes = ["IGNORE", "MONITOR", "INVESTIGATE", "ESCALATE", "BLOCK"]

    predictions = []
    actuals = []
    scores = []

    for ch in channels:
        label = ch.get("ground_truth_label", "")
        result = engine.score(ch)
        scores.append(result.composite_score)
        predictions.append(result.decision)

        # Map ground truth to expected decision
        if label == "CONFIRMED_SCAM":
            actuals.append("BLOCK")  # Scams should be blocked
        elif label == "CONFIRMED_LEGITIMATE":
            actuals.append("IGNORE")  # Legit should be ignored
        else:
            actuals.append("MONITOR")  # Unknown → monitor

    # 5-class confusion matrix
    n_classes = len(decision_classes)
    cm5 = np.zeros((n_classes, n_classes), dtype=int)
    for actual, pred in zip(actuals, predictions):
        if actual in decision_classes and pred in decision_classes:
            i = decision_classes.index(actual)
            j = decision_classes.index(pred)
            cm5[i, j] += 1

    # Binary collapse: BLOCK vs NOT_BLOCK
    binary_preds = ["BLOCK" if p == "BLOCK" else "NOT_BLOCK" for p in predictions]
    binary_actuals = ["BLOCK" if a == "BLOCK" else "NOT_BLOCK" for a in actuals]

    tp = sum(1 for p, a in zip(binary_preds, binary_actuals) if p == "BLOCK" and a == "BLOCK")
    fp = sum(1 for p, a in zip(binary_preds, binary_actuals) if p == "BLOCK" and a == "NOT_BLOCK")
    tn = sum(1 for p, a in zip(binary_preds, binary_actuals) if p == "NOT_BLOCK" and a == "NOT_BLOCK")
    fn = sum(1 for p, a in zip(binary_preds, binary_actuals) if p == "NOT_BLOCK" and a == "BLOCK")

    total = tp + fp + tn + fn
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-8)
    fpr = fp / max(fp + tn, 1)

    # Critical errors: legitimate channels classified as BLOCK or ESCALATE
    critical_errors = []
    for i, ch in enumerate(channels):
        if ch.get("ground_truth_label") == "CONFIRMED_LEGITIMATE" and predictions[i] in ["BLOCK", "ESCALATE"]:
            critical_errors.append({
                "channel": ch.get("channel_metadata", {}).get("username", "unknown"),
                "predicted": predictions[i],
                "score": scores[i],
            })

    # Generate plots
    _save_decision_confusion_matrix(cm5, decision_classes, REPORT_DIR)
    _save_decision_binary_matrix(tp, fp, tn, fn, REPORT_DIR)

    return {
        "model_name": "Decision Scoring Engine",
        "model_type": "5class",
        "status": "evaluated",
        "confusion_matrix_5class": cm5.tolist(),
        "binary_collapse": {
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "false_positive_rate": round(fpr, 4),
        },
        "critical_errors": critical_errors[:10],
        "critical_error_count": len(critical_errors),
        "total_evaluated": len(channels),
        "decision_distribution": {
            d: predictions.count(d) for d in decision_classes
        },
    }


def _save_decision_confusion_matrix(cm, classes, output_dir):
    """Generate 5-class decision engine confusion matrix."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        return

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="OrRd",
        xticklabels=classes, yticklabels=classes, ax=ax,
        annot_kws={"size": 12, "fontweight": "bold"},
    )
    ax.set_xlabel("Predicted Decision", fontsize=12)
    ax.set_ylabel("Expected Decision", fontsize=12)
    ax.set_title("Decision Engine — 5-Class Confusion Matrix", fontsize=14, pad=15)
    plt.xticks(rotation=30, ha="right", fontsize=10)
    plt.yticks(fontsize=10)
    plt.tight_layout()
    fig.savefig(output_dir / "decision_confusion_matrix.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Decision 5-class matrix saved")


def _save_decision_binary_matrix(tp, fp, tn, fn, output_dir):
    """Generate BLOCK vs NOT_BLOCK binary confusion matrix."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        return

    cm = np.array([[tn, fp], [fn, tp]])
    total = cm.sum()
    labels = np.array([
        [f"{tn}\n({tn/total*100:.1f}%)", f"{fp}\n({fp/total*100:.1f}%)"],
        [f"{fn}\n({fn/total*100:.1f}%)", f"{tp}\n({tp/total*100:.1f}%)"],
    ])

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        cm, annot=labels, fmt="", cmap="Blues",
        xticklabels=["NOT BLOCK", "BLOCK"],
        yticklabels=["NOT BLOCK", "BLOCK"],
        ax=ax, annot_kws={"size": 14, "fontweight": "bold"},
    )
    ax.set_xlabel("Predicted", fontsize=12)
    ax.set_ylabel("Actual", fontsize=12)
    ax.set_title("Decision Engine — Binary Collapse (BLOCK vs NOT)", fontsize=14, pad=15)
    plt.tight_layout()
    fig.savefig(output_dir / "decision_binary_matrix.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Decision binary matrix saved")


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

def print_summary_table(models: List[Dict]) -> None:
    """Print formatted summary table to terminal."""
    print("\n" + "=" * 90)
    print("  CyberLens v5.0 -- Model Evaluation Summary")
    print("=" * 90)
    print(f"  {'Model':<35} {'Status':<12} {'F1':<8} {'FPR':<8} {'AUC':<8}")
    print("-" * 90)

    for m in models:
        name = m.get("model_name", "Unknown")[:34]
        status = m.get("status", "unknown")

        if status == "evaluated":
            # Get F1
            f1 = m.get("f1", m.get("weighted_f1", m.get("binary_collapse", {}).get("f1", "-")))
            if isinstance(f1, float):
                f1 = f"{f1:.4f}"

            # Get FPR
            fpr = m.get("false_positive_rate", m.get("binary_collapse", {}).get("false_positive_rate", "-"))
            if isinstance(fpr, float):
                fpr_str = f"{fpr:.4f}"
                if fpr > 0.05:
                    fpr_str += " !!"
            else:
                fpr_str = str(fpr)

            # Get AUC
            auc = m.get("auc", m.get("auc_roc", "-"))
            if isinstance(auc, float):
                auc = f"{auc:.4f}"

            print(f"  {name:<35} {'[OK]':<12} {str(f1):<8} {fpr_str:<8} {str(auc):<8}")
        else:
            print(f"  {name:<35} {'[' + status + ']':<12} {'-':<8} {'-':<8} {'-':<8}")

    print("=" * 90)
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def evaluate(args):
    """Run full model evaluation pipeline."""
    logger.info("=" * 60)
    logger.info("  CyberLens — Unified Model Evaluation")
    logger.info("=" * 60)

    models_to_eval = args.models.split(",") if args.models != "all" else [
        "fingerprinter", "classifier", "deepfake", "decision"
    ]

    results = []

    if "fingerprinter" in models_to_eval:
        logger.info("Evaluating Siamese Fingerprinter...")
        results.append(load_fingerprinter_eval())

    if "classifier" in models_to_eval:
        logger.info("Evaluating IndicBERT Scam Classifier...")
        results.append(load_classifier_eval())

    if "deepfake" in models_to_eval:
        logger.info("Evaluating EfficientNet-B4 Deepfake Detector...")
        results.append(load_deepfake_eval())

    if "decision" in models_to_eval:
        logger.info("Evaluating Decision Scoring Engine...")
        results.append(run_decision_engine_eval())

    # Build unified report
    unified_report = {
        "version": "5.0",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "models": results,
        "summary": {
            "total_models": len(results),
            "evaluated": sum(1 for r in results if r.get("status") == "evaluated"),
            "not_trained": sum(1 for r in results if r.get("status") == "not_trained"),
            "any_high_fpr": any(
                r.get("false_positive_rate", r.get("binary_collapse", {}).get("false_positive_rate", 0)) > 0.05
                for r in results if r.get("status") == "evaluated"
            ),
        },
    }

    # Save
    report_path = REPORT_DIR / "unified_eval_report.json"
    with open(report_path, "w") as f:
        json.dump(unified_report, f, indent=2)
    logger.info("Unified report saved -> %s", report_path)

    # Print summary
    print_summary_table(results)

    logger.info("Evaluation complete!")


def parse_args():
    parser = argparse.ArgumentParser(description="CyberLens — Evaluate All Models")
    parser.add_argument("--models", default="all",
                        help="Comma-separated: fingerprinter,classifier,deepfake,decision")
    return parser.parse_args()


if __name__ == "__main__":
    evaluate(parse_args())
