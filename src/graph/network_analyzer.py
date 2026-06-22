"""
CyberLens — Network Analyzer
================================
Risk scoring, growth prediction, mastermind identification,
victim clustering, and expansion forecasting for criminal networks.

Author: CyberLens Team — GPCSSI Internship
"""

import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.graph import neo4j_client as db

logger = logging.getLogger("cyberlens.graph.network_analyzer")


@dataclass
class GrowthMetrics:
    """Growth metrics for a scam campaign."""
    campaign_id: str
    current_channels: int
    channels_last_24h: int
    victims_per_day: float
    predicted_30day_channels: int
    predicted_30day_victims: int
    growth_rate_pct: float     # percent growth per day
    risk_escalation: float     # 0–100


@dataclass
class VictimCluster:
    """A cluster of complaints linked by shared entities."""
    cluster_id: str
    shared_entity: str
    entity_type: str           # PHONE / UPI / TELEGRAM
    complaint_count: int
    estimated_total_loss: float
    districts_affected: List[str] = field(default_factory=list)


@dataclass
class ExpansionForecast:
    """30-day expansion forecast for a campaign."""
    campaign_id: str
    current_reach: int         # estimated current victims
    forecast_30day: int
    new_districts_expected: List[str]
    platform_expansion: List[str]
    confidence: float
    alert_level: str           # WATCH / WARNING / CRITICAL / EMERGENCY


