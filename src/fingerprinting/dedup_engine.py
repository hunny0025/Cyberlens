"""
CyberLens — Deduplication Engine
==================================
Prevents the same post from being analyzed twice.

Signals used:
  1. URL hash     — exact same post URL
  2. Image pHash  — near-identical images (Hamming distance ≤ 4)
  3. Content hash — same caption text (first 200 chars)

Author: CyberLens Team — GPCSSI Internship
"""

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set

logger = logging.getLogger("cyberlens.fingerprinting.dedup")


@dataclass
class DeduplicationResult:
    """Result of a deduplication check."""
    is_duplicate: bool
    matched_signal: Optional[str]  # "url" / "phash" / "content" / None
    canonical_id: Optional[str]    # ID of the original post (if duplicate)


class DedupEngine:
    """Prevents duplicate post analysis using multi-signal hashing.

    Designed to be instantiated once and reused across the monitoring
    lifecycle. Thread-safe for read, but NOT for concurrent writes.
    """

    # Max Hamming distance for pHash near-duplicate detection
    PHASH_THRESHOLD = 4

    def __init__(self):
        self._seen_urls: Set[str] = set()
        self._seen_content: Set[str] = set()
        # pHash → canonical post_id map (for fuzzy lookup)
        self._phash_map: Dict[str, str] = {}
        self._total_deduped = 0

    # ── Public API ────────────────────────────────────────────────────

    def is_duplicate(self, post: Any) -> bool:
        """Check if a post has already been processed.

        Args:
            post: Object or dict with post_url, image_phash, caption_text.

        Returns:
            True if the post is a duplicate of one already seen.
        """
        result = self.check(post)
        return result.is_duplicate

    def check(self, post: Any) -> DeduplicationResult:
        """Full dedup check with signal details.

        Returns:
            DeduplicationResult with match signal and canonical ID.
        """
        url     = _attr(post, "post_url")
        phash   = _attr(post, "image_phash")
        text    = _attr(post, "caption_text")
        post_id = _attr(post, "post_id") or _attr(post, "id") or ""

        # ── Signal 1: URL hash ──────────────────────────────────────
        if url:
            url_hash = _sha256(url)
            if url_hash in self._seen_urls:
                self._total_deduped += 1
                return DeduplicationResult(True, "url", url_hash[:8])
            self._seen_urls.add(url_hash)

        # ── Signal 2: pHash (perceptual, fuzzy) ─────────────────────
        if phash:
            match = self._find_phash_match(phash)
            if match:
                self._total_deduped += 1
                return DeduplicationResult(True, "phash", match)
            self._phash_map[phash] = post_id

        # ── Signal 3: Content hash ───────────────────────────────────
        if text:
            content_hash = _sha256(text[:200])
            if content_hash in self._seen_content:
                self._total_deduped += 1
                return DeduplicationResult(True, "content", content_hash[:8])
            self._seen_content.add(content_hash)

        return DeduplicationResult(False, None, None)

    def get_canonical(self, post: Any) -> Optional[str]:
        """Return the canonical post ID if this post is a duplicate.

        Args:
            post: Post to check.

        Returns:
            Canonical post_id string, or None if not a duplicate.
        """
        result = self.check(post)
        return result.canonical_id if result.is_duplicate else None

    def reset(self) -> None:
        """Clear all seen sets (e.g. start of new monitoring session)."""
        self._seen_urls.clear()
        self._seen_content.clear()
        self._phash_map.clear()
        self._total_deduped = 0

    @property
    def total_deduped(self) -> int:
        return self._total_deduped

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "seen_urls": len(self._seen_urls),
            "seen_phashes": len(self._phash_map),
            "seen_content": len(self._seen_content),
            "total_deduped": self._total_deduped,
        }

    # ── Private ───────────────────────────────────────────────────────

    def _find_phash_match(self, phash: str) -> Optional[str]:
        """Find a near-duplicate pHash within Hamming threshold."""
        try:
            h_new = int(phash, 16)
        except ValueError:
            return None

        for stored_phash, stored_id in self._phash_map.items():
            if len(stored_phash) != len(phash):
                continue
            try:
                h_stored = int(stored_phash, 16)
                hamming = bin(h_new ^ h_stored).count("1")
                if hamming <= self.PHASH_THRESHOLD:
                    return stored_id
            except ValueError:
                continue

        return None


# ── Helpers ────────────────────────────────────────────────────────────

def _attr(obj: Any, key: str) -> str:
    """Safely get attribute from object or dict."""
    if isinstance(obj, dict):
        return str(obj.get(key, ""))
    return str(getattr(obj, key, "") or "")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()
