#!/usr/bin/env python3
"""
CyberLens — Master Training Data Collection Script
======================================================
Orchestrates all data collection pipelines to build the
unified training dataset for CyberLens models.

Steps:
    1. Load labeled_channels.json (ground truth seed list)
    2. Collect full ChannelDataset for each labeled channel
    3. Scrape I4C advisories and CERT-In alerts
    4. Cross-reference collected entities against confirmed lists
    5. Save unified dataset to data/processed/training_dataset.json

Usage:
    python scripts/collect_training_data.py
    python scripts/collect_training_data.py --skip-telegram
    python scripts/collect_training_data.py --resume

Author: CyberLens Team — GPCSSI Internship
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "data_collection.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("cyberlens.collect")


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

LABELED_CHANNELS_PATH = PROJECT_ROOT / "data" / "ground_truth" / "labeled_channels.json"
I4C_ADVISORIES_PATH = PROJECT_ROOT / "data" / "ground_truth" / "i4c_advisories.json"
CERTIN_ALERTS_PATH = PROJECT_ROOT / "data" / "ground_truth" / "certin_alerts.json"
TRAINING_DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "training_dataset.json"
PROGRESS_PATH = PROJECT_ROOT / "data" / "processed" / ".collection_progress.json"


# ---------------------------------------------------------------------------
# Progress tracking (resume support)
# ---------------------------------------------------------------------------

def _load_progress() -> Dict[str, Any]:
    """Load collection progress for resume support."""
    if PROGRESS_PATH.exists():
        with open(PROGRESS_PATH, "r") as f:
            return json.load(f)
    return {"completed_channels": [], "step": 0}


def _save_progress(progress: Dict[str, Any]) -> None:
    """Save collection progress."""
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_PATH, "w") as f:
        json.dump(progress, f, indent=2)


# ---------------------------------------------------------------------------
# Cross-referencing
# ---------------------------------------------------------------------------

def _build_blocked_entity_set(
    i4c_path: Path, certin_path: Path
) -> Dict[str, Set[str]]:
    """Build sets of confirmed blocked entities from ground truth.

    Args:
        i4c_path: Path to I4C advisories JSON.
        certin_path: Path to CERT-In alerts JSON.

    Returns:
        Dict of entity_type → set of entity values.
    """
    blocked: Dict[str, Set[str]] = {
        "domains": set(),
        "urls": set(),
        "ips": set(),
        "channels": set(),
    }

    if i4c_path.exists():
        with open(i4c_path, "r", encoding="utf-8") as f:
            advisories = json.load(f)
        for adv in advisories:
            blocked["domains"].update(adv.get("blocked_domains", []))
            blocked["urls"].update(adv.get("blocked_urls", []))
            blocked["channels"].update(adv.get("blocked_channels", []))

    if certin_path.exists():
        with open(certin_path, "r", encoding="utf-8") as f:
            alerts = json.load(f)
        for alert in alerts:
            blocked["domains"].update(alert.get("domains", []))
            blocked["ips"].update(alert.get("ips", []))

    logger.info(
        "Blocked entity sets: %d domains, %d URLs, %d IPs, %d channels",
        len(blocked["domains"]),
        len(blocked["urls"]),
        len(blocked["ips"]),
        len(blocked["channels"]),
    )
    return blocked


def _cross_reference_channel(
    channel_data: Dict[str, Any],
    blocked: Dict[str, Set[str]],
) -> Dict[str, Any]:
    """Cross-reference a channel's entities against confirmed blocked lists.

    Args:
        channel_data: Channel dataset dict.
        blocked: Confirmed blocked entity sets.

    Returns:
        Channel data with added cross-reference results.
    """
    entities = channel_data.get("entities_found", {})
    xref = {
        "matched_blocked_domains": [],
        "matched_blocked_urls": [],
        "matched_blocked_channels": [],
        "blocked_entity_count": 0,
    }

    # Check URLs
    for url in entities.get("urls", []):
        if url in blocked["urls"]:
            xref["matched_blocked_urls"].append(url)

    # Check domains (extract from URLs)
    for url in entities.get("urls", []):
        for domain in blocked["domains"]:
            if domain in url:
                xref["matched_blocked_domains"].append(domain)

    # Check linked channels
    for ch in channel_data.get("linked_channels", []):
        if ch in blocked["channels"]:
            xref["matched_blocked_channels"].append(ch)

    xref["blocked_entity_count"] = (
        len(xref["matched_blocked_domains"]) +
        len(xref["matched_blocked_urls"]) +
        len(xref["matched_blocked_channels"])
    )

    channel_data["cross_reference"] = xref
    return channel_data


# ---------------------------------------------------------------------------
# Main collection pipeline
# ---------------------------------------------------------------------------

async def run_collection(args: argparse.Namespace) -> None:
    """Run the full data collection pipeline.

    Args:
        args: Parsed CLI arguments.
    """
    progress = _load_progress() if args.resume else {"completed_channels": [], "step": 0}

    logger.info("=" * 60)
    logger.info("  CyberLens — Training Data Collection Pipeline")
    logger.info("  Resume mode: %s", args.resume)
    logger.info("=" * 60)

    # ── Step 1: Load / generate labeled channels ─────────────
    logger.info("Step 1: Loading labeled channels...")
    from src.data_collection.known_scam_channels import (
        LABELED_CHANNELS,
        save_labeled_channels,
    )
    save_labeled_channels(str(LABELED_CHANNELS_PATH))
    logger.info("  -> %d labeled channels loaded", len(LABELED_CHANNELS))

    # ── Step 2: Collect ChannelDataset for each labeled channel
    channel_datasets: List[Dict[str, Any]] = []
    completed = set(progress.get("completed_channels", []))

    if not args.skip_telegram:
        logger.info("Step 2: Collecting Telegram channel datasets...")
        from src.data_collection.telegram_collector import TelegramDataCollector

        collector = TelegramDataCollector(message_limit=args.message_limit)

        if collector.is_available:
            channels_to_collect = [
                ch for ch in LABELED_CHANNELS
                if ch["channel"] not in completed
            ]
            total = len(channels_to_collect)

            for i, ch_info in enumerate(channels_to_collect, 1):
                channel = ch_info["channel"]
                label = ch_info["label"]

                logger.info(
                    "  [%d/%d] Collecting @%s (%s)...",
                    i, total, channel, label,
                )

                try:
                    dataset = await collector.collect_channel(channel)
                    ds_dict = dataset.to_dict()
                    ds_dict["ground_truth_label"] = label
                    ds_dict["ground_truth_category"] = ch_info.get("category", "")
                    ds_dict["ground_truth_source"] = ch_info.get("source", "")
                    channel_datasets.append(ds_dict)

                    completed.add(channel)
                    progress["completed_channels"] = list(completed)
                    _save_progress(progress)

                except Exception as e:
                    logger.error("  Failed to collect @%s: %s", channel, e)

        else:
            logger.warning(
                "  Telegram collector not available — "
                "creating placeholder entries from seed list"
            )
            for ch_info in LABELED_CHANNELS:
                channel_datasets.append({
                    "channel_metadata": {"username": ch_info["channel"]},
                    "posts": [],
                    "ground_truth_label": ch_info["label"],
                    "ground_truth_category": ch_info.get("category", ""),
                    "ground_truth_source": ch_info.get("source", ""),
                    "data_source": "seed_list_only",
                })
    else:
        logger.info("Step 2: SKIPPED (--skip-telegram)")
        for ch_info in LABELED_CHANNELS:
            channel_datasets.append({
                "channel_metadata": {"username": ch_info["channel"]},
                "posts": [],
                "ground_truth_label": ch_info["label"],
                "ground_truth_category": ch_info.get("category", ""),
                "ground_truth_source": ch_info.get("source", ""),
                "data_source": "seed_list_only",
            })

    # ── Step 3: Scrape I4C advisories and CERT-In alerts ─────
    logger.info("Step 3: Scraping I4C advisories and CERT-In alerts...")

    if not args.skip_scrapers:
        from src.data_collection.i4c_advisory_scraper import I4CAdvisoryScraper
        from src.data_collection.certin_scraper import CERTInScraper

        # I4C
        i4c = I4CAdvisoryScraper(output_path=str(I4C_ADVISORIES_PATH))
        if i4c.is_available:
            try:
                advisories = await i4c.scrape_advisories()
                logger.info("  -> %d I4C advisories collected", len(advisories))
            except Exception as e:
                logger.warning("  I4C scraper failed (Windows Playwright issue): %s", type(e).__name__)
        else:
            logger.warning("  I4C scraper not available (Playwright missing)")

        # CERT-In
        certin = CERTInScraper(output_path=str(CERTIN_ALERTS_PATH))
        if certin.is_available:
            try:
                alerts = await certin.scrape_alerts()
                logger.info("  -> %d CERT-In alerts collected", len(alerts))
            except Exception as e:
                logger.warning("  CERT-In scraper failed (Windows Playwright issue): %s", type(e).__name__)
        else:
            logger.warning("  CERT-In scraper not available (Playwright missing)")
    else:
        logger.info("Step 3: SKIPPED (--skip-scrapers)")

    # ── Step 4: Cross-reference entities ─────────────────────
    logger.info("Step 4: Cross-referencing entities against confirmed lists...")
    blocked = _build_blocked_entity_set(I4C_ADVISORIES_PATH, CERTIN_ALERTS_PATH)

    for ds in channel_datasets:
        _cross_reference_channel(ds, blocked)

    matched_count = sum(
        1 for ds in channel_datasets
        if ds.get("cross_reference", {}).get("blocked_entity_count", 0) > 0
    )
    logger.info("  -> %d channels have matched blocked entities", matched_count)

    # ── Step 5: Save unified dataset ─────────────────────────
    logger.info("Step 5: Saving unified training dataset...")
    TRAINING_DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)

    unified = {
        "metadata": {
            "version": "5.0",
            "total_channels": len(channel_datasets),
            "scam_channels": sum(
                1 for d in channel_datasets
                if d.get("ground_truth_label") == "CONFIRMED_SCAM"
            ),
            "legitimate_channels": sum(
                1 for d in channel_datasets
                if d.get("ground_truth_label") == "CONFIRMED_LEGITIMATE"
            ),
            "blocked_entities": {
                k: len(v) for k, v in blocked.items()
            },
        },
        "channels": channel_datasets,
    }

    with open(TRAINING_DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(unified, f, ensure_ascii=False, indent=2)

    logger.info("  -> Saved to %s", TRAINING_DATASET_PATH)

    # Clean up progress file
    if PROGRESS_PATH.exists():
        PROGRESS_PATH.unlink()

    logger.info("=" * 60)
    logger.info("  Collection complete!")
    logger.info("  Total channels: %d", len(channel_datasets))
    logger.info("  Dataset: %s", TRAINING_DATASET_PATH)
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="CyberLens — Collect real training data from public sources",
    )
    parser.add_argument(
        "--skip-telegram", action="store_true",
        help="Skip Telegram channel collection (use seed list only)",
    )
    parser.add_argument(
        "--skip-scrapers", action="store_true",
        help="Skip I4C and CERT-In scraping",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from last progress checkpoint",
    )
    parser.add_argument(
        "--message-limit", type=int, default=500,
        help="Max messages to collect per channel (default: 500)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Windows event loop fix
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run_collection(args))
