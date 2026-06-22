"""
CyberLens — WebSocket Real-Time Feed
========================================
Broadcasts live scraper events to connected dashboard clients.

Event types:
    POST_FOUND, OCR_COMPLETE, CLASSIFIED,
    HIGH_SEVERITY_ALERT, SCRAPER_STATUS

Usage:
    ws://localhost:8000/ws/scraper-feed

Author: CyberLens Team — GPCSSI Internship
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("cyberlens.api.websocket")

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """Manages WebSocket connections for real-time broadcasting.

    Attributes:
        active_connections: List of connected WebSocket clients.
    """

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._message_count = 0

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            "WebSocket client connected (total: %d)",
            len(self.active_connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected client."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(
            "WebSocket client disconnected (total: %d)",
            len(self.active_connections),
        )

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Send a message to all connected clients.

        Args:
            message: JSON-serializable message dict.
        """
        self._message_count += 1
        msg_json = json.dumps(message, default=str)

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(msg_json)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

    async def send_personal(
        self, message: Dict[str, Any], websocket: WebSocket
    ) -> None:
        """Send a message to a specific client.

        Args:
            message: JSON-serializable message dict.
            websocket: Target WebSocket connection.
        """
        try:
            await websocket.send_text(json.dumps(message, default=str))
        except Exception:
            self.disconnect(websocket)

    @property
    def client_count(self) -> int:
        return len(self.active_connections)

    @property
    def total_messages(self) -> int:
        return self._message_count


# Global connection manager instance
manager = ConnectionManager()


def get_manager() -> ConnectionManager:
    """Get the global ConnectionManager instance."""
    return manager


# ---------------------------------------------------------------------------
# Event helpers
# ---------------------------------------------------------------------------

def create_event(
    event_type: str,
    data: Dict[str, Any],
    severity: str = "INFO",
    case_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a standardized WebSocket event.

    Args:
        event_type: POST_FOUND, OCR_COMPLETE, CLASSIFIED,
                    HIGH_SEVERITY_ALERT, SCRAPER_STATUS
        data: Event payload.
        severity: INFO, WARNING, HIGH, CRITICAL
        case_id: Associated case ID (if any).

    Returns:
        Formatted event dict.
    """
    return {
        "type": event_type,
        "timestamp": datetime.now().isoformat(),
        "data": data,
        "severity": severity,
        "case_id": case_id,
    }


async def emit_post_found(post_data: Dict) -> None:
    """Emit POST_FOUND event."""
    event = create_event("POST_FOUND", post_data, "INFO")
    await manager.broadcast(event)


async def emit_ocr_complete(case_id: int, text_preview: str, entity_count: int) -> None:
    """Emit OCR_COMPLETE event."""
    event = create_event(
        "OCR_COMPLETE",
        {"text_preview": text_preview[:200], "entity_count": entity_count},
        "INFO",
        case_id=case_id,
    )
    await manager.broadcast(event)


async def emit_classified(
    case_id: int, category: str, confidence: float, severity: str
) -> None:
    """Emit CLASSIFIED event."""
    event = create_event(
        "CLASSIFIED",
        {"category": category, "confidence": confidence},
        severity,
        case_id=case_id,
    )
    await manager.broadcast(event)


async def emit_high_severity(case_id: int, category: str, details: str) -> None:
    """Emit HIGH_SEVERITY_ALERT event."""
    event = create_event(
        "HIGH_SEVERITY_ALERT",
        {"category": category, "details": details},
        "CRITICAL",
        case_id=case_id,
    )
    await manager.broadcast(event)


async def emit_scraper_status(
    status: str, posts_found: int = 0, error: str = ""
) -> None:
    """Emit SCRAPER_STATUS event."""
    event = create_event(
        "SCRAPER_STATUS",
        {"status": status, "posts_found": posts_found, "error": error},
        "WARNING" if error else "INFO",
    )
    await manager.broadcast(event)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/scraper-feed")
async def scraper_feed_ws(websocket: WebSocket):
    """WebSocket endpoint for real-time scraper feed.

    Clients connect here to receive live events:
        POST_FOUND, OCR_COMPLETE, CLASSIFIED,
        HIGH_SEVERITY_ALERT, SCRAPER_STATUS
    """
    await manager.connect(websocket)

    # Send welcome message
    await manager.send_personal(
        create_event(
            "CONNECTED",
            {
                "message": "Connected to CyberLens real-time feed",
                "active_clients": manager.client_count,
            },
        ),
        websocket,
    )

    try:
        while True:
            # Keep connection alive — listen for client messages
            data = await websocket.receive_text()

            # Handle client commands
            try:
                cmd = json.loads(data)
                cmd_type = cmd.get("type", "")

                if cmd_type == "ping":
                    await manager.send_personal(
                        create_event("pong", {"timestamp": time.time()}),
                        websocket,
                    )
                elif cmd_type == "status":
                    await manager.send_personal(
                        create_event("STATUS", {
                            "active_clients": manager.client_count,
                            "total_messages": manager.total_messages,
                        }),
                        websocket,
                    )
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket)
