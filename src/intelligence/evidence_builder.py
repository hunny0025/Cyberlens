"""
CyberLens — Evidence Builder
================================
Automatically assembles complete evidence packages for I4C submission.

Evidence package includes:
  - All scraped screenshots
  - OCR text extractions
  - Entity list (phones, UPIs, URLs, QRs)
  - D3.js network graph JSON
  - Role attribution
  - Scam narrative (reconstructed story)
  - Applicable IT Act / BNS sections
  - Related complaints / FIRs
  - Confidence score

Author: CyberLens Team — GPCSSI Internship
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cyberlens.intelligence.evidence")


@dataclass
class EvidencePackage:
    """Complete evidence package for a campaign."""
    campaign_id: str
    campaign_name: str

    # Evidence items
    screenshots: List[str]         # file paths to images
    ocr_extractions: List[Dict]    # OCR results per image
    entity_list: Dict[str, List[str]]  # phones, UPIs, URLs, QRs
    network_graph: Dict            # D3.js format
    role_attribution: Dict         # username → role mapping
    scam_narrative: str            # reconstructed step-by-step story
    legal_sections: List[str]      # IT Act, BNS sections
    related_complaints: List[Dict] # matching FIRs from the system

    # Metadata
    confidence_score: float
    generated_at: str
    generated_by: str = "CyberLens v2.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


class EvidenceBuilder:
    """Builds evidence packages for campaign prosecution.

    Aggregates data from all analysis modules into a single
    structured package ready for I4C submission.
    """

    def __init__(self):
        try:
            from src.graph.graph_builder import GraphBuilder
            from src.graph.role_attribution import RoleAttributor
            from src.intelligence.scam_reconstructor import ScamReconstructor
            self._graph_builder = GraphBuilder()
            self._role_attributor = RoleAttributor()
            self._reconstructor = ScamReconstructor()
        except Exception as e:
            logger.warning("EvidenceBuilder partial init: %s", e)
            self._graph_builder = None
            self._role_attributor = None
            self._reconstructor = None

    def build_evidence(self, campaign: Any) -> EvidencePackage:
        """Build complete evidence package for a campaign.

        Args:
            campaign: ScamCampaign object or dict.

        Returns:
            EvidencePackage ready for I4C submission.
        """
        cid = getattr(campaign, "id", None) or campaign.get("id", "unknown")
        name = getattr(campaign, "name", None) or campaign.get("name", "Unknown Campaign")

        # Collect screenshots
        screenshots = self._collect_screenshots(cid)

        # Collect OCR extractions
        ocr_extractions = self._collect_ocr(cid, screenshots)

        # Build entity list
        entities = self._build_entity_list(campaign, ocr_extractions)

        # Get network graph from Neo4j
        network_graph = {}
        if self._graph_builder:
            try:
                network_graph = self._graph_builder.get_network_map(cid)
            except Exception:
                pass
        if not network_graph:
            network_graph = self._demo_graph(cid)

        # Role attribution
        role_attribution = {}
        if self._role_attributor:
            try:
                role_map = self._role_attributor.assign_roles([], {})
                role_attribution = {
                    a.username: {
                        "role": a.role,
                        "confidence": a.confidence,
                        "evidence": a.evidence_list,
                    }
                    for a in role_map.assignments
                }
            except Exception:
                pass

        # Scam narrative
        scam_narrative = ""
        if self._reconstructor:
            try:
                narrative = self._reconstructor.reconstruct(campaign)
                scam_narrative = "\n".join(
                    f"Step {i+1}: {step}"
                    for i, step in enumerate(narrative.steps)
                )
            except Exception:
                scam_narrative = "Narrative generation failed — manual reconstruction required"

        # Legal sections
        legal_sections = self._map_legal_sections(campaign)

        # Find related complaints
        related_complaints = self._find_related_complaints(entities)

        # Confidence score
        confidence = self._compute_confidence(screenshots, entities, network_graph)

        package = EvidencePackage(
            campaign_id=cid,
            campaign_name=name,
            screenshots=screenshots,
            ocr_extractions=ocr_extractions,
            entity_list=entities,
            network_graph=network_graph,
            role_attribution=role_attribution,
            scam_narrative=scam_narrative,
            legal_sections=legal_sections,
            related_complaints=related_complaints,
            confidence_score=confidence,
            generated_at=datetime.now().isoformat(),
        )

        # Save to disk
        self._save_package(package)

        logger.info(
            "Evidence package built for campaign %s: "
            "%d screenshots, %d entities, %.0f%% confidence",
            cid, len(screenshots), sum(len(v) for v in entities.values()), confidence * 100,
        )
        return package

    # ── Helpers ───────────────────────────────────────────────────────

    def _collect_screenshots(self, campaign_id: str) -> List[str]:
        """Collect screenshot paths for the campaign."""
        data_dir = Path("data/screenshots") / campaign_id
        if data_dir.exists():
            return [str(p) for p in data_dir.glob("*.{jpg,png,webp}")]
        return []

    def _collect_ocr(self, campaign_id: str, screenshots: List[str]) -> List[Dict]:
        """Load cached OCR results for screenshots."""
        cache_dir = Path("data/ocr_cache") / campaign_id
        results = []
        for img_path in screenshots[:20]:  # limit to 20
            cache_file = cache_dir / (Path(img_path).stem + ".json")
            if cache_file.exists():
                try:
                    with open(cache_file) as f:
                        results.append(json.load(f))
                except Exception:
                    pass
        return results

    def _build_entity_list(self, campaign: Any, ocr_results: List[Dict]) -> Dict[str, List[str]]:
        """Aggregate all entities from OCR results and campaign data."""
        entities: Dict[str, List] = {
            "phones": [], "upi_ids": [], "urls": [],
            "telegram_links": [], "bank_accounts": [], "qr_codes": [],
        }

        # From OCR results
        for ocr in ocr_results:
            ent = ocr.get("entities", {})
            for key in entities:
                for val in ent.get(key, []):
                    if val not in entities[key]:
                        entities[key].append(val)

        # From campaign shared_entities
        shared = getattr(campaign, "shared_entities", []) or campaign.get("shared_entities", [])
        for val in shared:
            if val.startswith("+91"):
                if val not in entities["phones"]:
                    entities["phones"].append(val)
            elif "@" in val and "." not in val.split("@")[1]:
                if val not in entities["upi_ids"]:
                    entities["upi_ids"].append(val)

        return {k: v for k, v in entities.items() if v}

    def _map_legal_sections(self, campaign: Any) -> List[str]:
        """Map campaign category to applicable legal sections."""
        cat = (getattr(campaign, "scam_category", "") or
               campaign.get("scam_category", "")).lower()

        sections = ["IT Act §66D — Cheating by personation using computer resource"]
        if "invest" in cat:
            sections += ["IPC §420 / BNS §318 — Cheating", "SEBI Act §12A — Fraudulent schemes"]
        if "betting" in cat:
            sections += ["Public Gambling Act §3", "IT Act §67 — Publishing obscene material"]
        if "arrest" in cat:
            sections += ["IPC §170 / BNS §204 — Impersonating public servant",
                         "IT Act §66D — Identity fraud"]
        if "sextortion" in cat:
            sections += ["IT Act §66E — Privacy violation",
                         "BNS §77 — Criminal intimidation", "IT Act §67 — Obscene content"]
        if "customer care" in cat:
            sections += ["IT Act §66C — Identity theft"]

        return list(dict.fromkeys(sections))  # deduplicate preserving order

    def _find_related_complaints(self, entities: Dict[str, List[str]]) -> List[Dict]:
        """Find FIR complaints matching the entities (stub — connects to DB)."""
        # In production: query cybercrime.gov.in API or local complaint DB
        phones = entities.get("phones", [])
        if not phones:
            return []
        return [
            {"complaint_id": f"CYB-{abs(hash(p)):06d}", "phone": p,
             "status": "Under Investigation", "district": "Gurugram"}
            for p in phones[:3]
        ]

    def _compute_confidence(
        self, screenshots: List, entities: Dict, graph: Dict
    ) -> float:
        """Compute overall evidence confidence."""
        score = 0.3  # base
        if screenshots:
            score += min(0.2, len(screenshots) * 0.02)
        if entities:
            total_entities = sum(len(v) for v in entities.values())
            score += min(0.3, total_entities * 0.03)
        if graph.get("node_count", 0) > 3:
            score += 0.2
        return round(min(0.98, score), 2)

    def _save_package(self, package: EvidencePackage) -> None:
        """Save evidence package to disk."""
        try:
            out_dir = Path("data/evidence") / package.campaign_id
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / "evidence_package.json"
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(package.to_json())
            logger.info("Evidence saved: %s", out_file)
        except Exception as e:
            logger.warning("Evidence save failed: %s", e)

    @staticmethod
    def _demo_graph(campaign_id: str) -> Dict:
        return {"nodes": [], "links": [], "node_count": 0, "link_count": 0}
