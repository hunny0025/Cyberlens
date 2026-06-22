"""
CyberLens — FastAPI Application (v2.0)
=========================================
Main FastAPI app wiring all modules: ML models, scrapers,
WebSocket, statistics, background worker.

Usage:
    uvicorn src.api.main:app --reload --port 8000

Author: CyberLens Team — GPCSSI Internship
"""

import logging
import os
import sys
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

# ── Windows asyncio fix (required for Playwright subprocess support) ────────
# Uvicorn uses SelectorEventLoop on Windows which blocks subprocess creation.
# Playwright needs ProactorEventLoop to spawn browser processes.
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.routes import analysis, cases, crawler, i4c
from src.api.routes import statistics as stats_routes
from src.api.routes import websocket as ws_routes
from src.api.routes import graph as graph_routes
from src.api.routes import intelligence as intel_routes
from src.api.routes import monitor as monitor_routes
from src.api.routes import auth as auth_routes
from src.api.routes import actions as action_routes
from src.api.routes import complaints as complaint_routes
from src.api.routes import fingerprinting as fingerprint_routes
from src.api.routes import evaluation as eval_routes
from src.api.routes import pipeline as pipeline_routes
from src.database.db import init_db

logger = logging.getLogger("cyberlens.api")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Install PII masking filter (prevents phone/UPI/Aadhaar in logs)
try:
    from src.auth.encryption import install_pii_filter
    install_pii_filter(enable=os.getenv("PII_MASKING", "true").lower() == "true")
except Exception:
    pass

# Default to auth disabled for dev convenience
if "AUTH_DISABLED" not in os.environ:
    os.environ["AUTH_DISABLED"] = "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialize DB, models, scrapers, worker."""
    logger.info("=" * 60)
    logger.info("  CyberLens API v2.0 Starting...")
    logger.info("  Gurugram Police / GPCSSI India")
    logger.info("=" * 60)

    # Initialize database
    try:
        init_db()
        logger.info("✓ Database initialized")
    except Exception as e:
        logger.error("✗ Database initialization failed: %s", e)

    # Initialize Neo4j (graceful — app works without it)
    try:
        from src.graph import neo4j_client as neo4j
        from src.graph.neo4j_client import create_constraints
        if neo4j.is_available():
            create_constraints()
            logger.info("✓ Neo4j graph DB connected — constraints created")
        else:
            logger.info("○ Neo4j not configured — graph features in demo mode")
    except Exception as e:
        logger.warning("○ Neo4j unavailable: %s", e)

    # Initialize Monitor Orchestrator
    try:
        from src.monitor.monitor_orchestrator import MonitorOrchestrator
        orchestrator = MonitorOrchestrator(app=app)
        app.state.monitor_orchestrator = orchestrator
        await orchestrator.start()
        logger.info("✓ Monitor Orchestrator started")
    except Exception as e:
        logger.warning("✗ Monitor Orchestrator: %s", e)
        app.state.monitor_orchestrator = None

    # Load ML models
    _load_models(app)

    # Load social scraper (Playwright-based)
    try:
        from src.crawler.social_scraper import SocialScraperManager
        app.state.social_scraper = SocialScraperManager(delay=2.0)
        sources = app.state.social_scraper.sources_available
        logger.info("✓ SocialScraperManager — IG=%s FB=%s TG=%s",
                     sources["instagram"], sources["facebook"], sources["telegram"])
    except Exception as e:
        logger.warning("✗ SocialScraperManager: %s", e)
        app.state.social_scraper = None

    # Load synthetic feed (fallback / mixing)
    try:
        from src.crawler.synthetic_feed import SyntheticFeed
        app.state.synthetic_feed = SyntheticFeed()
        app.state.crawler = app.state.synthetic_feed
        logger.info("✓ SyntheticFeed (%d records)", app.state.synthetic_feed.total_records)
    except Exception as e:
        logger.warning("✗ SyntheticFeed: %s", e)
        app.state.synthetic_feed = None
        app.state.crawler = None

    # Start background scraper worker
    scraper_worker = None
    try:
        from src.api.background.scraper_worker import ScraperWorker
        scraper_worker = ScraperWorker(app, interval_seconds=1800)
        app.state.scraper_worker = scraper_worker
        # Auto-start if social scraper is available
        if app.state.social_scraper and any(
            app.state.social_scraper.sources_available.values()
        ):
            await scraper_worker.start()
            logger.info("✓ ScraperWorker started (interval=30min)")
        else:
            logger.info("✓ ScraperWorker ready (not auto-started — no scrapers)")
    except Exception as e:
        logger.warning("✗ ScraperWorker: %s", e)
        app.state.scraper_worker = None

    logger.info("=" * 60)
    logger.info("  CyberLens API Ready — http://0.0.0.0:8000")
    logger.info("  Docs: http://0.0.0.0:8000/docs")
    logger.info("  WebSocket: ws://0.0.0.0:8000/ws/scraper-feed")
    logger.info("=" * 60)

    yield

    # Cleanup
    if scraper_worker:
        await scraper_worker.stop()
    logger.info("CyberLens API shutting down...")


