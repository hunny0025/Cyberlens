"""
CyberLens -- Feedback Store
================================
Stores every recommendation, analyst decision, and enforcement
outcome for future model training.

This is the training data accumulator for evolving from
Rule-Based (Phase 1) to Probabilistic (Phase 2) to Learned (Phase 3).

Schema:
    feedback_id     -- unique identifier
    channel_id      -- channel assessed
    recommendation  -- JSON of the Recommendation object
    analyst_decision -- APPROVED / REJECTED / MODIFIED / PENDING
    analyst_notes   -- free-text analyst comments
    enforcement_outcome -- CONFIRMED_THREAT / FALSE_POSITIVE / INCONCLUSIVE / PENDING
    created_at      -- when the recommendation was made
    reviewed_at     -- when the analyst reviewed it
    outcome_at      -- when the enforcement outcome was recorded

Author: CyberLens Team
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cyberlens.intelligence.feedback")


class FeedbackStore:
    """SQLite-backed storage for recommendation feedback.

    Every recommendation goes in.  Analyst decisions and enforcement
    outcomes are recorded when available.  This data enables:

    1. Measuring system accuracy over time
    2. Calibrating confidence scores
    3. Learning attribution coefficients (Phase 2)
    4. Training full decision models (Phase 3)

    Attributes:
        db_path:  Path to SQLite database file.
    """

    def __init__(self, db_path: str = "data/feedback/feedback.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Create feedback table if it does not exist."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id TEXT PRIMARY KEY,
                    channel_id TEXT NOT NULL,
                    channel_name TEXT DEFAULT '',
                    recommended_action TEXT NOT NULL,
                    evidence_strength TEXT DEFAULT '',
                    confidence_class TEXT DEFAULT '',
                    recommendation_json TEXT DEFAULT '{}',
                    analyst_decision TEXT DEFAULT 'PENDING',
                    analyst_notes TEXT DEFAULT '',
                    enforcement_outcome TEXT DEFAULT 'PENDING',
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT DEFAULT '',
                    outcome_at TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_channel
                ON feedback(channel_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_decision
                ON feedback(analyst_decision)
            """)
        logger.info("FeedbackStore initialized: %s", self.db_path)

    # -- Record recommendation -------------------------------------------

    def record_recommendation(
        self,
        recommendation: Dict[str, Any],
    ) -> str:
        """Store a new recommendation for future feedback.

        Args:
            recommendation: Recommendation.to_dict() output.

        Returns:
            feedback_id for later updates.
        """
        import hashlib
        now = datetime.now(timezone.utc).isoformat()
        channel_id = recommendation.get("channel_id", "unknown")
        feedback_id = hashlib.sha256(
            f"{channel_id}:{now}".encode()
        ).hexdigest()[:16]

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO feedback
                (feedback_id, channel_id, channel_name, recommended_action,
                 evidence_strength, confidence_class, recommendation_json,
                 created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                feedback_id,
                channel_id,
                recommendation.get("channel_name", ""),
                recommendation.get("action", "NO_ACTION"),
                recommendation.get("evidence_strength", ""),
                recommendation.get("recommendation_confidence", ""),
                json.dumps(recommendation, default=str),
                now,
            ))

        logger.debug("Recorded recommendation %s for @%s", feedback_id, channel_id)
        return feedback_id

    # -- Record analyst decision -----------------------------------------

    def record_analyst_decision(
        self,
        feedback_id: str,
        decision: str,
        notes: str = "",
    ) -> None:
        """Record an analyst's decision on a recommendation.

        Args:
            feedback_id:  Feedback record ID.
            decision:  APPROVED / REJECTED / MODIFIED.
            notes:  Free-text analyst comments.
        """
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                UPDATE feedback
                SET analyst_decision = ?, analyst_notes = ?, reviewed_at = ?
                WHERE feedback_id = ?
            """, (decision, notes, now, feedback_id))
        logger.info("Analyst decision recorded: %s -> %s", feedback_id, decision)

    # -- Record enforcement outcome --------------------------------------

    def record_outcome(
        self,
        feedback_id: str,
        outcome: str,
    ) -> None:
        """Record the enforcement outcome.

        Args:
            feedback_id:  Feedback record ID.
            outcome:  CONFIRMED_THREAT / FALSE_POSITIVE / INCONCLUSIVE.
        """
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                UPDATE feedback
                SET enforcement_outcome = ?, outcome_at = ?
                WHERE feedback_id = ?
            """, (outcome, now, feedback_id))
        logger.info("Enforcement outcome recorded: %s -> %s", feedback_id, outcome)

    # -- Query methods ---------------------------------------------------

    def get_all_feedback(self) -> List[Dict[str, Any]]:
        """Retrieve all feedback records."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM feedback ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_reviewed_feedback(self) -> List[Dict[str, Any]]:
        """Retrieve feedback with analyst decisions (for training)."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM feedback WHERE analyst_decision != 'PENDING' "
                "ORDER BY reviewed_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_outcomes(self) -> List[Dict[str, Any]]:
        """Retrieve feedback with enforcement outcomes (for Phase 3 training)."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM feedback WHERE enforcement_outcome != 'PENDING' "
                "ORDER BY outcome_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_accuracy_summary(self) -> Dict[str, Any]:
        """Compute accuracy metrics from available feedback.

        Returns:
            Dict with counts, accuracy, false positive rate.
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            reviewed = conn.execute(
                "SELECT COUNT(*) FROM feedback WHERE analyst_decision != 'PENDING'"
            ).fetchone()[0]
            approved = conn.execute(
                "SELECT COUNT(*) FROM feedback WHERE analyst_decision = 'APPROVED'"
            ).fetchone()[0]
            rejected = conn.execute(
                "SELECT COUNT(*) FROM feedback WHERE analyst_decision = 'REJECTED'"
            ).fetchone()[0]
            confirmed = conn.execute(
                "SELECT COUNT(*) FROM feedback WHERE enforcement_outcome = 'CONFIRMED_THREAT'"
            ).fetchone()[0]
            false_pos = conn.execute(
                "SELECT COUNT(*) FROM feedback WHERE enforcement_outcome = 'FALSE_POSITIVE'"
            ).fetchone()[0]

        return {
            "total_recommendations": total,
            "analyst_reviewed": reviewed,
            "analyst_approved": approved,
            "analyst_rejected": rejected,
            "approval_rate": round(approved / max(reviewed, 1), 4),
            "confirmed_threats": confirmed,
            "false_positives": false_pos,
            "false_positive_rate": round(false_pos / max(confirmed + false_pos, 1), 4),
            "feedback_ready_for_phase2": reviewed >= 200,
            "feedback_ready_for_phase3": (confirmed + false_pos) >= 100,
        }
