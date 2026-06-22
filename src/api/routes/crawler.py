"""
CyberLens — Crawler Feed API Routes
=======================================
Serves live social media scraper feed with synthetic fallback.

Endpoints:
    GET  /api/crawler/feed       — get latest items (scraper first, fallback synthetic)
    POST /api/crawler/scrape-now — trigger fresh scrape manually
    GET  /api/statistics         — dashboard aggregated stats
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from src.api.schemas import (
    CrawlerFeedResponse,
    CrawlerItemResponse,
    StatsResponse,
)
from src.database import crud, db

logger = logging.getLogger("cyberlens.api.crawler")

router = APIRouter(prefix="/api", tags=["Crawler & Stats"])


# ---------------------------------------------------------------------------
# Helper: convert ScrapedPost → CrawlerItemResponse
# ---------------------------------------------------------------------------

def _scraped_to_response(post) -> CrawlerItemResponse:
    """Convert a ScrapedPost to the API response model."""
    return CrawlerItemResponse(
        source_url=post.post_url or "",
        raw_text=(post.caption_text or "")[:200],
        image_text="",  # OCR text extracted separately
        category_hint=getattr(post, "source", "UNKNOWN"),
        timestamp=post.timestamp or "",
        record_id=post.id or "",
    )


def _crawler_item_to_response(item) -> CrawlerItemResponse:
    """Convert a CrawlerItem to the API response model."""
    return CrawlerItemResponse(
        source_url=item.source_url or "",
        raw_text=(item.raw_text or "")[:200],
        image_text=(item.image_text or "")[:200],
        category_hint=item.category_hint or "",
        timestamp=item.timestamp or "",
        record_id=item.record_id or "",
    )


# ---------------------------------------------------------------------------
# GET /api/crawler/feed
# ---------------------------------------------------------------------------

@router.get("/crawler/feed", response_model=CrawlerFeedResponse)
async def get_crawler_feed(
    request: Request,
    limit: int = 20,
    session: Session = Depends(db.get_db),
):
    """Get latest items from the crawler feed.

    Tries the live SocialScraperManager first. If no real scraped posts
    are available (scraper not configured, no Playwright, or no results),
    falls back to SyntheticFeed.

    If both are available and SyntheticFeed has data, returns a mixed
    feed (30% real, 70% synthetic) for richer demo experience.

    Auto-ingests new items into the database as PENDING cases.
    """
    response_items: list[CrawlerItemResponse] = []
    total_ingested = 0
    total_available = 0
    source_label = "none"

    # ── Try social scraper first ──────────────────────────────────────────
    social_scraper = getattr(request.app.state, "social_scraper", None)
    real_posts = []

    if social_scraper:
        try:
            # Get recently scraped posts (don't trigger a new scrape on every feed request)
            real_posts = social_scraper.get_recent_posts(limit=limit)
            if real_posts:
                source_label = "social_scraper"
                logger.info("Feed: using %d real scraped posts", len(real_posts))
        except Exception as e:
            logger.warning("Social scraper recent posts failed: %s", e)

    # ── Get synthetic feed ────────────────────────────────────────────────
    synthetic_feed = getattr(request.app.state, "synthetic_feed", None)

    if real_posts and synthetic_feed:
        # Mix real + synthetic for richer feed
        try:
            mixed = synthetic_feed.mix_with_real(real_posts, ratio=0.3)
            response_items = [_scraped_to_response(p) for p in mixed[:limit]]
            total_ingested = (
                social_scraper.total_scraped if social_scraper else 0
            ) + synthetic_feed.ingested_count
            total_available = synthetic_feed.total_records
            source_label = "mixed"
            logger.info("Feed: mixed mode — %d items", len(response_items))
        except Exception as e:
            logger.warning("Feed mixing failed, falling back: %s", e)
            response_items = [_scraped_to_response(p) for p in real_posts[:limit]]

    elif real_posts:
        # Real posts only
        response_items = [_scraped_to_response(p) for p in real_posts[:limit]]
        total_ingested = social_scraper.total_scraped if social_scraper else 0
        total_available = total_ingested

    elif synthetic_feed:
        # Synthetic fallback
        try:
            items = synthetic_feed.fetch_new_items(limit=limit)
            response_items = [_crawler_item_to_response(item) for item in items]
            total_ingested = synthetic_feed.ingested_count
            total_available = synthetic_feed.total_records
            source_label = "synthetic"
        except Exception as e:
            logger.error("Synthetic feed also failed: %s", e)

    else:
        # Legacy: try old SyntheticCrawler from app.state.crawler
        crawler = getattr(request.app.state, "crawler", None)
        if crawler:
            try:
                items = crawler.fetch_new_items(limit=limit)
                response_items = [_crawler_item_to_response(item) for item in items]
                total_ingested = crawler.ingested_count
                total_available = crawler.total_records
                source_label = "legacy_synthetic"
            except Exception as e:
                logger.error("Legacy crawler also failed: %s", e)

    # ── Auto-ingest into DB as PENDING cases ──────────────────────────────
    ingested_count = 0
    for item in response_items:
        try:
            case_data = {
                "source_type": "CRAWLER",
                "source_url": item.source_url,
                "ocr_text": item.raw_text,
                "scam_category": item.category_hint if item.category_hint not in (
                    "INSTAGRAM", "FACEBOOK", "TELEGRAM", "SYNTHETIC", "UNKNOWN"
                ) else None,
                "status": "PENDING",
                "severity": "MEDIUM",
            }
            crud.create_case(session, case_data)
            ingested_count += 1
        except Exception as e:
            logger.debug("Failed to auto-ingest item: %s", e)

    try:
        session.commit()
    except Exception:
        session.rollback()

    # ── Log crawler activity ──────────────────────────────────────────────
    try:
        crud.create_crawler_log(
            session,
            source=source_label,
            items_found=len(response_items),
            items_flagged=ingested_count,
        )
        session.commit()
    except Exception:
        session.rollback()

    logger.info(
        "Feed response: %d items (source=%s, ingested=%d)",
        len(response_items), source_label, ingested_count,
    )

    return CrawlerFeedResponse(
        items=response_items,
        total_ingested=total_ingested,
        total_available=total_available,
    )


# ---------------------------------------------------------------------------
# POST /api/crawler/scrape-now
# ---------------------------------------------------------------------------

@router.post("/crawler/scrape-now")
async def trigger_scrape(
    request: Request,
    limit_per_source: int = 20,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: Session = Depends(db.get_db),
):
    """Trigger a fresh social media scrape manually.

    Runs all configured scrapers (Instagram, Facebook, Telegram)
    and returns the newly discovered posts. This is a potentially
    slow operation (30–120s) depending on network and platform load.

    Returns the scrape results immediately if fast enough, or
    kicks off a background task for long-running scrapes.
    """
    social_scraper = getattr(request.app.state, "social_scraper", None)

    if not social_scraper:
        return {
            "status": "unavailable",
            "message": (
                "SocialScraperManager not initialized. "
                "Ensure Playwright is installed: pip install playwright && playwright install chromium"
            ),
            "sources": {},
            "posts": [],
        }

    # Check which sources are available
    sources = social_scraper.sources_available

    if not any(sources.values()):
        return {
            "status": "no_sources",
            "message": (
                "No scraper sources available. Install: "
                "pip install playwright telethon && playwright install chromium"
            ),
            "sources": sources,
            "posts": [],
        }

    # Run scrape
    logger.info("Manual scrape triggered — limit_per_source=%d", limit_per_source)

    try:
        posts = await social_scraper.fetch_all(limit_per_source=limit_per_source)
    except Exception as e:
        logger.error("Manual scrape failed: %s", e)
        return {
            "status": "error",
            "message": str(e),
            "sources": sources,
            "posts": [],
        }

    # Auto-ingest new posts into DB
    ingested = 0
    for post in posts:
        try:
            case_data = {
                "source_type": "CRAWLER",
                "source_url": post.post_url,
                "ocr_text": post.caption_text,
                "status": "PENDING",
                "severity": "MEDIUM",
            }
            crud.create_case(session, case_data)
            ingested += 1
        except Exception as e:
            logger.debug("Failed to ingest scraped post: %s", e)

    try:
        session.commit()
    except Exception:
        session.rollback()

    # Log
    try:
        crud.create_crawler_log(
            session,
            source="manual_scrape",
            query=f"limit_per_source={limit_per_source}",
            items_found=len(posts),
            items_flagged=ingested,
        )
        session.commit()
    except Exception:
        session.rollback()

    logger.info(
        "Manual scrape complete: %d posts scraped, %d ingested to DB",
        len(posts), ingested,
    )

    return {
        "status": "success",
        "message": f"Scraped {len(posts)} posts from {sum(sources.values())} sources",
        "sources": sources,
        "posts_scraped": len(posts),
        "posts_ingested": ingested,
        "posts": [
            {
                "id": p.id,
                "source": p.source,
                "post_url": p.post_url,
                "caption_preview": (p.caption_text or "")[:150],
                "username": p.username,
                "timestamp": p.timestamp,
            }
            for p in posts[:50]  # Cap response size
        ],
    }


# ---------------------------------------------------------------------------
# GET /api/statistics
# ---------------------------------------------------------------------------

@router.get("/statistics", response_model=StatsResponse)
async def get_statistics(
    session: Session = Depends(db.get_db),
):
    """Get aggregated dashboard statistics."""
    stats = crud.get_statistics(session)
    return StatsResponse(**stats.to_dict())
