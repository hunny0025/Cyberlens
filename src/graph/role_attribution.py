"""
CyberLens — Role Attribution Engine
======================================
Analyzes activity patterns to assign operator roles in scam networks.

Roles:
  ADMIN              — Controls campaign, sets templates, manages members
  RECRUITER          — Contacts victims, posts ads, runs hashtag campaigns
  VICTIM_HANDLER     — Manages individual victim conversations
  MONEY_MULE         — Receives/forwards payments, operates UPI accounts
  CONTENT_DISTRIBUTOR — Reposts content across channels/groups

Author: CyberLens Team — GPCSSI Internship
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cyberlens.graph.roles")

# ---------------------------------------------------------------------------
# Role definitions
# ---------------------------------------------------------------------------

ROLES = {
    "ADMIN": {
        "description": "Controls campaign operations, sets strategy",
        "indicators": [
            "pinned messages", "welcome message", "rules", "adds members",
            "changes group description", "admin rights", "बॉस", "संचालक",
        ],
        "weight": 1.0,
    },
    "RECRUITER": {
        "description": "Contacts new victims, posts ads, runs hashtag campaigns",
        "indicators": [
            "join now", "click link", "dm for details", "limited slots",
            "free joining", "abhi join karo", "अभी जुड़ें", "link click",
            "forward this", "share karo",
        ],
        "weight": 0.9,
    },
    "VICTIM_HANDLER": {
        "description": "Manages individual victim conversations, builds trust",
        "indicators": [
            "profit screenshot", "withdrawal proof", "trust me",
            "your account ready", "customer support", "helpline",
            "आपका अकाउंट", "मुनाफा", "withdraw karo",
        ],
        "weight": 0.85,
    },
    "MONEY_MULE": {
        "description": "Receives and forwards criminal proceeds",
        "indicators": [
            "paytm karo", "gpay", "upi transfer", "send amount",
            "payment received", "amount bhejo", "पैसे भेजो",
            "account number", "transfer", "deposit",
        ],
        "weight": 0.9,
    },
    "CONTENT_DISTRIBUTOR": {
        "description": "Reposts scam content across channels",
        "indicators": [
            "forward", "share", "copy paste", "broadcast",
            "viral karo", "all groups", "sabko bhejo",
        ],
        "weight": 0.7,
    },
}


@dataclass
class RoleAssignment:
    """Role assignment for a single operator."""
    username: str
    role: str
    confidence: float
    evidence_list: List[str] = field(default_factory=list)
    activity_score: float = 0.0


@dataclass
class RoleMap:
    """Complete role map for a campaign."""
    campaign_id: str
    assignments: List[RoleAssignment] = field(default_factory=list)
    admin_identified: bool = False
    total_operators: int = 0

    def to_summary(self) -> str:
        """Human-readable role summary for investigators."""
        lines = [f"Role Attribution — Campaign {self.campaign_id}",
                 f"Total operators: {self.total_operators}", ""]
        for a in self.assignments:
            lines.append(
                f"  @{a.username}: {a.role} (confidence={a.confidence:.0%})"
            )
            for ev in a.evidence_list[:3]:
                lines.append(f"    • {ev}")
        return "\n".join(lines)


class RoleAttributor:
    """Assigns roles to operators based on message patterns.

    Works entirely locally — no external API calls.
    Optionally enhanced with Gemini if GEMINI_API_KEY is set.
    """

    def assign_roles(
        self,
        channel_messages: List[Dict[str, Any]],
        user_activity: Dict[str, List[str]],
    ) -> RoleMap:
        """Assign roles based on activity patterns.

        Args:
            channel_messages: List of {text, username, timestamp} dicts.
            user_activity: {username: [message_texts]} map.

        Returns:
            RoleMap with assignments for each operator.
        """
        campaign_id = "unknown"
        assignments = []

        for username, messages in user_activity.items():
            role, confidence, evidence = self._classify_user(username, messages)
            activity_score = self._compute_activity_score(messages)

            assignments.append(RoleAssignment(
                username=username,
                role=role,
                confidence=confidence,
                evidence_list=evidence,
                activity_score=activity_score,
            ))

        # Sort by activity score
        assignments.sort(key=lambda a: a.activity_score, reverse=True)
        admin_identified = any(a.role == "ADMIN" for a in assignments)

        return RoleMap(
            campaign_id=campaign_id,
            assignments=assignments,
            admin_identified=admin_identified,
            total_operators=len(assignments),
        )

    def _classify_user(
        self, username: str, messages: List[str]
    ) -> tuple:
        """Classify a user's role from their messages.

        Returns:
            (role, confidence, evidence_list)
        """
        combined = " ".join(messages).lower()
        scores: Dict[str, float] = {}
        evidence: Dict[str, List[str]] = {}

        for role_name, role_def in ROLES.items():
            score = 0.0
            ev = []
            for indicator in role_def["indicators"]:
                if indicator.lower() in combined:
                    score += role_def["weight"]
                    ev.append(f"Message contains '{indicator}'")

            if score > 0:
                scores[role_name] = score
                evidence[role_name] = ev

        if not scores:
            return ("UNKNOWN", 0.3, ["No distinctive role patterns found"])

        best_role = max(scores, key=scores.__getitem__)
        raw_score = scores[best_role]
        confidence = min(0.95, 0.4 + raw_score * 0.1)

        return (best_role, confidence, evidence.get(best_role, []))

    def _compute_activity_score(self, messages: List[str]) -> float:
        """Score activity level from 0–100."""
        if not messages:
            return 0.0
        base = min(100.0, len(messages) * 2.0)
        # Bonus for messages with entities (phones, UPIs)
        entity_msgs = sum(
            1 for m in messages
            if re.search(r"\+91|\d{10}|@\w+|₹|\d+%", m)
        )
        bonus = min(20.0, entity_msgs * 3.0)
        return round(base + bonus, 1)
