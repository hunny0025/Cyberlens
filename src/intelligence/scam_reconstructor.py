"""
CyberLens — Scam Reconstructor
=================================
Reconstructs the full scam playbook from campaign data using
rule-based pattern matching + optional Gemini enhancement.

Output format (step-by-step):
  Step 1: Victim contacted via Instagram DM with investment offer
  Step 2: Added to Telegram VIP group showing profit screenshots
  ...

Author: CyberLens Team — GPCSSI Internship
"""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cyberlens.intelligence.reconstructor")


@dataclass
class ScamNarrative:
    """Reconstructed scam playbook narrative."""
    campaign_id: str
    campaign_name: str
    scam_type: str
    steps: List[str]           # step-by-step playbook
    victim_profile: str        # who is targeted
    financial_trail: str       # money flow description
    key_entities: Dict[str, List[str]]
    total_estimated_loss: str
    confidence: float
    generated_by: str = "rule_engine"


# ---------------------------------------------------------------------------
# Scam playbook templates
# ---------------------------------------------------------------------------

PLAYBOOKS = {
    "Investment Scam": {
        "steps": [
            "Victim sees sponsored post / WhatsApp forward promising guaranteed returns",
            "Victim contacts the channel or is added to a 'VIP Investment Group'",
            "Admin posts fake profit screenshots to build trust",
            "Victim is asked to invest a 'minimum amount' (₹5,000–₹50,000)",
            "Small 'demo profits' are shown to encourage bigger investment",
            "Victim is convinced to invest larger amounts",
            "Victim attempts to withdraw — told to pay 'taxes' or 'fees' first",
            "Money transferred to collected UPI IDs",
            "Channel/group deleted, victim blocked",
        ],
        "victim_profile": "First-time investors, middle-aged adults (35-55), retirees seeking passive income",
        "financial_trail": "Victim UPI → Mule UPI → Hawala → Cash",
    },
    "Real Money Betting": {
        "steps": [
            "Victim contacts betting tips channel on Telegram/Instagram",
            "Free 'accurate' prediction shared to build credibility",
            "Victim invited to 'premium paid group' (₹500–₹2,000 fee)",
            "Insider 'fixing' tips shared — all show as winning",
            "Victim encouraged to bet larger amounts",
            "Tips start losing, victim asked to pay to 'recover losses'",
            "Victim blocked after maximum extraction",
        ],
        "victim_profile": "Sports fans, young men (18-35), college students",
        "financial_trail": "Victim → UPI/Paytm → Hawala operator → Overseas",
    },
    "Digital Arrest": {
        "steps": [
            "Victim receives video call from 'CBI/ED/Police officer' in uniform",
            "Told their Aadhaar/PAN is linked to illegal activity or money laundering",
            "Victim put under 'digital arrest' — told not to disconnect",
            "Made to sit in front of camera for hours under psychological coercion",
            "Asked to transfer money to 'safe government account' for 'clearance'",
            "Multiple transfers demanded as 'fines', 'taxes', 'deposits'",
            "Call ends when victim refuses or runs out of money",
        ],
        "victim_profile": "Elderly (55+), government employees, professionals with savings",
        "financial_trail": "Victim RTGS → Mule accounts → Cash withdrawal within hours",
    },
    "Fake Customer Care": {
        "steps": [
            "Victim searches for bank/service helpline — scam number appears first",
            "Or victim posts complaint on social media — scammer replies",
            "Scammer asks for OTP / card details 'to verify account'",
            "Account funds drained or fraudulent transactions made",
        ],
        "victim_profile": "Banking customers, e-commerce users, elderly users",
        "financial_trail": "Victim bank account → Instant UPI transfers → Multiple mule accounts",
    },
    "Sextortion": {
        "steps": [
            "Victim connects with attractive profile on Facebook/Instagram",
            "Moved to WhatsApp/Telegram for 'private chat'",
            "Victim tricked into video call — intimate content recorded",
            "Content morphed/used as leverage for blackmail",
            "Threats to share with family/colleagues unless payment made",
            "Repeat demands after initial payment",
        ],
        "victim_profile": "Men (18-50), married professionals, vulnerable youth",
        "financial_trail": "Victim → UPI/Bitcoin → Overseas accounts",
    },
}


