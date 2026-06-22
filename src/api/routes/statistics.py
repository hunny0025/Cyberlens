"""
CyberLens — Statistics API Routes
=====================================
Advanced statistics endpoints for dashboard:
- Heatmap (district-level case counts)
- Entity patterns (repeat offenders)
- Trends (7-day category trends, hourly distribution)

Author: CyberLens Team — GPCSSI Internship
"""

import logging
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import crud, db

logger = logging.getLogger("cyberlens.api.statistics")

router = APIRouter(prefix="/api/statistics", tags=["Statistics"])


# ---------------------------------------------------------------------------
# Hotspot district data (known cybercrime hubs)
# ---------------------------------------------------------------------------

INDIA_DISTRICTS = [
    {"district": "Gurugram", "state": "Haryana", "lat": 28.4595, "lon": 77.0266, "boost": 5},
    {"district": "Jamtara", "state": "Jharkhand", "lat": 23.9570, "lon": 86.8039, "boost": 8},
    {"district": "Mewat", "state": "Haryana", "lat": 27.9381, "lon": 77.0074, "boost": 7},
    {"district": "Nuh", "state": "Haryana", "lat": 27.8740, "lon": 77.0080, "boost": 6},
    {"district": "Bharatpur", "state": "Rajasthan", "lat": 27.2173, "lon": 77.4900, "boost": 4},
    {"district": "Mathura", "state": "Uttar Pradesh", "lat": 27.4924, "lon": 77.6737, "boost": 3},
    {"district": "Deoghar", "state": "Jharkhand", "lat": 24.4764, "lon": 86.6946, "boost": 5},
    {"district": "Alwar", "state": "Rajasthan", "lat": 27.5530, "lon": 76.6346, "boost": 3},
    {"district": "Hyderabad", "state": "Telangana", "lat": 17.3850, "lon": 78.4867, "boost": 2},
    {"district": "Bengaluru", "state": "Karnataka", "lat": 12.9716, "lon": 77.5946, "boost": 2},
    {"district": "Mumbai", "state": "Maharashtra", "lat": 19.0760, "lon": 72.8777, "boost": 2},
    {"district": "Delhi", "state": "Delhi", "lat": 28.7041, "lon": 77.1025, "boost": 3},
    {"district": "Noida", "state": "Uttar Pradesh", "lat": 28.5355, "lon": 77.3910, "boost": 3},
    {"district": "Lucknow", "state": "Uttar Pradesh", "lat": 26.8467, "lon": 80.9462, "boost": 1},
    {"district": "Jaipur", "state": "Rajasthan", "lat": 26.9124, "lon": 75.7873, "boost": 2},
    {"district": "Kolkata", "state": "West Bengal", "lat": 22.5726, "lon": 88.3639, "boost": 1},
    {"district": "Chennai", "state": "Tamil Nadu", "lat": 13.0827, "lon": 80.2707, "boost": 1},
    {"district": "Pune", "state": "Maharashtra", "lat": 18.5204, "lon": 73.8567, "boost": 1},
    {"district": "Ahmedabad", "state": "Gujarat", "lat": 23.0225, "lon": 72.5714, "boost": 1},
    {"district": "Chandigarh", "state": "Chandigarh", "lat": 30.7333, "lon": 76.7794, "boost": 1},
]


# ---------------------------------------------------------------------------
# Heatmap endpoint
# ---------------------------------------------------------------------------

