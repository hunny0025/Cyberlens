"""
CyberLens — Graph Builder
===========================
Creates and connects Neo4j nodes for criminal network mapping.
All methods degrade gracefully when Neo4j is unavailable.

Author: CyberLens Team — GPCSSI Internship
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.graph import neo4j_client as db
from src.graph.models import (
    ChannelNode, DomainNode, ImageNode, PhoneNumberNode,
    QRCodeNode, ScamCampaignNode, TelegramUserNode, UPIIdNode,
)

logger = logging.getLogger("cyberlens.graph.builder")

_NOW = lambda: datetime.now().isoformat()


class GraphBuilder:
    """Builds criminal network graph in Neo4j.

    Provides MERGE-based upserts so duplicate nodes are
    never created. All write failures are logged and ignored
    when Neo4j is unavailable.
    """

    # ── Node creation ─────────────────────────────────────────────────

    def add_channel(self, data: Dict[str, Any]) -> Optional[str]:
        """Create or update a Channel node.

        Args:
            data: Dict with at minimum 'id', 'name', 'platform'.

        Returns:
            channel_id or None if Neo4j unavailable.
        """
        channel = ChannelNode(
            id=data.get("id", self._make_id(data.get("name", ""))),
            name=data.get("name", ""),
            platform=data.get("platform", "unknown"),
            subscriber_count=data.get("subscriber_count", 0),
            risk_score=data.get("risk_score", 0.0),
            first_seen=data.get("first_seen", _NOW()),
            post_count=data.get("post_count", 0),
            scam_category=data.get("scam_category", ""),
        )
        cypher = """
            MERGE (c:Channel {id: $id})
            ON CREATE SET c += $props, c.created_at = $now
            ON MATCH  SET c.risk_score = $risk_score,
                         c.post_count  = c.post_count + 1,
                         c.updated_at  = $now
            RETURN c.id AS id
        """
        result = db.run_query(cypher, {
            "id": channel.id,
            "props": channel.to_props(),
            "risk_score": channel.risk_score,
            "now": _NOW(),
        })
        if result:
            logger.debug("Channel upserted: %s", channel.id)
            return channel.id
        return None

    def add_entity(self, entity_type: str, value: str, **kwargs) -> bool:
        """Create or update an entity node (Phone, UPI, Domain, QR).

        Args:
            entity_type: PHONE / UPI / DOMAIN / QR / TELEGRAM_USER / IMAGE
            value: Primary key value.
            **kwargs: Additional properties.

        Returns:
            True if successful.
        """
        entity_type = entity_type.upper()
        now = _NOW()

        if entity_type == "PHONE":
            cypher = """
                MERGE (p:PhoneNumber {value: $value})
                ON CREATE SET p.flag_count = 1, p.first_seen = $now, p.carrier = $carrier,
                              p.location_hint = $location
                ON MATCH  SET p.flag_count = p.flag_count + 1, p.last_seen = $now
            """
            return db.run_write(cypher, {
                "value": value, "now": now,
                "carrier": kwargs.get("carrier", ""),
                "location": kwargs.get("location_hint", ""),
            })

        elif entity_type == "UPI":
            cypher = """
                MERGE (u:UPIId {value: $value})
                ON CREATE SET u.flag_count = 1, u.first_seen = $now, u.bank = $bank
                ON MATCH  SET u.flag_count = u.flag_count + 1, u.last_seen = $now
            """
            bank = value.split("@")[1] if "@" in value else ""
            return db.run_write(cypher, {"value": value, "now": now, "bank": bank})

        elif entity_type == "DOMAIN":
            cypher = """
                MERGE (d:Domain {url: $url})
                ON CREATE SET d.first_seen = $now, d.is_phishing = $phishing,
                              d.virustotal_score = $vt_score
                ON MATCH  SET d.is_phishing = $phishing, d.updated_at = $now
            """
            return db.run_write(cypher, {
                "url": value, "now": now,
                "phishing": kwargs.get("is_phishing", False),
                "vt_score": kwargs.get("virustotal_score", 0.0),
            })

        elif entity_type == "QR":
            cypher = """
                MERGE (q:QRCode {decoded_value: $value})
                ON CREATE SET q.qr_type = $qr_type, q.first_seen = $now,
                              q.linked_entity = $linked, q.risk_score = $risk
                ON MATCH  SET q.updated_at = $now
            """
            return db.run_write(cypher, {
                "value": value, "now": now,
                "qr_type": kwargs.get("qr_type", "UNKNOWN"),
                "linked": kwargs.get("linked_entity", ""),
                "risk": kwargs.get("risk_score", 0.0),
            })

        elif entity_type == "TELEGRAM_USER":
            cypher = """
                MERGE (t:TelegramUser {username: $username})
                ON CREATE SET t.role = $role, t.activity_score = $score,
                              t.first_seen = $now, t.channels_operated = 1
                ON MATCH  SET t.channels_operated = t.channels_operated + 1,
                              t.activity_score = $score, t.updated_at = $now
            """
            return db.run_write(cypher, {
                "username": value, "now": now,
                "role": kwargs.get("role", "UNKNOWN"),
                "score": kwargs.get("activity_score", 0.0),
            })

        elif entity_type == "IMAGE":
            cypher = """
                MERGE (i:Image {hash: $hash})
                ON CREATE SET i.scam_type = $scam_type, i.first_seen = $now,
                              i.usage_count = 1, i.phash = $phash
                ON MATCH  SET i.usage_count = i.usage_count + 1, i.last_seen = $now
            """
            return db.run_write(cypher, {
                "hash": value, "now": now,
                "scam_type": kwargs.get("scam_type", ""),
                "phash": kwargs.get("phash", ""),
            })

        logger.warning("Unknown entity type: %s", entity_type)
        return False

    # ── Relationship creation ─────────────────────────────────────────

    def link_channel_to_entity(
        self, channel_id: str, entity_type: str, entity_value: str, **props
    ) -> bool:
        """Create a relationship from Channel to an entity.

        Args:
            channel_id: Channel node ID.
            entity_type: PHONE / UPI / DOMAIN / IMAGE / TELEGRAM_USER
            entity_value: Entity primary key.
            **props: Relationship properties.

        Returns:
            True if successful.
        """
        entity_type = entity_type.upper()

        rel_map = {
            "PHONE":        ("PhoneNumber", "value", "USES_PHONE"),
            "UPI":          ("UPIId",        "value", "USES_UPI"),
            "DOMAIN":       ("Domain",       "url",   "HOSTS"),
            "IMAGE":        ("Image",        "hash",  "SHARES_CONTENT"),
            "TELEGRAM_USER":("TelegramUser", "username", "OPERATED_BY"),
        }
        if entity_type not in rel_map:
            return False

        label, key, rel = rel_map[entity_type]
        cypher = f"""
            MATCH (c:Channel {{id: $channel_id}})
            MATCH (e:{label} {{{key}: $entity_value}})
            MERGE (c)-[r:{rel}]->(e)
            ON CREATE SET r.created_at = $now, r.count = 1
            ON MATCH  SET r.count = r.count + 1, r.last_seen = $now
        """
        return db.run_write(cypher, {
            "channel_id": channel_id,
            "entity_value": entity_value,
            "now": _NOW(),
        })

    def link_phone_to_upi(self, phone: str, upi: str) -> bool:
        """Link a phone number to a UPI ID (LINKED_TO)."""
        cypher = """
            MATCH (p:PhoneNumber {value: $phone})
            MATCH (u:UPIId {value: $upi})
            MERGE (p)-[r:LINKED_TO]->(u)
            ON CREATE SET r.created_at = $now
        """
        return db.run_write(cypher, {"phone": phone, "upi": upi, "now": _NOW()})

    def link_images_similar(self, hash1: str, hash2: str, score: float) -> bool:
        """Link two images with a SIMILAR_TO relationship."""
        cypher = """
            MATCH (a:Image {hash: $h1})
            MATCH (b:Image {hash: $h2})
            MERGE (a)-[r:SIMILAR_TO]->(b)
            ON CREATE SET r.similarity_score = $score, r.created_at = $now
            ON MATCH  SET r.similarity_score = $score
        """
        return db.run_write(cypher, {"h1": hash1, "h2": hash2, "score": score, "now": _NOW()})

    # ── Campaign management ───────────────────────────────────────────

    def merge_campaign(self, campaign_id: str, name: str,
                       channels: List[str], **props) -> bool:
        """Create a ScamCampaign node and link channels to it.

        Args:
            campaign_id: Unique campaign identifier.
            name: Human-readable campaign name.
            channels: List of Channel IDs to link.
            **props: Additional campaign properties.

        Returns:
            True if successful.
        """
        # Create campaign node
        cypher_campaign = """
            MERGE (s:ScamCampaign {id: $id})
            ON CREATE SET s.name = $name, s.start_date = $now,
                          s.risk_level = $risk, s.channel_count = $count,
                          s.scam_category = $category, s.status = 'ACTIVE',
                          s.victim_estimate = $victims
            ON MATCH  SET s.channel_count = $count, s.updated_at = $now
        """
        ok = db.run_write(cypher_campaign, {
            "id": campaign_id,
            "name": name,
            "now": _NOW(),
            "risk": props.get("risk_level", "MEDIUM"),
            "count": len(channels),
            "category": props.get("scam_category", ""),
            "victims": props.get("victim_estimate", 0),
        })

        if not ok:
            return False

        # Link channels
        for ch_id in channels:
            cypher_link = """
                MATCH (c:Channel {id: $channel_id})
                MATCH (s:ScamCampaign {id: $campaign_id})
                MERGE (c)-[:BELONGS_TO]->(s)
            """
            db.run_write(cypher_link, {"channel_id": ch_id, "campaign_id": campaign_id})

        logger.info("Campaign '%s' created with %d channels", name, len(channels))
        return True

    # ── Query methods ─────────────────────────────────────────────────

    def find_connections(self, entity_value: str) -> Dict[str, Any]:
        """Return full subgraph for a given entity (phone, UPI, etc).

        Args:
            entity_value: The entity value to search for.

        Returns:
            D3.js-ready dict with nodes and links lists.
        """
        cypher = """
            MATCH (n)-[r]-(m)
            WHERE n.value = $val OR n.id = $val OR n.username = $val
               OR n.url = $val OR n.hash = $val OR n.decoded_value = $val
            RETURN n, r, m
            LIMIT 100
        """
        results = db.run_query(cypher, {"val": entity_value})
        return self._to_d3(results)

    def get_network_map(self, campaign_id: str) -> Dict[str, Any]:
        """Return D3.js-ready network for a campaign.

        Args:
            campaign_id: ScamCampaign node ID.

        Returns:
            Dict with 'nodes' and 'links' lists.
        """
        cypher = """
            MATCH (s:ScamCampaign {id: $id})<-[:BELONGS_TO]-(c:Channel)
            OPTIONAL MATCH (c)-[r1:USES_PHONE]->(p:PhoneNumber)
            OPTIONAL MATCH (c)-[r2:USES_UPI]->(u:UPIId)
            OPTIONAL MATCH (c)-[r3:OPERATED_BY]->(t:TelegramUser)
            OPTIONAL MATCH (c)-[r4:SHARES_CONTENT]->(i:Image)
            RETURN s, c, p, u, t, i, r1, r2, r3, r4
            LIMIT 200
        """
        results = db.run_query(cypher, {"id": campaign_id})
        return self._to_d3(results)

    def get_all_campaigns(self) -> List[Dict[str, Any]]:
        """List all ScamCampaign nodes."""
        cypher = """
            MATCH (s:ScamCampaign)
            OPTIONAL MATCH (s)<-[:BELONGS_TO]-(c:Channel)
            RETURN s, count(c) AS channels
            ORDER BY s.risk_level DESC, s.channel_count DESC
            LIMIT 50
        """
        return db.run_query(cypher, {})

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _make_id(text: str) -> str:
        """Generate a stable ID from text."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    @staticmethod
    def _to_d3(records: List[Dict]) -> Dict[str, Any]:
        """Convert Neo4j records to D3.js force-graph format."""
        nodes = {}
        links = []

        for record in records:
            for key, val in record.items():
                if val is None:
                    continue

                # Node objects have dict-like properties
                if hasattr(val, "items"):
                    node_id = (val.get("id") or val.get("value") or
                               val.get("username") or val.get("url") or
                               val.get("hash") or str(id(val)))
                    if node_id and node_id not in nodes:
                        nodes[node_id] = {
                            "id": node_id,
                            "label": list(val.labels)[0] if hasattr(val, "labels") else key,
                            "properties": dict(val),
                        }

                # Relationship objects
                elif hasattr(val, "type"):
                    source_id = (val.start_node.get("id") or val.start_node.get("value")
                                 or str(id(val.start_node)))
                    target_id = (val.end_node.get("id") or val.end_node.get("value")
                                 or str(id(val.end_node)))
                    if source_id and target_id:
                        links.append({
                            "source": source_id,
                            "target": target_id,
                            "type": val.type,
                            "properties": dict(val),
                        })

        return {
            "nodes": list(nodes.values()),
            "links": links,
            "node_count": len(nodes),
            "link_count": len(links),
        }
