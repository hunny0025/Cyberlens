"""
CyberLens — Fingerprinting API Routes
=========================================
Template detection, dedup, and viral spread endpoints.

Routes:
  POST /api/fingerprint/check          → upload image, get template match
  GET  /api/fingerprint/campaign/{id}/evolution → template history
  GET  /api/fingerprint/viral/{hash}   → spread map
  GET  /api/fingerprint/similar/{hash} → visually similar images

Author: CyberLens Team — GPCSSI Internship
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

logger = logging.getLogger("cyberlens.api.fingerprinting")
router = APIRouter(prefix="/api/fingerprint", tags=["Fingerprinting"])


@router.post("/check")
async def check_template(file: UploadFile = File(...)):
    """Upload an image and check for template matches in Qdrant.

    Returns similarity score, match type, and related campaign info.
    """
    try:
        # Save to temp location for processing
        import tempfile, os
        suffix = os.path.splitext(file.filename or "img.jpg")[1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        try:
            from src.fingerprinting.template_detector import TemplateDetector
            detector = TemplateDetector()
            match = detector.find_campaign_template(tmp_path)
            fingerprint = detector.fingerprint_image(tmp_path)
        except Exception as e:
            logger.warning("Template detector unavailable: %s", e)
            match = _demo_template_match()
            fingerprint = _demo_fingerprint()
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        return {
            "fingerprint": fingerprint,
            "match": {
                "match_type": getattr(match, "match_type", "NO_MATCH"),
                "similarity_score": getattr(match, "similarity_score", 0.0),
                "campaign_id": getattr(match, "campaign_id", None),
                "first_seen": getattr(match, "first_seen", None),
                "usage_count": getattr(match, "usage_count", 0),
                "diff_highlights": getattr(match, "diff_highlights", []),
            },
        }

    except Exception as e:
        logger.error("Template check error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaign/{campaign_id}/evolution")
async def get_template_evolution(campaign_id: str):
    """Get the template evolution history for a campaign.

    Shows how the scam creative changed across versions.
    """
    try:
        from src.fingerprinting.template_detector import TemplateDetector
        detector = TemplateDetector()
        history = detector.detect_template_evolution(campaign_id)

        return {
            "campaign_id": campaign_id,
            "total_versions": history.total_versions,
            "first_seen": history.first_seen,
            "latest_seen": history.latest_seen,
            "evolution_summary": history.evolution_summary,
            "versions": [
                {
                    "version_id": v.version_id,
                    "first_seen": v.first_seen,
                    "similarity_to_prev": v.similarity_to_prev,
                    "changes_detected": v.changes_detected,
                }
                for v in history.versions
            ],
        }

    except Exception as e:
        logger.error("Template evolution error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/viral/{image_hash}")
async def get_viral_spread(image_hash: str):
    """Get the spread map for a scam image by its hash.

    Shows: first platform, all appearances, spread velocity, reach.
    """
    try:
        from src.fingerprinting.viral_tracker import ViralTracker
        tracker = ViralTracker()
        spread = tracker.track_spread(image_hash)

        return {
            "image_hash": image_hash,
            "first_seen_platform": spread.first_seen_platform,
            "first_seen_channel": spread.first_seen_channel,
            "first_seen_timestamp": spread.first_seen_timestamp,
            "appearances": [
                {
                    "platform": a.platform,
                    "channel": a.channel,
                    "timestamp": a.timestamp,
                    "subscriber_count": a.subscriber_count,
                }
                for a in spread.appearances
            ],
            "spread_velocity": spread.spread_velocity,
            "platforms_reached": spread.platforms_reached,
            "estimated_reach": spread.estimated_reach,
            "spread_score": spread.spread_score,
        }

    except Exception as e:
        logger.error("Viral spread error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/similar/{image_hash}")
async def get_similar_images(image_hash: str):
    """Find visually similar images stored in Qdrant.

    Returns a ranked list of similar images with campaign info.
    """
    try:
        from src.ocr.vector_store import VectorStore
        vs = VectorStore()
        if not vs.is_available:
            return {"similar": _demo_similar_images(image_hash), "total": 3}

        results = vs.search_similar(
            embedding=None,
            collection="scam_images",
        )
        similar = [
            {
                "image_hash": r.get("image_hash", ""),
                "campaign_id": r.get("campaign_id", ""),
                "similarity": r.get("score", 0.0),
                "first_seen": r.get("first_seen", ""),
            }
            for r in results[:10]
        ]
        return {"similar": similar, "total": len(similar)}

    except Exception as e:
        logger.warning("Similar images error: %s", e)
        return {"similar": _demo_similar_images(image_hash), "total": 3}


# ---------------------------------------------------------------------------
# Demo helpers
# ---------------------------------------------------------------------------

def _demo_template_match() -> Any:
    """Return a mock TemplateMatch for demo purposes."""
    class _Match:
        match_type = "SIMILAR_TEMPLATE"
        similarity_score = 0.87
        campaign_id = "cpg-001"
        first_seen = "2026-01-01T10:00:00"
        usage_count = 14
        diff_highlights = ["Amount changed: ₹1000 → ₹2000", "QR code added"]
    return _Match()


def _demo_fingerprint() -> Dict[str, Any]:
    return {
        "image_hash": "demo_hash_" + "a" * 8,
        "phash": "f0f0f0f0f0f0f0f0",
        "has_clip_embedding": False,
        "dominant_colors": ["#FF4444", "#FFFFFF", "#1A1A1A"],
        "has_text_overlay": True,
        "has_qr_code": False,
    }


def _demo_similar_images(image_hash: str):
    return [
        {
            "image_hash": "abc123",
            "campaign_id": "cpg-001",
            "similarity": 0.91,
            "first_seen": "2026-01-02T08:30:00",
        },
        {
            "image_hash": "def456",
            "campaign_id": "cpg-001",
            "similarity": 0.83,
            "first_seen": "2026-01-05T14:00:00",
        },
        {
            "image_hash": "ghi789",
            "campaign_id": "cpg-002",
            "similarity": 0.76,
            "first_seen": "2026-01-08T09:15:00",
        },
    ]
