"""
CyberLens — Campaign Discovery Engine
========================================
Automatically groups related social media posts into ScamCampaigns
by finding connected components in the entity co-occurrence graph.

Algorithm:
  Step 1: Extract entities (phone, UPI, QR, links) from each post
  Step 2: Build entity co-occurrence graph (posts sharing same entity → edge)
  Step 3: Find connected components → each = one campaign
  Step 4: Score campaign risk (size × velocity × entity reuse)
  Step 5: Name campaign using rule-based NLP
  Step 6: Save to Neo4j + SQLite

Author: CyberLens Team — GPCSSI Internship
"""

import hashlib
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("cyberlens.intelligence.discovery")


@dataclass
class ScamCampaign:
    """A detected scam campaign grouping multiple posts/channels."""
    id: str
    name: str
    start_date: str
    risk_level: str               # LOW / MEDIUM / HIGH / CRITICAL
    risk_score: float             # 0–100
    scam_category: str
    channel_count: int
    post_count: int
    shared_entities: List[str]    # phones, UPIs, URLs that link this campaign
    estimated_reach: int          # total subscriber count estimate
    victim_estimate: int
    status: str = "ACTIVE"
    growth_rate: float = 0.0
    districts_affected: List[str] = field(default_factory=list)


@dataclass
class ScrapedPost:
    """Minimal post representation for campaign discovery."""
    post_id: str
    source: str
    username: str
    caption_text: str = ""
    post_url: str = ""
    timestamp: str = ""
    image_path: str = ""
    # Pre-extracted entities (populated by OCR pipeline)
    phones: List[str] = field(default_factory=list)
    upi_ids: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    telegram_links: List[str] = field(default_factory=list)
    subscriber_count: int = 0


