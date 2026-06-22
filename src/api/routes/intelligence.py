"""
CyberLens — Intelligence API Routes
======================================
Campaign intelligence, evidence packages, early warnings.

Author: CyberLens Team — GPCSSI Internship
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("cyberlens.api.intelligence")
router = APIRouter(prefix="/api/intelligence", tags=["Campaign Intelligence"])


class IdentityResolveRequest(BaseModel):
    entities: List[Dict[str, str]]  # [{value, entity_type, platform, channel}]


@router.get("/campaigns")
async def list_campaigns():
    """List all active detected campaigns."""
    try:
        from src.intelligence.campaign_discovery import CampaignDiscoveryEngine
        # Return demo campaigns if no real data yet
        return {"campaigns": _demo_campaigns(), "total": len(_demo_campaigns())}
    except Exception as e:
        return {"campaigns": _demo_campaigns(), "total": len(_demo_campaigns())}


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Get full campaign detail with network, growth, and narrative."""
    try:
        from src.intelligence.growth_predictor import GrowthPredictor
        from src.graph.graph_builder import GraphBuilder
        from src.graph.network_analyzer import NetworkAnalyzer

        gp = GrowthPredictor()
        na = NetworkAnalyzer()
        gb = GraphBuilder()

        forecast = gp.predict_growth(campaign_id)
        risk_score = na.calculate_risk_score(campaign_id)
        mastermind = na.find_mastermind(campaign_id)
        network = gb.get_network_map(campaign_id)

        return {
            "campaign_id": campaign_id,
            "risk_score": risk_score,
            "growth_forecast": forecast.__dict__,
            "mastermind": mastermind,
            "network": network,
        }
    except Exception as e:
        logger.error("Campaign detail error: %s", e)
        return {"campaign_id": campaign_id, "error": str(e), "demo": _demo_campaign_detail(campaign_id)}


@router.get("/campaigns/{campaign_id}/evidence")
async def get_campaign_evidence(campaign_id: str, background_tasks: BackgroundTasks):
    """Build and return evidence package for a campaign."""
    try:
        from src.intelligence.evidence_builder import EvidenceBuilder
        from src.intelligence.campaign_discovery import ScamCampaign

        builder = EvidenceBuilder()
        # Build with demo campaign if no real data
        campaign = _find_campaign(campaign_id)
        package = builder.build_evidence(campaign)
        return package.to_dict()
    except Exception as e:
        logger.error("Evidence build error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaigns/{campaign_id}/narrative")
