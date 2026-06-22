"""
CyberLens — SMS + Email Alert System
========================================
Sends EMERGENCY/CRITICAL alerts to officers via SMS and email.

SMS: Bhashini SMS Gateway / Twilio fallback
Email: SMTP (govt mail servers) / Gmail fallback

Scheduling:
  EMERGENCY — immediate SMS + email
  CRITICAL  — immediate email, SMS digest every 30 min
  WARNING   — email digest at 7 AM / 7 PM
  WATCH     — no notification (dashboard only)

Author: CyberLens Team — GPCSSI India
"""

import logging
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cyberlens.alerts")


@dataclass
class AlertRecipient:
    """An officer who receives alerts."""
    officer_id: str
    name: str
    phone: str            # +91XXXXXXXXXX
    email: str
    district: str
    role: str
    sms_enabled: bool = True
    email_enabled: bool = True


# Default recipients (loaded from DB in production)
DEFAULT_RECIPIENTS = [
    AlertRecipient("off-001", "System Admin", "+919999999999",
                   "admin@gpcssi.gov.in", "ALL", "ADMIN"),
    AlertRecipient("off-003", "SP NCR", "+919876543210",
                   "sp@haryana.police.gov.in", "ALL", "SP_OFFICER"),
]


class AlertNotifier:
    """Multi-channel alert notification system."""

    def __init__(self):
        self._sms_provider = os.getenv("SMS_PROVIDER", "twilio")  # twilio / bhashini
        self._smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self._smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self._smtp_user = os.getenv("SMTP_USER", "")
        self._smtp_password = os.getenv("SMTP_PASSWORD", "")
        self._from_email = os.getenv("ALERT_FROM_EMAIL", "cyberlens@gpcssi.gov.in")

        # Twilio credentials
        self._twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self._twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self._twilio_from = os.getenv("TWILIO_FROM_NUMBER", "")

        self._recipients = list(DEFAULT_RECIPIENTS)
        self._sent_count = 0

    async def send_alert(
        self,
        severity: str,
        campaign_name: str,
        trigger_reason: str,
        recommended_action: str,
        estimated_victims: int = 0,
        districts: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Send alert to appropriate officers based on severity.

        Args:
            severity: EMERGENCY / CRITICAL / WARNING / WATCH

        Returns:
            Dict with send results.
        """
        results = {"sms_sent": 0, "email_sent": 0, "errors": []}

        # Filter recipients by district
        recipients = self._filter_recipients(districts)

        if severity in ("EMERGENCY", "CRITICAL"):
            # Immediate SMS + email
            for r in recipients:
                if r.sms_enabled and severity == "EMERGENCY":
                    ok = self._send_sms(r.phone, self._format_sms(
                        severity, campaign_name, trigger_reason, recommended_action
                    ))
                    if ok:
                        results["sms_sent"] += 1
                    else:
                        results["errors"].append(f"SMS failed: {r.name}")

                if r.email_enabled:
                    ok = self._send_email(
                        r.email, r.name,
                        f"[{severity}] CyberLens Alert — {campaign_name}",
                        self._format_email_html(
                            severity, campaign_name, trigger_reason,
                            recommended_action, estimated_victims, districts,
                        ),
                    )
                    if ok:
                        results["email_sent"] += 1
                    else:
                        results["errors"].append(f"Email failed: {r.name}")

        elif severity == "WARNING":
            # Email only (queued for digest in production)
            for r in recipients:
                if r.email_enabled:
                    ok = self._send_email(
                        r.email, r.name,
                        f"[WARNING] CyberLens — {campaign_name}",
                        self._format_email_html(
                            severity, campaign_name, trigger_reason,
                            recommended_action, estimated_victims, districts,
                        ),
                    )
                    if ok:
                        results["email_sent"] += 1

        self._sent_count += results["sms_sent"] + results["email_sent"]
        logger.info(
            "Alert sent: severity=%s sms=%d email=%d errors=%d",
            severity, results["sms_sent"], results["email_sent"], len(results["errors"]),
        )
        return results

    # ── SMS ───────────────────────────────────────────────────────────

    def _send_sms(self, phone: str, message: str) -> bool:
        """Send SMS via Twilio or Bhashini."""
        if not self._twilio_sid:
            logger.info("SMS not configured (TWILIO_ACCOUNT_SID not set) — skipping")
            logger.info("SMS would send to %s: %s", phone[:6] + "****", message[:50])
            return False

        try:
            from twilio.rest import Client
            client = Client(self._twilio_sid, self._twilio_token)
            msg = client.messages.create(
                body=message, from_=self._twilio_from, to=phone,
            )
            logger.info("SMS sent: %s → %s", msg.sid, phone[:6] + "****")
            return True
        except ImportError:
            logger.info("twilio package not installed — pip install twilio")
            return False
        except Exception as e:
            logger.error("SMS send failed: %s", e)
            return False

    def _format_sms(
        self, severity: str, campaign: str, trigger: str, action: str
    ) -> str:
        """Format SMS message (160 char limit)."""
        msg = f"[{severity}] {campaign}\n{trigger[:80]}\nAction: {action[:60]}"
        return msg[:160]

    # ── Email ─────────────────────────────────────────────────────────

    def _send_email(self, to_email: str, to_name: str, subject: str, html: str) -> bool:
        """Send email via SMTP."""
        if not self._smtp_user:
            logger.info("Email not configured (SMTP_USER not set) — skipping")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"CyberLens Alert <{self._from_email}>"
            msg["To"] = to_email
            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(self._smtp_user, self._smtp_password)
                server.sendmail(self._from_email, to_email, msg.as_string())

            logger.info("Email sent: %s → %s", subject[:40], to_email)
            return True
        except Exception as e:
            logger.error("Email send failed: %s", e)
            return False

    def _format_email_html(
        self, severity: str, campaign: str, trigger: str,
        action: str, victims: int, districts: Optional[List[str]],
    ) -> str:
        """Format email as HTML."""
        sev_colors = {
            "EMERGENCY": "#dc2626", "CRITICAL": "#f97316",
            "WARNING": "#eab308", "WATCH": "#3b82f6",
        }
        color = sev_colors.get(severity, "#64748b")
        now = datetime.now().strftime("%d %b %Y, %I:%M %p IST")

        return f"""
        <div style="font-family:Inter,Arial,sans-serif;max-width:600px;margin:0 auto;background:#0f172a;color:#f1f5f9;border-radius:12px;overflow:hidden;">
          <div style="background:{color};padding:16px 24px;">
            <h1 style="margin:0;font-size:18px;color:white;">🛡️ CyberLens — [{severity}] Alert</h1>
          </div>
          <div style="padding:24px;">
            <h2 style="margin:0 0 12px;font-size:20px;">{campaign}</h2>
            <div style="background:#1e293b;padding:14px;border-radius:8px;margin-bottom:16px;border-left:4px solid {color};">
              <div style="font-size:12px;color:#94a3b8;margin-bottom:4px;">TRIGGER</div>
              <div style="font-size:14px;">{trigger}</div>
            </div>
            <div style="background:#1e293b;padding:14px;border-radius:8px;margin-bottom:16px;">
              <div style="font-size:12px;color:#94a3b8;margin-bottom:4px;">👮 RECOMMENDED ACTION</div>
              <div style="font-size:14px;font-weight:600;">{action}</div>
            </div>
            <div style="display:flex;gap:16px;margin-bottom:16px;">
              <div style="background:#1e293b;padding:12px;border-radius:8px;flex:1;">
                <div style="font-size:11px;color:#94a3b8;">EST. VICTIMS</div>
                <div style="font-size:22px;font-weight:800;color:{color};">{victims:,}</div>
              </div>
              <div style="background:#1e293b;padding:12px;border-radius:8px;flex:1;">
                <div style="font-size:11px;color:#94a3b8;">DISTRICTS</div>
                <div style="font-size:14px;">{', '.join(districts or ['ALL'])}</div>
              </div>
            </div>
            <div style="font-size:11px;color:#64748b;border-top:1px solid #334155;padding-top:12px;">
              Generated: {now} · CyberLens v3.0 · Gurugram Police GPCSSI
            </div>
          </div>
        </div>
        """

    def _filter_recipients(self, districts: Optional[List[str]]) -> List[AlertRecipient]:
        """Filter recipients by district."""
        if not districts:
            return self._recipients
        return [
            r for r in self._recipients
            if r.district == "ALL" or r.district in districts
        ]

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "total_sent": self._sent_count,
            "recipients_configured": len(self._recipients),
            "sms_enabled": bool(self._twilio_sid),
            "email_enabled": bool(self._smtp_user),
        }
