"""Build the unified analysis dataset.

Runs the full pipeline:
    1. Load and clean OFF EU data
    2. Compute missing Nutri-Scores
    3. Load supermarket scrapes
    4. Join supermarket data to OFF
    5. Save processed datasets

Usage:
    python scripts/build_dataset.py
"""

import logging
import time
from pathlib import Path

import pandas as pd

from src.data.load_off import load_off_eu
from src.data.clean import clean_off_pipeline
from src.data.nutriscore import compute_nutriscore_column
from src.data.join import join_supermarket_to_off

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/processed")
SCRAPED_DIR = Path("data/scraped")


def main():
    start = time.time()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Load and clean OFF ──────────────────────────────────
    logger.info("Step 1: Loading and cleaning OFF data...")
    df_off = load_off_eu()
    df_off = clean_off_pipeline(df_off)

    # ── Step 2: Compute missing Nutri-Scores ────────────────────────
    logger.info("Step 2: Computing missing Nutri-Scores...")
    df_off = compute_nutriscore_column(df_off)

    # Save cleaned OFF
    off_path = OUTPUT_DIR / "off_eu_clean.parquet"
    df_off.to_parquet(off_path, index=False)
    logger.info("Saved cleaned OFF: %s (%d products)", off_path, len(df_off))

    # ── Step 3: Load and join supermarket data ──────────────────────
    retailers = {
        "mercadona": SCRAPED_DIR / "mercadona_products.parquet",
        "albert_heijn": SCRAPED_DIR / "albert_heijn_products.parquet",
    }

    all_matched = []
    all_unmatched = []

    for retailer, path in retailers.items():
        if not path.exists():
            logger.warning("Skipping %s: %s not found", retailer, path)
            continue

        logger.info("Step 3: Joining %s to OFF...", retailer)
        df_super = pd.read_parquet(path)
        matched, unmatched = join_supermarket_to_off(df_super, df_off, retailer=retailer)

        all_matched.append(matched)
        all_unmatched.append(unmatched)

        logger.info(
            "  %s: %d matched, %d unmatched (%.1f%% match rate)",
            retailer, len(matched), len(unmatched),
            len(matched) / len(df_super) * 100 if len(df_super) > 0 else 0,
        )

    # ── Step 4: Save joined data ────────────────────────────────────
    if all_matched:
        df_matched = pd.concat(all_matched, ignore_index=True)
        matched_path = OUTPUT_DIR / "supermarket_off_matched.parquet"
        df_matched.to_parquet(matched_path, index=False)
        logger.info("Saved matched data: %s (%d products)", matched_path, len(df_matched))

    if all_unmatched:
        df_unmatched = pd.concat(all_unmatched, ignore_index=True)
        unmatched_path = OUTPUT_DIR / "supermarket_unmatched.parquet"
        df_unmatched.to_parquet(unmatched_path, index=False)
        logger.info("Saved unmatched data: %s (%d products)", unmatched_path, len(df_unmatched))

    # ── Step 5: Build combined supermarket dataset ──────────────────
    # All supermarket products (matched + unmatched) with their original data
    all_super = []
    for retailer, path in retailers.items():
        if path.exists():
            df = pd.read_parquet(path)
            all_super.append(df)

    if all_super:
        df_all_super = pd.concat(all_super, ignore_index=True)
        super_path = OUTPUT_DIR / "supermarket_all.parquet"
        df_all_super.to_parquet(super_path, index=False)
        logger.info("Saved all supermarket data: %s (%d products)", super_path, len(df_all_super))

    elapsed = time.time() - start
    logger.info("Pipeline complete in %.0fs", elapsed)

    # Summary
    print("\n" + "=" * 60)
    print("DATASET BUILD SUMMARY")
    print("=" * 60)
    print(f"OFF EU (cleaned):    {len(df_off):>10,} products")
    if all_matched:
        print(f"Supermarket matched: {len(df_matched):>10,} products")
    if all_unmatched:
        print(f"Supermarket unmatched: {len(df_unmatched):>8,} products")
    if all_super:
        print(f"Supermarket total:   {len(df_all_super):>10,} products")
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print(f"Time: {elapsed:.0f}s")


if __name__ == "__main__":
    main()
