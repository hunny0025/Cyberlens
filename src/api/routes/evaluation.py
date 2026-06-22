"""
CyberLens — Model Evaluation API Routes
===========================================
Serves model evaluation reports and confusion matrix images
to the Model Performance frontend page.

Endpoints:
    GET /api/evaluation/summary     → unified eval report JSON
    GET /api/evaluation/matrix/{model} → confusion matrix PNG
    GET /api/evaluation/last_run    → last evaluation timestamp

Author: CyberLens Team — GPCSSI Internship
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

logger = logging.getLogger("cyberlens.api.evaluation")

router = APIRouter(prefix="/api/evaluation", tags=["Model Evaluation"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
REPORT_DIR = PROJECT_ROOT / "reports" / "model_evaluation"
MODELS_DIR = PROJECT_ROOT / "models"


# ---------------------------------------------------------------------------
# Matrix file locations
# ---------------------------------------------------------------------------

MATRIX_PATHS = {
    "fingerprinter": MODELS_DIR / "fingerprinter" / "confusion_matrix.png",
    "classifier_counts": MODELS_DIR / "scam_classifier" / "confusion_matrix_counts.png",
    "classifier_recall": MODELS_DIR / "scam_classifier" / "confusion_matrix_recall.png",
    "classifier_precision": MODELS_DIR / "scam_classifier" / "confusion_matrix_precision.png",
    "classifier_calibration": MODELS_DIR / "scam_classifier" / "calibration_plot.png",
    "deepfake": MODELS_DIR / "deepfake_detector" / "confusion_matrix.png",
    "deepfake_roc": MODELS_DIR / "deepfake_detector" / "roc_curve.png",
    "decision_5class": REPORT_DIR / "decision_confusion_matrix.png",
    "decision_binary": REPORT_DIR / "decision_binary_matrix.png",
    "fingerprinter_threshold": MODELS_DIR / "fingerprinter" / "threshold_sweep.png",
}


@router.get("/summary")
async def get_eval_summary():
    """Get unified evaluation report for all models.

    Returns:
        JSON with per-model metrics, F1, FPR, AUC, and status.
    """
    report_path = REPORT_DIR / "unified_eval_report.json"

    if not report_path.exists():
        # Try to assemble from individual reports
        return _assemble_from_individual()

    with open(report_path, "r") as f:
        report = json.load(f)

    return JSONResponse(content=report)


@router.get("/matrix/{model}")
async def get_eval_matrix(model: str):
    """Get confusion matrix image for a specific model.

    Args:
        model: Model identifier (fingerprinter, classifier_counts,
               classifier_recall, deepfake, decision_5class, etc.)

    Returns:
        PNG image file.
    """
    if model not in MATRIX_PATHS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown model: {model}. Available: {list(MATRIX_PATHS.keys())}",
        )

    path = MATRIX_PATHS[model]
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Matrix not found for {model}. Run evaluation first.",
        )

    return FileResponse(
        str(path),
        media_type="image/png",
        filename=f"{model}_confusion_matrix.png",
    )


@router.get("/last_run")
async def get_last_run():
    """Get timestamp of the last evaluation run.

    Returns:
        JSON with last_run timestamp and available models.
    """
    report_path = REPORT_DIR / "unified_eval_report.json"

    if report_path.exists():
        with open(report_path, "r") as f:
            report = json.load(f)
        return {
            "last_run": report.get("evaluated_at", "unknown"),
            "models_evaluated": report.get("summary", {}).get("evaluated", 0),
            "available_matrices": [
                k for k, v in MATRIX_PATHS.items() if v.exists()
            ],
        }

    return {
        "last_run": None,
        "models_evaluated": 0,
        "available_matrices": [
            k for k, v in MATRIX_PATHS.items() if v.exists()
        ],
    }


def _assemble_from_individual() -> JSONResponse:
    """Assemble evaluation summary from individual model reports."""
    models = []

    # Fingerprinter
    fp_path = MODELS_DIR / "fingerprinter" / "eval_report.json"
    if fp_path.exists():
        with open(fp_path, "r") as f:
            data = json.load(f)
        data["model_name"] = "Siamese Fingerprinter"
        data["status"] = "evaluated"
        models.append(data)
    else:
        models.append({"model_name": "Siamese Fingerprinter", "status": "not_trained"})

    # Classifier
    cl_path = MODELS_DIR / "scam_classifier" / "eval_report.json"
    if cl_path.exists():
        with open(cl_path, "r") as f:
            data = json.load(f)
        data["model_name"] = "IndicBERT Scam Classifier"
        data["status"] = "evaluated"
        models.append(data)
    else:
        models.append({"model_name": "IndicBERT Scam Classifier", "status": "not_trained"})

    # Deepfake
    df_path = MODELS_DIR / "deepfake_detector" / "eval_report.json"
    if df_path.exists():
        with open(df_path, "r") as f:
            data = json.load(f)
        data["model_name"] = "EfficientNet-B4 Deepfake Detector"
        data["status"] = "evaluated"
        models.append(data)
    else:
        models.append({"model_name": "EfficientNet-B4 Deepfake Detector", "status": "not_trained"})

    return JSONResponse(content={
        "version": "5.0",
        "models": models,
        "summary": {
            "total_models": len(models),
            "evaluated": sum(1 for m in models if m.get("status") == "evaluated"),
        },
    })