def _load_models(app: FastAPI) -> None:
    """Load all ML models into app.state."""

    # OCR Manager
    try:
        from src.ocr.ocr_manager import OCRManager
        app.state.ocr_manager = OCRManager(enable_vision_fallback=True)
        logger.info("✓ OCR Manager (type-aware + Hindi cleaner)")
    except Exception as e:
        logger.warning("✗ OCR Manager: %s", e)
        app.state.ocr_manager = None

    # Scam Classifier (14-category trained DistilBERT)
    try:
        from src.classifier.scam_classifier import ScamClassifier
        app.state.classifier = ScamClassifier(
            model_dir=str(PROJECT_ROOT / "models" / "scam_classifier"),
        )
        logger.info("✓ Scam Classifier (loaded=%s, categories=%d)",
                     app.state.classifier.is_loaded,
                     app.state.classifier.category_count)
    except Exception as e:
        logger.warning("✗ Scam Classifier: %s", e)
        app.state.classifier = None

    # Deepfake Detector
    try:
        from src.deepfake.detector import DeepfakeDetector
        app.state.deepfake_detector = DeepfakeDetector(
            model_dir=str(PROJECT_ROOT / "models" / "deepfake_detector"),
        )
        logger.info("✓ Deepfake Detector (loaded=%s)",
                     app.state.deepfake_detector.is_loaded)
    except Exception as e:
        logger.warning("✗ Deepfake Detector: %s", e)
        app.state.deepfake_detector = None

    # Intent Analyzer (ScamDeepfakeAnalyzer)
    try:
        from src.deepfake.intent_analyzer import IntentAnalyzer
        app.state.intent_analyzer = IntentAnalyzer()
        logger.info("✓ Intent Analyzer (celebrity DB loaded)")
    except Exception as e:
        logger.warning("✗ Intent Analyzer: %s", e)
        app.state.intent_analyzer = None

    # Legal Mapper
    try:
        from src.deepfake.legal_mapper import LegalMapper
        app.state.legal_mapper = LegalMapper()
        logger.info("✓ Legal Mapper")
    except Exception as e:
        logger.warning("✗ Legal Mapper: %s", e)
        app.state.legal_mapper = None


# Create FastAPI app
app = FastAPI(
    title="CyberLens API",
    description=(
        "AI-powered cybercrime detection API for Gurugram Police / GPCSSI India. "
        "Provides multi-category scam classification (14 types), deepfake detection "
        "with use-case inference, OCR with Hindi/entity extraction, real-time "
        "social media scraping, and I4C submission."
    ),
    version="3.0.0",
    lifespan=lifespan,
)

# CORS — allow Vercel frontend + local dev origins
_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
# In production, FRONTEND_URL points to the Vercel deployment
_frontend_url = os.getenv("FRONTEND_URL")
if _frontend_url:
    _origins.append(_frontend_url.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analysis.router)
app.include_router(cases.router)
app.include_router(i4c.router)
app.include_router(crawler.router)
app.include_router(stats_routes.router)
app.include_router(ws_routes.router)
app.include_router(graph_routes.router)
app.include_router(intel_routes.router)
app.include_router(monitor_routes.router)
app.include_router(auth_routes.router)
app.include_router(action_routes.router)
app.include_router(complaint_routes.router)
app.include_router(fingerprint_routes.router)
app.include_router(eval_routes.router)
app.include_router(pipeline_routes.router)


# ---------------------------------------------------------------------------
# Scraper control endpoints
# ---------------------------------------------------------------------------

@app.get("/api/scraper/status", tags=["Scraper Control"])
async def scraper_status():
    """Get background scraper worker status."""
    worker = getattr(app.state, "scraper_worker", None)
    social = getattr(app.state, "social_scraper", None)

    return {
        "worker": worker.status if worker else {"running": False},
        "sources": social.sources_available if social else {},
        "total_scraped": social.total_scraped if social else 0,
    }


@app.post("/api/scraper/start", tags=["Scraper Control"])
async def start_scraper():
    """Start the background scraper worker."""
    worker = getattr(app.state, "scraper_worker", None)
    if not worker:
        return {"status": "error", "message": "ScraperWorker not initialized"}
    if worker.running:
        return {"status": "already_running"}
    await worker.start()
    return {"status": "started", "interval": worker.interval_seconds}


@app.post("/api/scraper/stop", tags=["Scraper Control"])
async def stop_scraper():
    """Stop the background scraper worker."""
    worker = getattr(app.state, "scraper_worker", None)
    if not worker:
        return {"status": "error", "message": "ScraperWorker not initialized"}
    if not worker.running:
        return {"status": "already_stopped"}
    await worker.stop()
    return {"status": "stopped"}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
async def health_check():
    """System health check with model and scraper status."""
    social = getattr(app.state, "social_scraper", None)
    worker = getattr(app.state, "scraper_worker", None)

    return {
        "status": "healthy",
        "service": "CyberLens API",
        "version": "2.0.0",
        "models": {
            "ocr_manager": getattr(app.state, "ocr_manager", None) is not None,
            "classifier": getattr(app.state, "classifier", None) is not None,
            "classifier_loaded": getattr(
                getattr(app.state, "classifier", None), "is_loaded", False
            ),
            "deepfake_detector": getattr(app.state, "deepfake_detector", None) is not None,
            "deepfake_loaded": getattr(
                getattr(app.state, "deepfake_detector", None), "is_loaded", False
            ),
            "intent_analyzer": getattr(app.state, "intent_analyzer", None) is not None,
            "legal_mapper": getattr(app.state, "legal_mapper", None) is not None,
        },
        "scrapers": {
            "social_scraper": social is not None,
            "sources": social.sources_available if social else {},
            "synthetic_feed": getattr(app.state, "synthetic_feed", None) is not None,
            "worker_running": worker.running if worker else False,
        },
    }