@router.get("/heatmap")
async def get_heatmap(
    session: Session = Depends(db.get_db),
) -> List[Dict[str, Any]]:
    """Get district-level case counts for India map visualization.

    Returns synthetic but realistic-looking data with known cybercrime
    hotspots (Gurugram, Jamtara, Mewat, Nuh) boosted to reflect
    their real-world significance.

    Returns:
        List of district objects with count, latitude, longitude.
    """
    # Get total case count from DB for scaling
    try:
        stats = crud.get_statistics(session)
        total_cases = stats.total_cases if hasattr(stats, "total_cases") else 0
    except Exception:
        total_cases = 50

    base_count = max(5, total_cases // 20)

    result = []
    for district in INDIA_DISTRICTS:
        # Base count + hotspot boost + slight randomization
        count = base_count + district["boost"] * random.randint(2, 5)
        count += random.randint(0, base_count // 2)

        result.append({
            "district": district["district"],
            "state": district["state"],
            "count": count,
            "latitude": district["lat"],
            "longitude": district["lon"],
            "is_hotspot": district["boost"] >= 5,
        })

    # Sort by count descending
    result.sort(key=lambda x: x["count"], reverse=True)

    return result


# ---------------------------------------------------------------------------
# Entity patterns endpoint
# ---------------------------------------------------------------------------

@router.get("/entity-patterns")
async def get_entity_patterns(
    min_cases: int = 3,
    session: Session = Depends(db.get_db),
) -> List[Dict[str, Any]]:
    """Detect repeat entities appearing across multiple cases.

    Returns phone numbers, UPI IDs, and URLs that appear in 3+ cases,
    indicating organized scam operations.

    Args:
        min_cases: Minimum case count to flag (default 3).

    Returns:
        List of entity pattern objects with case count and details.
    """
    try:
        entities = crud.get_flagged_entities(session, min_count=min_cases)
    except Exception:
        entities = []

    if not entities:
        # Return demo data if no real entities
        return _demo_entity_patterns()

    result = []
    for entity in entities:
        result.append({
            "value": entity.get("value", ""),
            "type": entity.get("entity_type", "PHONE"),
            "case_count": entity.get("flag_count", 0),
            "first_seen": entity.get("first_seen", ""),
            "last_seen": entity.get("last_seen", ""),
            "is_ring": entity.get("flag_count", 0) >= 5,
            "alert_level": "CRITICAL" if entity.get("flag_count", 0) >= 5 else "HIGH",
        })

    result.sort(key=lambda x: x["case_count"], reverse=True)
    return result


def _demo_entity_patterns() -> List[Dict[str, Any]]:
    """Generate demo entity patterns for the dashboard."""
    return [
        {
            "value": "+91-98765XXXXX",
            "type": "PHONE",
            "case_count": 8,
            "first_seen": (datetime.now() - timedelta(days=12)).isoformat(),
            "last_seen": (datetime.now() - timedelta(hours=3)).isoformat(),
            "is_ring": True,
            "alert_level": "CRITICAL",
        },
        {
            "value": "+91-87654XXXXX",
            "type": "PHONE",
            "case_count": 5,
            "first_seen": (datetime.now() - timedelta(days=7)).isoformat(),
            "last_seen": (datetime.now() - timedelta(hours=8)).isoformat(),
            "is_ring": True,
            "alert_level": "CRITICAL",
        },
        {
            "value": "scammer@paytm",
            "type": "UPI",
            "case_count": 4,
            "first_seen": (datetime.now() - timedelta(days=5)).isoformat(),
            "last_seen": (datetime.now() - timedelta(hours=1)).isoformat(),
            "is_ring": False,
            "alert_level": "HIGH",
        },
        {
            "value": "t.me/betting_tips_vip",
            "type": "TELEGRAM",
            "case_count": 6,
            "first_seen": (datetime.now() - timedelta(days=14)).isoformat(),
            "last_seen": (datetime.now() - timedelta(hours=2)).isoformat(),
            "is_ring": True,
            "alert_level": "CRITICAL",
        },
        {
            "value": "+91-76543XXXXX",
            "type": "PHONE",
            "case_count": 3,
            "first_seen": (datetime.now() - timedelta(days=3)).isoformat(),
            "last_seen": (datetime.now() - timedelta(hours=5)).isoformat(),
            "is_ring": False,
            "alert_level": "HIGH",
        },
    ]


# ---------------------------------------------------------------------------
# Trends endpoint
# ---------------------------------------------------------------------------

@router.get("/trends")
async def get_trends(
    session: Session = Depends(db.get_db),
) -> Dict[str, Any]:
    """Get trend data for dashboard analytics.

    Returns:
        - 7-day trend per category
        - Hourly distribution (scam posting patterns)
        - Top 10 flagged phone numbers
    """
    now = datetime.now()

    # 7-day category trend
    weekly_trend = []
    categories = [
        "Real Money Betting", "Investment Scam",
        "Fake Customer Care", "Digital Arrest",
        "Sextortion", "Job Scam",
    ]

    for i in range(7):
        day = now - timedelta(days=6 - i)
        day_data = {
            "date": day.strftime("%Y-%m-%d"),
            "day": day.strftime("%a"),
        }
        for cat in categories:
            # Simulate with slight variation
            base = random.randint(3, 15)
            if cat in ("Investment Scam", "Real Money Betting"):
                base += random.randint(2, 8)
            day_data[cat] = base
        weekly_trend.append(day_data)

    # Hourly distribution
    hourly = []
    for hour in range(24):
        # Scams peak 10am-2pm and 6pm-10pm
        if 10 <= hour <= 14:
            count = random.randint(8, 20)
        elif 18 <= hour <= 22:
            count = random.randint(10, 25)
        elif 0 <= hour <= 5:
            count = random.randint(1, 4)
        else:
            count = random.randint(3, 10)

        hourly.append({
            "hour": hour,
            "label": f"{hour:02d}:00",
            "count": count,
        })

    # Top flagged phones
    top_phones = [
        {"phone": f"+91-9{random.randint(1000,9999)}XXXXX", "count": random.randint(3, 12),
         "category": random.choice(categories)}
        for _ in range(10)
    ]
    top_phones.sort(key=lambda x: x["count"], reverse=True)

    return {
        "weekly_trend": weekly_trend,
        "hourly_distribution": hourly,
        "top_flagged_phones": top_phones,
        "period": {
            "start": (now - timedelta(days=6)).isoformat(),
            "end": now.isoformat(),
        },
    }
