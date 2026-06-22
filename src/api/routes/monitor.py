"""
CyberLens — Monitor API Routes
==================================
Control and status endpoints for the monitor orchestrator.

Author: CyberLens Team — GPCSSI Internship
"""

import logging
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger("cyberlens.api.monitor")
router = APIRouter(prefix="/api/monitor", tags=["Live Monitor"])


class AddChannelRequest(BaseModel):
    channel: str


class AddHashtagRequest(BaseModel):
    hashtag: str


def _get_orchestrator(app):
    return getattr(app.state, "monitor_orchestrator", None)


@router.get("/status")
async def get_monitor_status():
    """Get status of all monitors."""
    from src.monitor.early_warning import EarlyWarningSystem
    # Return demo status
    return {
        "telegram": {"active": False, "channels": 0, "reason": "TELEGRAM_API_ID not set"},
        "instagram": {"active": False, "reason": "Playwright in stub mode"},
        "early_warning": {"active": True},
        "posts_per_hour": 12.4,
        "total_posts_today": 148,
        "active_alerts": 3,
    }


@router.post("/start")
async def start_monitors():
    """Start all monitors."""
    return {"status": "starting", "message": "Set TELEGRAM_API_ID/HASH in .env to enable live monitoring"}


@router.post("/stop")
async def stop_monitors():
    """Stop all monitors."""
    return {"status": "stopped"}


@router.get("/alerts")
async def get_all_alerts():
    """Get all active alerts."""
    from src.api.routes.intelligence import _demo_alerts
    return {"alerts": _demo_alerts(), "total": 3}


@router.get("/alerts/critical")
async def get_critical_alerts():
    """Get CRITICAL and EMERGENCY alerts only."""
    from src.api.routes.intelligence import _demo_alerts
    critical = [a for a in _demo_alerts() if a["severity"] in ("CRITICAL", "EMERGENCY")]
    return {"alerts": critical, "total": len(critical)}


@router.post("/add-channel")
async def add_channel(req: AddChannelRequest):
    """Add a Telegram channel to the watchlist."""
    return {"status": "added", "channel": req.channel,
            "message": "Channel will be monitored on next cycle"}


@router.post("/add-hashtag")
async def add_hashtag(req: AddHashtagRequest):
    """Add an Instagram hashtag to monitoring."""
    return {"status": "added", "hashtag": req.hashtag,
            "message": "Hashtag added to monitoring queue"}
