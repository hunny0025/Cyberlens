"""
CyberLens -- Intelligence Pipeline API Routes
================================================
Serves results from the redesigned 4-layer intelligence framework:
  - Recommendations (TAKEDOWN / ANALYST_REVIEW / MONITORING / NO_ACTION)
  - Attribution pairs (same-operator detection)
  - Feedback store (analyst decisions + accuracy metrics)
  - Pipeline re-run trigger

Author: CyberLens Team
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter

logger = logging.getLogger("cyberlens.api.pipeline")

router = APIRouter(prefix="/api/pipeline", tags=["Intelligence Pipeline"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _load_json(path: Path):
    """Safely load a JSON file."""
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load %s: %s", path, e)
    return None


@router.get("/recommendations")
async def get_recommendations():
    """Get the latest intelligence recommendations."""
    data = _load_json(PROJECT_ROOT / "reports" / "recommendations" / "latest.json")
    if not data:
        return {"recommendations": [], "summary": {}, "generated_at": None}

    recs = data.get("recommendations", [])

    # Build summary
    action_counts = {}
    strength_counts = {}
    for r in recs:
        a = r.get("action", "UNKNOWN")
        s = r.get("evidence_strength", "UNKNOWN")
        action_counts[a] = action_counts.get(a, 0) + 1
        strength_counts[s] = strength_counts.get(s, 0) + 1

    suppressed = sum(1 for r in recs if r.get("suppressed"))
    takedowns = action_counts.get("TAKEDOWN_REQUEST", 0)
    reviews = action_counts.get("ANALYST_REVIEW", 0)

    return {
        "recommendations": recs,
        "summary": {
            "total_channels": len(recs),
            "action_counts": action_counts,
            "strength_counts": strength_counts,
            "suppressed_count": suppressed,
            "takedown_count": takedowns,
            "review_count": reviews,
            "threat_rate": round(takedowns / max(len(recs), 1), 4),
        },
        "generated_at": data.get("generated_at"),
    }


@router.get("/attribution")
async def get_attribution():
    """Get operator attribution results."""
    data = _load_json(PROJECT_ROOT / "reports" / "recommendations" / "attribution_results.json")
    if not data or not isinstance(data, list):
        return {"pairs": [], "summary": {}}

    # Only return pairs above threshold
    significant = [p for p in data if p.get("probability_same_operator", 0) > 0.2]
    significant.sort(key=lambda x: x.get("probability_same_operator", 0), reverse=True)

    # Group by operator clusters
    clusters = {}
    for pair in significant:
        a = pair.get("channel_a", "")
        b = pair.get("channel_b", "")
        found_cluster = None
        for cid, members in clusters.items():
            if a in members or b in members:
                found_cluster = cid
                break
        if found_cluster:
            clusters[found_cluster].add(a)
            clusters[found_cluster].add(b)
        else:
            clusters[f"cluster_{len(clusters)+1}"] = {a, b}

    return {
        "pairs": significant,
        "clusters": {k: list(v) for k, v in clusters.items()},
        "summary": {
            "total_pairs_evaluated": len(data),
            "pairs_above_threshold": len(significant),
            "operator_clusters": len(clusters),
        },
    }


@router.get("/feedback")
async def get_feedback_summary():
    """Get feedback store metrics."""
    try:
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from src.intelligence.feedback_store import FeedbackStore
        fb = FeedbackStore(db_path=str(PROJECT_ROOT / "data" / "feedback" / "feedback.db"))
        summary = fb.get_accuracy_summary()
        recent = fb.get_all_feedback()[:20]
        return {"summary": summary, "recent": recent}
    except Exception as e:
        logger.error("Feedback store error: %s", e)
        return {"summary": {}, "recent": [], "error": str(e)}


@router.get("/evidence/{channel_id}")
async def get_channel_evidence(channel_id: str):
    """Get detailed evidence for a specific channel."""
    data = _load_json(PROJECT_ROOT / "reports" / "recommendations" / "latest.json")
    if not data:
        return {"channel_id": channel_id, "evidence": None}

    for rec in data.get("recommendations", []):
        if rec.get("channel_id") == channel_id:
            return {
                "channel_id": channel_id,
                "recommendation": rec,
            }

    return {"channel_id": channel_id, "evidence": None}


@router.get("/dataset-stats")
async def get_dataset_stats():
    """Get training dataset statistics."""
    data = _load_json(PROJECT_ROOT / "data" / "processed" / "training_dataset.json")
    if not data:
        return {"stats": None}

    channels = data.get("channels", [])
    meta = data.get("metadata", {})

    scam_categories = {}
    total_posts = 0
    total_entities = {"upis": 0, "phones": 0, "urls": 0}

    for ch in channels:
        posts = ch.get("posts", [])
        total_posts += len(posts)
        cat = ch.get("ground_truth_category", "unknown")
        scam_categories[cat] = scam_categories.get(cat, 0) + 1
        ent = ch.get("entities_found", {})
        total_entities["upis"] += len(ent.get("upis", []))
        total_entities["phones"] += len(ent.get("phones", []))
        total_entities["urls"] += len(ent.get("urls", []))

    return {
        "stats": {
            "total_channels": len(channels),
            "scam_channels": meta.get("scam_channels", 0),
            "legitimate_channels": meta.get("legitimate_channels", 0),
            "total_posts": total_posts,
            "total_entities": total_entities,
            "categories": scam_categories,
            "blocked_entities": meta.get("blocked_entities", {}),
            "version": meta.get("version", "unknown"),
        },
    }


@router.post("/run")
async def run_pipeline():
    """Trigger a pipeline re-run (non-blocking)."""
    import subprocess
    try:
        proc = subprocess.Popen(
            ["python", "scripts/run_intelligence_pipeline.py", "--attribution"],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return {"status": "started", "pid": proc.pid}
    except Exception as e:
        return {"status": "error", "message": str(e)}