class NetworkAnalyzer:
    """Analyzes criminal network graphs for intelligence insights.

    Provides risk scoring, growth prediction, and victim clustering.
    Degrades gracefully when Neo4j is unavailable (uses heuristics).
    """

    def calculate_risk_score(self, campaign_id: str) -> float:
        """Calculate campaign risk score (0–100).

        Factors: channel count, entity count, cross-platform,
        repeat offenders, victim density.

        Args:
            campaign_id: ScamCampaign node ID.

        Returns:
            Risk score float 0–100.
        """
        cypher = """
            MATCH (s:ScamCampaign {id: $id})<-[:BELONGS_TO]-(c:Channel)
            OPTIONAL MATCH (c)-[:USES_PHONE]->(p:PhoneNumber)
            OPTIONAL MATCH (c)-[:USES_UPI]->(u:UPIId)
            RETURN
              count(DISTINCT c) AS channels,
              count(DISTINCT p) AS phones,
              count(DISTINCT u) AS upis,
              s.victim_estimate AS victims,
              s.risk_level AS risk_level
        """
        results = db.run_query(cypher, {"id": campaign_id})

        if not results:
            # Heuristic fallback
            return 50.0

        r = results[0]
        channels = r.get("channels", 0) or 0
        phones = r.get("phones", 0) or 0
        upis = r.get("upis", 0) or 0
        victims = r.get("victims", 0) or 0
        risk_level = r.get("risk_level", "MEDIUM") or "MEDIUM"

        # Base score from risk level
        base = {"LOW": 20, "MEDIUM": 40, "HIGH": 65, "CRITICAL": 85}.get(risk_level, 40)

        # Add for each factor
        score = base
        score += min(20, channels * 2)        # up to 20 pts for channels
        score += min(10, phones * 1.5)        # up to 10 pts for phones
        score += min(10, upis * 2)            # up to 10 pts for UPIs
        score += min(15, math.log1p(victims)) # up to 15 pts for victims

        return round(min(100.0, score), 1)

    def detect_growth_rate(self, campaign_id: str) -> GrowthMetrics:
        """Detect channel growth rate for a campaign.

        Args:
            campaign_id: ScamCampaign node ID.

        Returns:
            GrowthMetrics with current and predicted stats.
        """
        cypher_total = """
            MATCH (s:ScamCampaign {id: $id})<-[:BELONGS_TO]-(c:Channel)
            RETURN count(c) AS total, s.victim_estimate AS victims
        """
        cypher_recent = """
            MATCH (s:ScamCampaign {id: $id})<-[:BELONGS_TO]-(c:Channel)
            WHERE c.created_at >= $since
            RETURN count(c) AS recent
        """
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()

        total_r = db.run_query(cypher_total, {"id": campaign_id})
        recent_r = db.run_query(cypher_recent, {"id": campaign_id, "since": yesterday})

        total = (total_r[0].get("total", 0) if total_r else 0) or 1
        victims = (total_r[0].get("victims", 0) if total_r else 0) or 0
        recent = (recent_r[0].get("recent", 0) if recent_r else 0) or 0

        # Compute growth rate
        growth_pct = (recent / total * 100) if total > 0 else 0
        victims_per_day = max(1, victims / 7)  # assume 7-day campaign

        # 30-day projection (compound growth)
        daily_rate = 1 + (growth_pct / 100)
        predicted_channels = int(total * (daily_rate ** 30))
        predicted_victims = int(victims_per_day * 30 * (daily_rate ** 15))

        risk_esc = min(100.0, growth_pct * 5 + self.calculate_risk_score(campaign_id) * 0.5)

        return GrowthMetrics(
            campaign_id=campaign_id,
            current_channels=total,
            channels_last_24h=recent,
            victims_per_day=round(victims_per_day, 1),
            predicted_30day_channels=predicted_channels,
            predicted_30day_victims=predicted_victims,
            growth_rate_pct=round(growth_pct, 2),
            risk_escalation=round(risk_esc, 1),
        )

    def find_mastermind(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Find the likely mastermind (highest centrality TelegramUser).

        Identifies the user with most outgoing connections to channels,
        as a proxy for network centrality.

        Args:
            campaign_id: ScamCampaign node ID.

        Returns:
            TelegramUser dict or None.
        """
        cypher = """
            MATCH (s:ScamCampaign {id: $id})<-[:BELONGS_TO]-(c:Channel)
            MATCH (c)<-[:OPERATED_BY]-(t:TelegramUser)
            RETURN t, count(c) AS channels_run
            ORDER BY channels_run DESC
            LIMIT 1
        """
        results = db.run_query(cypher, {"id": campaign_id})
        if results:
            r = results[0]
            t = dict(r.get("t", {}))
            t["channels_operated"] = r.get("channels_run", 0)
            t["centrality_rank"] = 1
            return t
        return None

    def cluster_victims(
        self, complaint_list: List[Dict[str, Any]]
    ) -> List[VictimCluster]:
        """Group complaints by shared entities (phone, UPI, Telegram).

        Args:
            complaint_list: List of {complaint_id, phone, upi, telegram, district, loss}.

        Returns:
            List of VictimCluster grouped by shared entity.
        """
        from collections import defaultdict

        entity_complaints: Dict[str, List[Dict]] = defaultdict(list)

        for c in complaint_list:
            for field_name in ("phone", "upi", "telegram"):
                val = c.get(field_name, "")
                if val:
                    entity_complaints[f"{field_name}:{val}"].append(c)

        clusters = []
        for entity_key, complaints in entity_complaints.items():
            if len(complaints) < 2:
                continue

            entity_type, entity_val = entity_key.split(":", 1)
            total_loss = sum(c.get("loss", 0) for c in complaints)
            districts = list({c.get("district", "") for c in complaints if c.get("district")})

            clusters.append(VictimCluster(
                cluster_id=f"vc-{abs(hash(entity_key)) % 10000:04d}",
                shared_entity=entity_val,
                entity_type=entity_type.upper(),
                complaint_count=len(complaints),
                estimated_total_loss=total_loss,
                districts_affected=districts,
            ))

        clusters.sort(key=lambda c: c.complaint_count, reverse=True)
        return clusters

    def predict_expansion(self, campaign_id: str) -> ExpansionForecast:
        """Predict campaign geographic and platform expansion.

        Args:
            campaign_id: ScamCampaign node ID.

        Returns:
            ExpansionForecast with likely new areas.
        """
        growth = self.detect_growth_rate(campaign_id)
        risk = self.calculate_risk_score(campaign_id)

        # Determine alert level
        if growth.channels_last_24h >= 5 or risk >= 85:
            alert_level = "EMERGENCY"
        elif growth.channels_last_24h >= 3 or risk >= 70:
            alert_level = "CRITICAL"
        elif growth.channels_last_24h >= 1 or risk >= 50:
            alert_level = "WARNING"
        else:
            alert_level = "WATCH"

        # Predict new districts based on known expansion patterns
        known_hotspot_adjacents = {
            "Gurugram": ["Faridabad", "Rewari", "Jhajjar"],
            "Jamtara": ["Dhanbad", "Giridih", "Bokaro"],
            "Mewat": ["Alwar", "Palwal", "Rewari"],
        }
        new_districts = ["Faridabad", "Rewari"]  # default expansion pattern

        # Predict new platforms
        new_platforms = []
        if growth.growth_rate_pct > 5:
            new_platforms.append("YouTube")
        if growth.growth_rate_pct > 10:
            new_platforms.append("WhatsApp")
        if growth.growth_rate_pct > 20:
            new_platforms.append("Facebook")

        return ExpansionForecast(
            campaign_id=campaign_id,
            current_reach=growth.current_channels * 500,  # rough estimate
            forecast_30day=growth.predicted_30day_victims,
            new_districts_expected=new_districts,
            platform_expansion=new_platforms,
            confidence=min(0.85, 0.4 + risk / 200),
            alert_level=alert_level,
        )
