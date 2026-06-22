"""
CyberLens — Data Collection Pipeline
========================================
Real-data collectors for training the CyberLens intelligence system.

Modules:
    telegram_collector  — Collect public Telegram channel datasets
    i4c_advisory_scraper — Scrape I4C public advisories (ground truth)
    certin_scraper       — Scrape CERT-In public alerts (ground truth)
    known_scam_channels  — Hardcoded seed list of confirmed scam / legit channels

Author: CyberLens Team — GPCSSI Internship
"""

from src.data_collection.known_scam_channels import LABELED_CHANNELS
from src.data_collection.telegram_collector import TelegramDataCollector
from src.data_collection.i4c_advisory_scraper import I4CAdvisoryScraper
from src.data_collection.certin_scraper import CERTInScraper

__all__ = [
    "TelegramDataCollector",
    "I4CAdvisoryScraper",
    "CERTInScraper",
    "LABELED_CHANNELS",
]

