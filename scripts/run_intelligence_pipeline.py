#!/usr/bin/env python3
"""
CyberLens -- Intelligence Pipeline Runner
=============================================
Runs the redesigned 4-layer intelligence framework on the
collected dataset and produces structured recommendations.

Pipeline:
    1. Load channel data
    2. Collect evidence (Layer 1)
    3. Compute confidence (Layer 3)
    4. Generate recommendations (Layer 4)
    5. Run attribution on top pairs (Layer 2)
    6. Save results + store in feedback DB

Usage:
    python scripts/run_intelligence_pipeline.py
    python scripts/run_intelligence_pipeline.py --attribution

Author: CyberLens Team
"""

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "intelligence_pipeline.log"),
    ],
)
logger = logging.getLogger("cyberlens.pipeline")


def main(args):
    logger.info("=" * 70)
    logger.info("  CyberLens -- Intelligence Pipeline (Redesigned)")
    logger.info("  Evidence -> Confidence -> Recommendation -> Feedback")
    logger.info("=" * 70)

    # Load dataset
    dataset_path = PROJECT_ROOT / "data" / "processed" / "training_dataset.json"
    if not dataset_path.exists():
        logger.error("Dataset not found: %s", dataset_path)
        logger.error("Run: python scripts/collect_training_data.py --skip-telegram --skip-scrapers")
        sys.exit(1)

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    channels = data.get("channels", [])
    logger.info("Loaded %d channels from %s", len(channels), dataset_path)

    if not channels:
        logger.error("No channels in dataset")
        sys.exit(1)

    # -------------------------------------------------------------------
    # Layer 1 + 3 + 4: Evidence -> Confidence -> Recommendation
    # -------------------------------------------------------------------
    logger.info("-" * 70)
    logger.info("  Running recommendation engine...")
    logger.info("-" * 70)

    from src.intelligence.recommendation_engine import RecommendationEngine
    engine = RecommendationEngine()
    recommendations = engine.recommend_batch(channels)

    # Print summary table
    print("\n" + "=" * 90)
    print("  CyberLens v6.0 -- Intelligence Recommendations")
    print("=" * 90)
    print(f"  {'Channel':<35} {'Action':<25} {'Strength':<15} {'Confidence':<12}")
    print("-" * 90)

    for rec in recommendations:
        name = rec.channel_name[:34]
        action = rec.action
        if rec.suppressed:
            action = f"SUPPRESSED ({rec.suppression_reason[:30]}...)"
        print(f"  {name:<35} {action:<25} {rec.evidence_strength:<15} {rec.recommendation_confidence:<12}")

    print("=" * 90)

    # Action summary
    action_counts = {}
    for rec in recommendations:
        a = rec.action
        action_counts[a] = action_counts.get(a, 0) + 1

    print("\n  Action Summary:")
    for action, count in sorted(action_counts.items()):
        print(f"    {action}: {count}")

    # Suppression summary
    suppressed = [r for r in recommendations if r.suppressed]
    if suppressed:
        print(f"\n  Suppressed: {len(suppressed)} recommendations withheld (false positive prevention)")
    else:
        print(f"\n  Suppressed: 0 (no recommendations withheld)")
    print()

    # -------------------------------------------------------------------
    # Save recommendations
    # -------------------------------------------------------------------
    engine.save_recommendations(recommendations)
    logger.info("Recommendations saved to reports/recommendations/latest.json")

    # -------------------------------------------------------------------
    # Store in feedback DB
    # -------------------------------------------------------------------
    from src.intelligence.feedback_store import FeedbackStore
    feedback = FeedbackStore()
    for rec in recommendations:
        feedback.record_recommendation(rec.to_dict())
    logger.info("All recommendations stored in feedback database")

    summary = feedback.get_accuracy_summary()
    logger.info("Feedback DB: %d total records", summary["total_recommendations"])

    # -------------------------------------------------------------------
    # Layer 2: Attribution (optional, pairwise)
    # -------------------------------------------------------------------
    if args.attribution:
        logger.info("-" * 70)
        logger.info("  Running attribution engine...")
        logger.info("-" * 70)

        from src.intelligence.attribution_engine import AttributionEngine
        from src.intelligence.evidence_collector import EvidenceCollector

        collector = EvidenceCollector()
        assessments = collector.assess_batch(channels)
        attrib_engine = AttributionEngine()

        # Only compute for pairs above 0.2 threshold (skip obviously unrelated)
        results = attrib_engine.compute_all_pairs(assessments, min_probability=0.2)

        print("\n" + "=" * 90)
        print("  Operator Attribution Results (P > 0.2)")
        print("=" * 90)
        print(f"  {'Channel A':<25} {'Channel B':<25} {'P(same_op)':<12} {'Strength':<15}")
        print("-" * 90)

        for ar in results[:20]:  # top 20
            print(f"  {ar.channel_a:<25} {ar.channel_b:<25} {ar.probability_same_operator:<12.4f} {ar.attribution_strength:<15}")

        print("=" * 90)

        if not results:
            print("  No channel pairs above attribution threshold.\n")

        # Save attribution results
        attrib_path = PROJECT_ROOT / "reports" / "recommendations" / "attribution_results.json"
        attrib_path.parent.mkdir(parents=True, exist_ok=True)
        with open(attrib_path, "w") as f:
            json.dump(
                [r.to_dict() for r in results],
                f, indent=2, default=str,
            )
        logger.info("Attribution results saved -> %s", attrib_path)

    # -------------------------------------------------------------------
    # Print a detailed example
    # -------------------------------------------------------------------
    if recommendations:
        # Find first non-NO_ACTION recommendation
        interesting = next(
            (r for r in recommendations if r.action not in ("NO_ACTION", "SUPPRESSED")),
            recommendations[0],
        )
        print("\n" + "=" * 90)
        print(f"  Detailed Recommendation: @{interesting.channel_name}")
        print("=" * 90)
        print(f"  Action:          {interesting.action}")
        print(f"  Urgency:         {interesting.urgency}")
        print(f"  Strength:        {interesting.evidence_strength}")
        print(f"  Confidence:      {interesting.recommendation_confidence}")
        print(f"  Justification:   {interesting.primary_justification}")
        if interesting.caveats:
            print(f"  Caveats:")
            for caveat in interesting.caveats:
                print(f"    - {caveat}")
        if interesting.applicable_sections:
            print(f"  Legal Sections:")
            for section in interesting.applicable_sections[:3]:
                print(f"    - {section}")
        print(f"\n  Analyst Instructions:")
        print(f"    {interesting.analyst_instructions}")
        if interesting.suppressed:
            print(f"\n  SUPPRESSED: {interesting.suppression_reason}")
        print("=" * 90)
        print()

    logger.info("=" * 70)
    logger.info("  Intelligence pipeline complete!")
    logger.info("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CyberLens Intelligence Pipeline")
    parser.add_argument("--attribution", action="store_true",
                        help="Run pairwise operator attribution (slow for large datasets)")
    main(parser.parse_args())
