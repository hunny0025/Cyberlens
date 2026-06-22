"""
CyberLens — NPCI UPI Freeze Workflow
========================================
Automates UPI ID freeze requests to NPCI (National Payments Corporation of India).

Workflow:
  1. Officer confirms scam UPI ID → submits freeze request
  2. System generates NPCI-format JSON payload
  3. Sends to NPCI sandbox (or logs if no credentials)
  4. Tracks status: PENDING → SUBMITTED → FROZEN → REJECTED
  5. Cross-links frozen UPI to all related campaigns

Author: CyberLens Team — GPCSSI India
"""

import json
import logging
import os
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cyberlens.reports.npci")

NPCI_FREEZE_LOG = Path(os.getenv("AUDIT_LOG_DIR", "logs/audit")) / "npci_freeze.jsonl"


@dataclass
class FreezeRequest:
    """A UPI ID freeze request to NPCI."""
    request_id: str
    upi_id: str
    bank_name: str
    reason: str
    campaign_id: str
    campaign_name: str
    fir_numbers: List[str]
    evidence_hashes: List[str]
    officer_id: str
    officer_badge: str
    district: str
    status: str = "PENDING"     # PENDING → SUBMITTED → FROZEN → REJECTED
    submitted_at: str = ""
    npci_reference: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class NPCIFreezeManager:
    """Manages UPI ID freeze requests to NPCI."""

    def __init__(self):
        NPCI_FREEZE_LOG.parent.mkdir(parents=True, exist_ok=True)
        self._npci_api_url = os.getenv("NPCI_API_URL", "")
        self._npci_api_key = os.getenv("NPCI_API_KEY", "")
        self._requests: Dict[str, FreezeRequest] = {}
        self._load_requests()

    def create_freeze_request(
        self,
        upi_id: str,
        campaign_id: str,
        campaign_name: str,
        officer_id: str,
        officer_badge: str,
        district: str,
        reason: str = "Scam UPI ID detected in active cybercrime campaign",
        fir_numbers: Optional[List[str]] = None,
        evidence_hashes: Optional[List[str]] = None,
    ) -> FreezeRequest:
        """Create a new UPI freeze request.

        Args:
            upi_id: The UPI ID to freeze (e.g., scammer@paytm)
            campaign_id: Associated campaign

        Returns:
            FreezeRequest object
        """
        # Infer bank from UPI handle
        bank = self._detect_bank(upi_id)

        req = FreezeRequest(
            request_id="NPCI-" + secrets.token_hex(6).upper(),
            upi_id=upi_id,
            bank_name=bank,
            reason=reason,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            fir_numbers=fir_numbers or [],
            evidence_hashes=evidence_hashes or [],
            officer_id=officer_id,
            officer_badge=officer_badge,
            district=district,
        )

        self._requests[req.request_id] = req
        self._save_request(req)

        logger.info("NPCI freeze request created: %s for %s", req.request_id, upi_id)
        return req

    def submit_freeze(self, request_id: str) -> Dict[str, Any]:
        """Submit a freeze request to NPCI API.

        Args:
            request_id: The freeze request ID.

        Returns:
            Submission result with NPCI reference number.
        """
        req = self._requests.get(request_id)
        if not req:
            return {"error": "Request not found"}

        if not self._npci_api_url:
            # Demo mode — log the payload
            req.status = "SUBMITTED"
            req.submitted_at = datetime.now(timezone.utc).isoformat()
            req.npci_reference = "DEMO-" + secrets.token_hex(4).upper()
            self._save_request(req)

            logger.info(
                "NPCI freeze DEMO submitted: %s → %s (no NPCI_API_URL configured)",
                req.request_id, req.upi_id,
            )
            return {
                "status": "SUBMITTED",
                "request_id": req.request_id,
                "npci_reference": req.npci_reference,
                "message": "DEMO MODE — set NPCI_API_URL + NPCI_API_KEY for real submission",
                "payload": self._build_npci_payload(req),
            }

        # Real submission
        try:
            import requests as http
            payload = self._build_npci_payload(req)
            resp = http.post(
                f"{self._npci_api_url}/freeze",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._npci_api_key}",
                    "Content-Type": "application/json",
                    "X-Source": "CyberLens-GPCSSI",
                },
                timeout=30,
            )

            if resp.status_code in (200, 201):
                result = resp.json()
                req.status = "SUBMITTED"
                req.submitted_at = datetime.now(timezone.utc).isoformat()
                req.npci_reference = result.get("reference_id", "")
                self._save_request(req)
                return {"status": "SUBMITTED", "npci_reference": req.npci_reference}
            else:
                req.status = "REJECTED"
                self._save_request(req)
                return {"status": "REJECTED", "reason": resp.text}

        except Exception as e:
            logger.error("NPCI submission failed: %s", e)
            return {"status": "ERROR", "error": str(e)}

    def get_status(self, request_id: str) -> Dict[str, Any]:
        """Get current status of a freeze request."""
        req = self._requests.get(request_id)
        if not req:
            return {"error": "Request not found"}
        return asdict(req)

    def list_requests(self, campaign_id: Optional[str] = None) -> List[Dict]:
        """List all freeze requests, optionally filtered by campaign."""
        reqs = list(self._requests.values())
        if campaign_id:
            reqs = [r for r in reqs if r.campaign_id == campaign_id]
        return [asdict(r) for r in reqs]

    # ── Helpers ───────────────────────────────────────────────────────

    def _build_npci_payload(self, req: FreezeRequest) -> Dict:
        """Build NPCI-format JSON payload."""
        return {
            "requestType": "UPI_FREEZE",
            "upiId": req.upi_id,
            "bankName": req.bank_name,
            "reason": req.reason,
            "firNumbers": req.fir_numbers,
            "evidenceHashes": req.evidence_hashes,
            "campaignId": req.campaign_id,
            "campaignDescription": req.campaign_name,
            "requestingOfficer": {
                "badgeNumber": req.officer_badge,
                "officerId": req.officer_id,
                "district": req.district,
            },
            "source": "CyberLens v3.0 — Gurugram Police GPCSSI",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _detect_bank(upi_id: str) -> str:
        """Detect bank from UPI handle."""
        handle = upi_id.split("@")[-1].lower() if "@" in upi_id else ""
        bank_map = {
            "paytm": "Paytm Payments Bank",
            "gpay": "Google Pay (Axis Bank)",
            "oksbi": "State Bank of India",
            "okaxis": "Axis Bank",
            "okhdfcbank": "HDFC Bank",
            "okicici": "ICICI Bank",
            "ybl": "PhonePe (Yes Bank)",
            "ibl": "ICICI Bank",
            "upi": "Generic UPI",
            "apl": "Amazon Pay",
            "ratn": "RBL Bank",
            "kotak": "Kotak Mahindra Bank",
        }
        return bank_map.get(handle, f"Unknown ({handle})")

    def _save_request(self, req: FreezeRequest) -> None:
        """Append request to JSONL log."""
        try:
            with open(NPCI_FREEZE_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(req)) + "\n")
        except Exception as e:
            logger.error("NPCI log write failed: %s", e)

    def _load_requests(self) -> None:
        """Load existing requests from log."""
        if not NPCI_FREEZE_LOG.exists():
            return
        try:
            with open(NPCI_FREEZE_LOG, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    rid = data.get("request_id")
                    if rid:
                        self._requests[rid] = FreezeRequest(**{
                            k: v for k, v in data.items()
                            if k in FreezeRequest.__dataclass_fields__
                        })
        except Exception as e:
            logger.warning("NPCI log load failed: %s", e)
