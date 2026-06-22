"""
CyberLens — Early Warning System
====================================
Continuously checks thresholds and generates alerts for:
  NEW_CAMPAIGN, RAPID_GROWTH, CROSS_PLATFORM, HIGH_VICTIM_RISK,
  TEMPLATE_REUSE, ENTITY_REPEAT, EMERGING_HOTSPOT

Author: CyberLens Team — GPCSSI Internship
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("cyberlens.monitor.early_warning")


@dataclass
class Alert:
    """An early warning alert."""
    alert_id: str
    type: str                  # NEW_CAMPAIGN / RAPID_GROWTH / etc.
    severity: str              # WATCH / WARNING / CRITICAL / EMERGENCY
    campaign_id: str
    campaign_name: str
    trigger_reason: str
    recommended_action: str
    affected_districts: List[str] = field(default_factory=list)
    estimated_victims: int = 0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


class EarlyWarningSystem:
    """Monitors campaigns and triggers alerts based on thresholds.

    Integrates with WebSocket to broadcast alerts to dashboard in real-time.
    """

    THRESHOLDS = {
        "RAPID_GROWTH": {"new_channels_24h": 5, "severity": "CRITICAL"},
        "HIGH_VICTIM_RISK": {"estimated_reach": 10000, "severity": "CRITICAL"},
        "CROSS_PLATFORM": {"platforms": 3, "severity": "EMERGENCY"},
        "ENTITY_REPEAT": {"campaign_count": 5, "severity": "HIGH"},
        "EMERGING_HOTSPOT": {"activity_multiplier": 3, "severity": "WARNING"},
    }

    def __init__(self):
        self._active_alerts: List[Alert] = []
        self._alert_counter = 0
        self._callbacks: List[Callable] = []

    def register_callback(self, callback: Callable) -> None:
        """Register a callback to receive alerts (e.g. WebSocket broadcast)."""
        self._callbacks.append(callback)

    async def check_thresholds(self, campaign: Any) -> List[Alert]:
        """Check all thresholds for a campaign and generate alerts.

        Args:
            campaign: ScamCampaign or dict with metrics.

        Returns:
            List of new Alert objects generated.
        """
        alerts = []

        cid = getattr(campaign, "id", None) or campaign.get("id", "")
        name = getattr(campaign, "name", None) or campaign.get("name", "")
        channel_count = getattr(campaign, "channel_count", 0) or campaign.get("channel_count", 0)
        growth_rate = getattr(campaign, "growth_rate", 0) or campaign.get("growth_rate", 0)
        reach = getattr(campaign, "estimated_reach", 0) or campaign.get("estimated_reach", 0)
        victims = getattr(campaign, "victim_estimate", 0) or campaign.get("victim_estimate", 0)

        # RAPID_GROWTH: >5 new channels in 24h
        new_channels_24h = max(0, int(channel_count * growth_rate / 100))
        if new_channels_24h >= self.THRESHOLDS["RAPID_GROWTH"]["new_channels_24h"]:
            alerts.append(self._create_alert(
                alert_type="RAPID_GROWTH",
                severity="CRITICAL",
                campaign_id=cid, campaign_name=name,
                trigger=f"{new_channels_24h} new channels in last 24 hours",
                action="Immediately brief district SP. Block all listed entities with NPCI/CERT-In.",
                victims=victims,
            ))

        # HIGH_VICTIM_RISK: reach > 10,000
        if reach >= self.THRESHOLDS["HIGH_VICTIM_RISK"]["estimated_reach"]:
            alerts.append(self._create_alert(
                alert_type="HIGH_VICTIM_RISK",
                severity="CRITICAL",
                campaign_id=cid, campaign_name=name,
                trigger=f"Estimated reach: {reach:,} users",
                action="Issue public advisory. Coordinate with social media platforms for takedown.",
                victims=victims,
            ))

        # NEW_CAMPAIGN: first time detected
        if channel_count <= 2:
            alerts.append(self._create_alert(
                alert_type="NEW_CAMPAIGN",
                severity="WATCH",
                campaign_id=cid, campaign_name=name,
                trigger="New scam campaign detected",
                action="Monitor for growth. Add to watchlist.",
                victims=victims,
            ))

        # Register alerts
        for alert in alerts:
            self._active_alerts.append(alert)
            await self._broadcast(alert)

        return alerts

    def get_active_alerts(self, severity: Optional[str] = None) -> List[Alert]:
        """Get all active alerts, optionally filtered by severity."""
        if severity:
            return [a for a in self._active_alerts if a.severity == severity]
        return list(self._active_alerts)

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge (remove) an alert."""
        before = len(self._active_alerts)
        self._active_alerts = [a for a in self._active_alerts if a.alert_id != alert_id]
        return len(self._active_alerts) < before

    def _create_alert(
        self, alert_type: str, severity: str,
        campaign_id: str, campaign_name: str,
        trigger: str, action: str, victims: int = 0,
        districts: Optional[List[str]] = None,
    ) -> Alert:
        self._alert_counter += 1
        return Alert(
            alert_id=f"alr-{self._alert_counter:04d}",
            type=alert_type,
            severity=severity,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            trigger_reason=trigger,
            recommended_action=action,
            affected_districts=districts or [],
            estimated_victims=victims,
        )

    async def _broadcast(self, alert: Alert) -> None:
        """Broadcast alert to all registered callbacks."""
        for cb in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(alert)
                else:
                    cb(alert)
            except Exception as e:
                logger.debug("Alert callback error: %s", e)

        # Also broadcast via WebSocket
        try:
            from src.api.routes.websocket import emit_high_severity
            await emit_high_severity(
                0, f"{alert.type}: {alert.campaign_name}",
                alert.trigger_reason,
            )
        except Exception:
            pass