class ScamReconstructor:
    """Reconstructs scam playbooks from campaign data.

    Uses rule-based templates enhanced by detected entities.
    Optionally calls Gemini API for bespoke narrative generation.
    """

    def reconstruct(self, campaign: Any) -> ScamNarrative:
        """Reconstruct the scam narrative for a campaign.

        Args:
            campaign: ScamCampaign object or dict with campaign data.

        Returns:
            ScamNarrative with step-by-step playbook.
        """
        # Handle both dataclass and dict
        if hasattr(campaign, "__dict__"):
            cat = campaign.scam_category
            name = campaign.name
            cid = campaign.id
            entities = {
                "phones": getattr(campaign, "shared_entities", []),
                "upis": [],
            }
        else:
            cat = campaign.get("scam_category", "Unknown")
            name = campaign.get("name", "Unknown Campaign")
            cid = campaign.get("id", "")
            entities = {}

        # Find best matching playbook
        playbook = None
        for pb_name, pb_data in PLAYBOOKS.items():
            if pb_name.lower() in cat.lower() or cat.lower() in pb_name.lower():
                playbook = (pb_name, pb_data)
                break

        if not playbook:
            playbook = ("Unknown", {
                "steps": ["Campaign pattern not yet catalogued — manual investigation required"],
                "victim_profile": "Unknown",
                "financial_trail": "Unknown",
            })

        scam_type, pb = playbook

        # Try Gemini enhancement
        steps = self._try_gemini_enhance(cat, name, entities) or pb["steps"]

        return ScamNarrative(
            campaign_id=cid,
            campaign_name=name,
            scam_type=scam_type,
            steps=steps,
            victim_profile=pb["victim_profile"],
            financial_trail=pb["financial_trail"],
            key_entities=entities,
            total_estimated_loss=self._estimate_loss(campaign),
            confidence=0.85 if steps != pb["steps"] else 0.7,
            generated_by="gemini" if steps != pb["steps"] else "rule_engine",
        )

    def _try_gemini_enhance(
        self, category: str, name: str, entities: Dict
    ) -> Optional[List[str]]:
        """Try to get Gemini-enhanced narrative. Returns None on failure."""
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            return None

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash")

            prompt = (
                f"You are a cybercrime intelligence analyst for Indian Police (GPCSSI).\n"
                f"Campaign: {name}\nCategory: {category}\n"
                f"Shared entities: {entities}\n\n"
                f"Reconstruct the step-by-step scam playbook this criminal network "
                f"likely uses to defraud Indian citizens. Output ONLY numbered steps, "
                f"one per line, in simple English. Maximum 10 steps."
            )

            response = model.generate_content(prompt)
            raw = response.text.strip()
            steps = []
            for line in raw.split("\n"):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("Step")):
                    step = re.sub(r"^[\d\.\:\s]+Step\s*\d*[\.\:\s]*", "", line).strip()
                    if step:
                        steps.append(step)
            return steps[:10] if len(steps) >= 3 else None

        except Exception as e:
            logger.debug("Gemini narrative failed: %s", e)
            return None

    @staticmethod
    def _estimate_loss(campaign: Any) -> str:
        """Estimate total financial loss."""
        victims = (
            campaign.victim_estimate if hasattr(campaign, "victim_estimate")
            else campaign.get("victim_estimate", 0)
        )
        if victims <= 0:
            return "Unknown"
        avg_loss = 25000  # average ₹25,000 per victim (I4C data)
        total = victims * avg_loss
        if total >= 10_000_000:
            return f"₹{total / 10_000_000:.1f} Crore (estimated)"
        if total >= 100_000:
            return f"₹{total / 100_000:.1f} Lakh (estimated)"
        return f"₹{total:,} (estimated)"