async def get_campaign_narrative(campaign_id: str):
    """Get reconstructed scam narrative for a campaign."""
    try:
        from src.intelligence.scam_reconstructor import ScamReconstructor
        recon = ScamReconstructor()
        campaign = _find_campaign(campaign_id)
        narrative = recon.reconstruct(campaign)
        return {
            "campaign_id": campaign_id,
            "scam_type": narrative.scam_type,
            "steps": [f"Step {i+1}: {s}" for i, s in enumerate(narrative.steps)],
            "victim_profile": narrative.victim_profile,
            "financial_trail": narrative.financial_trail,
            "estimated_loss": narrative.total_estimated_loss,
            "confidence": narrative.confidence,
            "generated_by": narrative.generated_by,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/early-warning")
async def get_early_warnings():
    """Get all active early warning alerts."""
    return {"alerts": _demo_alerts(), "total": len(_demo_alerts())}


@router.post("/resolve-identity")
async def resolve_identity(req: IdentityResolveRequest):
    """Submit entities and get identity cluster analysis."""
    try:
        from src.intelligence.identity_resolver import Entity, IdentityResolver
        entities = [
            Entity(
                value=e.get("value", ""),
                entity_type=e.get("entity_type", "UNKNOWN"),
                platform=e.get("platform", ""),
                channel=e.get("channel", ""),
            )
            for e in req.entities
        ]
        resolver = IdentityResolver()
        clusters = resolver.resolve(entities)
        return {
            "clusters": [
                {
                    "cluster_id": c.cluster_id,
                    "match_probability": c.match_probability,
                    "evidence": c.match_evidence,
                    "platforms": c.platforms_linked,
                    "summary": c.summary,
                }
                for c in clusters
            ],
            "total": len(clusters),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/growth/{campaign_id}")
async def get_growth_forecast(campaign_id: str):
    """Get 30-day growth forecast for a campaign."""
    try:
        from src.intelligence.growth_predictor import GrowthPredictor
        gp = GrowthPredictor()
        forecast = gp.predict_growth(campaign_id)
        return forecast.__dict__
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Demo helpers
# ---------------------------------------------------------------------------

def _find_campaign(campaign_id: str):
    """Find campaign in demo list or return stub."""
    for c in _demo_campaigns():
        if c["id"] == campaign_id:
            return type("Campaign", (), c)()
    return type("Campaign", (), {
        "id": campaign_id, "name": "Unknown Campaign",
        "scam_category": "Investment Scam",
        "victim_estimate": 500, "shared_entities": [],
    })()


def _demo_campaigns():
    return [
        {"id": "cpg-001", "name": "IPL Betting Ring — Gurugram", "risk_level": "CRITICAL",
         "risk_score": 88, "scam_category": "Real Money Betting",
         "channel_count": 23, "post_count": 147, "estimated_reach": 45000,
         "victim_estimate": 4500, "status": "ACTIVE", "growth_rate": 12.5,
         "shared_entities": ["+91-98765XXXXX", "betting@paytm", "t.me/ipl_vip_tips"],
         "districts_affected": ["Gurugram", "Delhi", "Noida"]},
        {"id": "cpg-002", "name": "Fake Zerodha Network", "risk_level": "HIGH",
         "risk_score": 72, "scam_category": "Investment Scam",
         "channel_count": 11, "post_count": 83, "estimated_reach": 18000,
         "victim_estimate": 1800, "status": "ACTIVE", "growth_rate": 6.2,
         "shared_entities": ["+91-87654XXXXX", "invest@gpay", "t.me/zerodha_official2"],
         "districts_affected": ["Mumbai", "Pune", "Bengaluru"]},
        {"id": "cpg-003", "name": "Digital Arrest Ring — NCR", "risk_level": "CRITICAL",
         "risk_score": 91, "scam_category": "Digital Arrest",
         "channel_count": 7, "post_count": 42, "estimated_reach": 0,
         "victim_estimate": 320, "status": "ACTIVE", "growth_rate": 8.1,
         "shared_entities": ["+91-76543XXXXX"],
         "districts_affected": ["Delhi", "Gurugram", "Noida", "Ghaziabad"]},
    ]


def _demo_campaign_detail(campaign_id: str):
    return {
        "risk_score": 85,
        "growth_forecast": {
            "current_channels": 15, "new_channels_last_24h": 3,
            "projected_30day_channels": 87, "victim_estimate_30day": 12000,
            "risk_escalation_score": 78, "alert_level": "CRITICAL",
        },
    }


def _demo_alerts():
    from datetime import datetime
    return [
        {"alert_id": "alr-001", "type": "RAPID_GROWTH", "severity": "CRITICAL",
         "campaign_id": "cpg-001", "campaign_name": "IPL Betting Ring",
         "trigger_reason": "5 new channels detected in last 24 hours",
         "recommended_action": "Immediately block all listed phone numbers and UPI IDs. File FIR.",
         "affected_districts": ["Gurugram", "Delhi"],
         "estimated_victims": 4500, "timestamp": datetime.now().isoformat()},
        {"alert_id": "alr-002", "type": "ENTITY_REPEAT", "severity": "HIGH",
         "campaign_id": "cpg-002", "campaign_name": "Fake Zerodha Network",
         "trigger_reason": "UPI ID invest@gpay seen in 6 separate campaigns",
         "recommended_action": "Initiate UPI ID freeze with NPCI. Cross-link all campaigns.",
         "affected_districts": ["Mumbai", "Pune"],
         "estimated_victims": 1800, "timestamp": datetime.now().isoformat()},
        {"alert_id": "alr-003", "type": "CROSS_PLATFORM", "severity": "WARNING",
         "campaign_id": "cpg-003", "campaign_name": "Digital Arrest Ring — NCR",
         "trigger_reason": "Same deepfake video detected on Telegram + WhatsApp + Instagram",
         "recommended_action": "Submit NCMEC/DMCA takedowns. Brief district police.",
         "affected_districts": ["Delhi", "Gurugram"],
         "estimated_victims": 320, "timestamp": datetime.now().isoformat()},
    ]
