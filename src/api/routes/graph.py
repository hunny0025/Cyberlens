"""
CyberLens — Graph API Routes
===============================
REST endpoints for criminal network graph intelligence.

Author: CyberLens Team — GPCSSI Internship
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.graph import neo4j_client as db
from src.graph.graph_builder import GraphBuilder
from src.graph.network_analyzer import NetworkAnalyzer

logger = logging.getLogger("cyberlens.api.graph")
router = APIRouter(prefix="/api/graph", tags=["Criminal Network Graph"])

_builder = GraphBuilder()
_analyzer = NetworkAnalyzer()


class FindNetworkRequest(BaseModel):
    entity_value: str
    entity_type: str = "AUTO"


@router.get("/campaigns")
async def list_campaigns():
    """List all detected scam campaigns."""
    if not db.is_available():
        return {"available": False, "message": "Neo4j not connected — see docker-compose.yml",
                "demo": _demo_campaigns()}
    campaigns = _builder.get_all_campaigns()
    return {"campaigns": campaigns, "total": len(campaigns)}


@router.get("/campaign/{campaign_id}")
async def get_campaign_network(campaign_id: str):
    """Get D3.js network map for a campaign."""
    if not db.is_available():
        return {"available": False, "demo_graph": _demo_d3_graph(campaign_id)}
    network = _builder.get_network_map(campaign_id)
    risk = _analyzer.calculate_risk_score(campaign_id)
    growth = _analyzer.detect_growth_rate(campaign_id)
    mastermind = _analyzer.find_mastermind(campaign_id)
    return {
        "campaign_id": campaign_id,
        "network": network,
        "risk_score": risk,
        "growth": growth.__dict__,
        "mastermind": mastermind,
    }


@router.get("/entity/{value}")
async def get_entity_connections(value: str):
    """Get all graph connections for an entity (phone, UPI, URL, etc)."""
    if not db.is_available():
        return {"available": False, "message": "Neo4j not connected"}
    network = _builder.find_connections(value)
    return {"entity": value, "network": network}


@router.post("/find-network")
async def find_network(req: FindNetworkRequest):
    """Submit an entity value and get its full criminal network."""
    if not db.is_available():
        return {"available": False, "message": "Neo4j not connected"}
    network = _builder.find_connections(req.entity_value)
    return {
        "entity_value": req.entity_value,
        "entity_type": req.entity_type,
        "network": network,
    }


@router.get("/mastermind/{campaign_id}")
async def get_mastermind(campaign_id: str):
    """Identify the likely mastermind operator of a campaign."""
    if not db.is_available():
        return {"available": False}
    mastermind = _analyzer.find_mastermind(campaign_id)
    if not mastermind:
        raise HTTPException(status_code=404, detail="No mastermind identified yet")
    return {"campaign_id": campaign_id, "mastermind": mastermind}


@router.get("/health")
async def graph_health():
    """Check Neo4j connection health."""
    return db.health_check()


# ---------------------------------------------------------------------------
# Demo data (when Neo4j unavailable)
# ---------------------------------------------------------------------------

def _demo_campaigns():
    return [
        {"id": "cpg-001", "name": "IPL Betting Ring — Gurugram", "risk_level": "CRITICAL",
         "channel_count": 23, "victim_estimate": 4500, "status": "ACTIVE"},
        {"id": "cpg-002", "name": "Fake Zerodha Network", "risk_level": "HIGH",
         "channel_count": 11, "victim_estimate": 1800, "status": "ACTIVE"},
        {"id": "cpg-003", "name": "Digital Arrest Ring — NCR", "risk_level": "CRITICAL",
         "channel_count": 7, "victim_estimate": 320, "status": "ACTIVE"},
    ]


def _demo_d3_graph(campaign_id: str) -> Dict[str, Any]:
    return {
        "nodes": [
            {"id": campaign_id, "label": "ScamCampaign", "properties": {"name": "Demo Campaign", "risk_level": "HIGH"}},
            {"id": "ch-001", "label": "Channel", "properties": {"name": "invest_tips_vip", "platform": "telegram"}},
            {"id": "ch-002", "label": "Channel", "properties": {"name": "quick_profit_99", "platform": "instagram"}},
            {"id": "ph-001", "label": "PhoneNumber", "properties": {"value": "+91-98765XXXXX", "flag_count": 8}},
            {"id": "upi-001", "label": "UPIId", "properties": {"value": "scammer@paytm", "flag_count": 4}},
            {"id": "tg-001", "label": "TelegramUser", "properties": {"username": "@scam_admin", "role": "ADMIN"}},
        ],
        "links": [
            {"source": "ch-001", "target": campaign_id, "type": "BELONGS_TO"},
            {"source": "ch-002", "target": campaign_id, "type": "BELONGS_TO"},
            {"source": "ch-001", "target": "ph-001", "type": "USES_PHONE"},
            {"source": "ch-002", "target": "ph-001", "type": "USES_PHONE"},
            {"source": "ch-001", "target": "upi-001", "type": "USES_UPI"},
            {"source": "tg-001", "target": "ch-001", "type": "OPERATED_BY"},
        ],
        "node_count": 6,
        "link_count": 6,
    }
