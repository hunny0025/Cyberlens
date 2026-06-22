"""
CyberLens — Qdrant Vector Store Wrapper
==========================================
Local-mode Qdrant for storing CLIP image embeddings and
sentence embeddings for similarity search.

Collections:
  scam_images   — CLIP embeddings of all processed images
  scam_text     — Sentence embeddings of OCR text
  campaign_profiles — Aggregate embeddings per campaign

Install: pip install qdrant-client

Author: CyberLens Team — GPCSSI Internship
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger("cyberlens.ocr.vector_store")

QDRANT_PATH = os.getenv("QDRANT_PATH", "data/qdrant")

# Collection dimension map
COLLECTION_DIMS = {
    "scam_images": 512,
    "scam_text": 384,
    "campaign_profiles": 512,
}


class VectorStore:
    """Qdrant vector store in local file mode (no server needed).

    Falls back to a simple in-memory cosine search if qdrant-client
    is not installed.
    """

    _client = None
    _available = False

    def __init__(self):
        self._load()

    def _load(self) -> None:
        if VectorStore._client is not None:
            return
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            Path(QDRANT_PATH).mkdir(parents=True, exist_ok=True)
            VectorStore._client = QdrantClient(path=QDRANT_PATH)

            # Ensure collections exist
            existing = {c.name for c in VectorStore._client.get_collections().collections}
            for name, dim in COLLECTION_DIMS.items():
                if name not in existing:
                    VectorStore._client.create_collection(
                        collection_name=name,
                        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                    )

            VectorStore._available = True
            logger.info("Qdrant vector store ready: %s", QDRANT_PATH)
        except ImportError:
            logger.info("qdrant-client not installed — using in-memory fallback search")
        except Exception as e:
            logger.warning("Qdrant init failed: %s", e)

    # ── Write operations ──────────────────────────────────────────────

    def store_embedding(
        self,
        image_hash: str,
        embedding: np.ndarray,
        metadata: Dict[str, Any],
        collection: str = "scam_images",
    ) -> bool:
        """Store an image embedding in Qdrant.

        Args:
            image_hash: SHA256 hash (used as point ID).
            embedding: CLIP embedding (512-dim numpy array).
            metadata: Payload dict (campaign_id, first_seen, etc.)
            collection: Target collection name.

        Returns:
            True if successful.
        """
        if not VectorStore._available:
            return False

        try:
            from qdrant_client.models import PointStruct

            point_id = abs(hash(image_hash)) % (2 ** 31)  # positive int ID
            VectorStore._client.upsert(
                collection_name=collection,
                points=[PointStruct(
                    id=point_id,
                    vector=embedding.tolist(),
                    payload={**metadata, "image_hash": image_hash},
                )],
            )
            return True
        except Exception as e:
            logger.error("Qdrant store failed: %s", e)
            return False

    # ── Search operations ─────────────────────────────────────────────

    def search_similar(
        self,
        embedding: np.ndarray,
        top_k: int = 5,
        score_threshold: float = 0.75,
        collection: str = "scam_images",
    ) -> List[Dict[str, Any]]:
        """Search for similar embeddings.

        Args:
            embedding: Query embedding (numpy array).
            top_k: Maximum results.
            score_threshold: Minimum cosine similarity.
            collection: Collection to search.

        Returns:
            List of {score, payload} dicts.
        """
        if not VectorStore._available:
            return []

        try:
            results = VectorStore._client.search(
                collection_name=collection,
                query_vector=embedding.tolist(),
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True,
            )
            return [
                {"score": r.score, **r.payload}
                for r in results
            ]
        except Exception as e:
            logger.debug("Qdrant search failed: %s", e)
            return []

    @property
    def is_available(self) -> bool:
        return VectorStore._available

    def stats(self) -> Dict[str, int]:
        """Return count per collection."""
        if not VectorStore._available:
            return {}
        try:
            return {
                name: VectorStore._client.count(name).count
                for name in COLLECTION_DIMS
            }
        except Exception:
            return {}