class CampaignDiscoveryEngine:
    """Groups posts into campaigns via entity co-occurrence graph.

    Designed to run on batches of ScrapedPosts after OCR entity
    extraction. No external dependencies required for core logic.
    """

    def __init__(self):
        self._graph_builder = None
        try:
            from src.graph.graph_builder import GraphBuilder
            self._graph_builder = GraphBuilder()
        except Exception:
            pass

    def discover_campaigns(
        self, posts: List[ScrapedPost]
    ) -> List[ScamCampaign]:
        """Discover campaigns from a list of posts.

        Args:
            posts: List of ScrapedPost with extracted entities.

        Returns:
            List of ScamCampaign, sorted by risk score.
        """
        if not posts:
            return []

        # Step 1: Build entity → post index
        entity_to_posts: Dict[str, Set[str]] = defaultdict(set)
        post_map: Dict[str, ScrapedPost] = {}

        for post in posts:
            post_map[post.post_id] = post
            all_entities = (
                post.phones + post.upi_ids + post.telegram_links +
                [u for u in post.urls if len(u) > 10]
            )
            for entity in all_entities:
                entity_to_posts[entity].add(post.post_id)

        # Step 2: Build adjacency (posts sharing ≥1 entity are connected)
        adjacency: Dict[str, Set[str]] = defaultdict(set)
        for entity, post_ids in entity_to_posts.items():
            if len(post_ids) < 2:
                continue  # isolated post — not a campaign link
            post_list = list(post_ids)
            for i in range(len(post_list)):
                for j in range(i + 1, len(post_list)):
                    adjacency[post_list[i]].add(post_list[j])
                    adjacency[post_list[j]].add(post_list[i])

        # Step 3: Find connected components via BFS
        visited: Set[str] = set()
        components: List[List[str]] = []

        for post_id in post_map:
            if post_id in visited:
                continue
            component = []
            queue = [post_id]
            while queue:
                pid = queue.pop(0)
                if pid in visited:
                    continue
                visited.add(pid)
                component.append(pid)
                queue.extend(adjacency.get(pid, set()) - visited)
            if len(component) >= 1:
                components.append(component)

        # Step 4 & 5: Score and name each component
        campaigns = []
        for component in components:
            if len(component) < 1:
                continue
            campaign = self._build_campaign(component, post_map, entity_to_posts)
            campaigns.append(campaign)

        # Sort by risk score
        campaigns.sort(key=lambda c: c.risk_score, reverse=True)

        # Step 6: Save to Neo4j (non-blocking)
        self._save_to_graph(campaigns, post_map)

        logger.info(
            "Campaign discovery complete: %d posts → %d campaigns",
            len(posts), len(campaigns),
        )
        return campaigns

    def _build_campaign(
        self,
        post_ids: List[str],
        post_map: Dict[str, ScrapedPost],
        entity_to_posts: Dict[str, Set[str]],
    ) -> ScamCampaign:
        """Build a ScamCampaign from a connected component."""
        posts_in = [post_map[pid] for pid in post_ids if pid in post_map]

        # Gather all shared entities
        all_phones = list({p for post in posts_in for p in post.phones})
        all_upis = list({u for post in posts_in for u in post.upi_ids})
        all_tg = list({t for post in posts_in for t in post.telegram_links})
        shared = all_phones + all_upis + all_tg

        # Total reach
        total_reach = sum(p.subscriber_count for p in posts_in)
        victim_estimate = max(1, int(total_reach * 0.01))  # 1% victim rate

        # Risk score
        risk_score = self._score_campaign(posts_in, shared)
        risk_level = self._risk_level(risk_score)

        # Campaign name
        name = self._generate_name(posts_in, all_phones, all_upis, all_tg)

        # Category (most common)
        category = self._detect_category(posts_in)

        # Stable ID
        campaign_id = "cpg-" + hashlib.sha256(
            "".join(sorted(post_ids)).encode()
        ).hexdigest()[:8]

        return ScamCampaign(
            id=campaign_id,
            name=name,
            start_date=min((p.timestamp for p in posts_in if p.timestamp),
                           default=datetime.now().isoformat()),
            risk_level=risk_level,
            risk_score=risk_score,
            scam_category=category,
            channel_count=len({p.username for p in posts_in}),
            post_count=len(posts_in),
            shared_entities=shared[:10],
            estimated_reach=total_reach,
            victim_estimate=victim_estimate,
        )

    def _score_campaign(self, posts: List[ScrapedPost], entities: List[str]) -> float:
        """Score campaign risk 0–100."""
        size_score = min(40, len(posts) * 3)
        entity_score = min(30, len(entities) * 5)
        platform_score = min(20, len({p.source for p in posts}) * 7)
        reach_score = min(10, sum(p.subscriber_count for p in posts) / 10000)
        return round(min(100, size_score + entity_score + platform_score + reach_score), 1)

    @staticmethod
    def _risk_level(score: float) -> str:
        if score >= 75: return "CRITICAL"
        if score >= 50: return "HIGH"
        if score >= 25: return "MEDIUM"
        return "LOW"

    def _generate_name(
        self,
        posts: List[ScrapedPost],
        phones: List[str],
        upis: List[str],
        tg_links: List[str],
    ) -> str:
        """Generate human-readable campaign name using pattern matching."""
        all_text = " ".join(p.caption_text.lower() for p in posts)

        # Detect scam type
        if re.search(r"\bipl\b|cricket|betting|match|satta", all_text):
            base = "IPL Betting Ring"
        elif re.search(r"zerodha|angel|groww|upstox|stock|invest|mutual fund", all_text):
            base = "Fake Investment Network"
        elif re.search(r"digital arrest|cbi|ed |enforcement|aadhaar", all_text):
            base = "Digital Arrest Ring"
        elif re.search(r"customer care|helpline|bank|atm|otp", all_text):
            base = "Fake Customer Care Network"
        elif re.search(r"job|vacancy|hiring|work from home|घर से काम", all_text):
            base = "Job Scam Ring"
        elif re.search(r"lottery|prize|won|winner|congratulation", all_text):
            base = "Lottery Scam Network"
        else:
            base = "Unidentified Scam Network"

        # Add geography if detectable
        geo_match = re.search(
            r"\b(gurugram|delhi|mumbai|hyderabad|bengaluru|jamtara|noida)\b", all_text
        )
        geo = geo_match.group(1).title() if geo_match else ""

        return f"{base}{' — ' + geo if geo else ''}"

    def _detect_category(self, posts: List[ScrapedPost]) -> str:
        """Detect primary scam category from post texts."""
        text = " ".join(p.caption_text.lower() for p in posts)
        if re.search(r"invest|return|profit|mutual fund", text):
            return "Investment Scam"
        if re.search(r"betting|cricket|ipl|satta", text):
            return "Real Money Betting"
        if re.search(r"arrest|cbi|ed |court|warrant", text):
            return "Digital Arrest"
        if re.search(r"customer care|helpline|bank", text):
            return "Fake Customer Care"
        if re.search(r"job|hiring|vacancy", text):
            return "Job Scam"
        if re.search(r"lottery|prize|winner", text):
            return "Lottery Scam"
        return "Other"

    def _save_to_graph(
        self,
        campaigns: List[ScamCampaign],
        post_map: Dict[str, ScrapedPost],
    ) -> None:
        """Non-blocking save to Neo4j graph."""
        if not self._graph_builder:
            return
        try:
            for campaign in campaigns[:10]:  # limit to top 10
                self._graph_builder.merge_campaign(
                    campaign_id=campaign.id,
                    name=campaign.name,
                    channels=[],  # channels added separately
                    risk_level=campaign.risk_level,
                    scam_category=campaign.scam_category,
                    victim_estimate=campaign.victim_estimate,
                )
        except Exception as e:
            logger.debug("Graph save failed: %s", e)
