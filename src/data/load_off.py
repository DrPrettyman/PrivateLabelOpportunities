"""Load and parse the Open Food Facts bulk database.

The pre-filtered EU Parquet file is created by scripts/download_off.py,
which uses DuckDB to stream-filter the remote OFF dump and extract
nutrients from the nested struct into flat columns.

Expected columns after download:
    code, product_name, brands, brands_tags, categories_tags,
    countries_tags, nutriscore_grade, nutriscore_score, nova_group,
    labels_tags, stores_tags, quantity, product_quantity,
    unique_scans_n, energy_kcal_100g, fat_100g, saturated_fat_100g,
    sugars_100g, salt_100g, fiber_100g, proteins_100g,
    carbohydrates_100g, sodium_100g
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Default path for the pre-filtered EU data
DEFAULT_PATH = Path("data/raw/off_eu.parquet")


def load_off_eu(path: Path | None = None) -> pd.DataFrame:
    """Load the pre-filtered EU Open Food Facts Parquet file.

    This file is produced by scripts/download_off.py and contains
    only EU-country products with nutrients already extracted into
    flat columns.

    Args:
        path: Path to the off_eu.parquet file.

    Returns:
        DataFrame ready for cleaning and analysis.
    """
    path = path or DEFAULT_PATH

    logger.info("Loading Open Food Facts EU data from %s", path)
    df = pd.read_parquet(path)

    logger.info("Loaded %d products, %d columns", len(df), len(df.columns))
    logger.info("Columns: %s", list(df.columns))

    # Basic type coercion
    if "nutriscore_grade" in df.columns:
        df["nutriscore_grade"] = df["nutriscore_grade"].astype(str).str.lower().str.strip()
        df.loc[df["nutriscore_grade"].isin(["", "nan", "none", "unknown"]), "nutriscore_grade"] = pd.NA

    if "nova_group" in df.columns:
        df["nova_group"] = pd.to_numeric(df["nova_group"], errors="coerce")

    if "code" in df.columns:
        df["code"] = df["code"].astype(str).str.strip()

    return df


def profile_off(df: pd.DataFrame) -> dict:
    """Generate a data quality profile of the OFF dataset.

    Returns dict with key metrics for the data quality report.
    """
    total = len(df)
    profile = {
        "total_products": total,
        "columns": list(df.columns),
    }

    # Missing value rates for key fields
    key_fields = [
        "product_name", "brands", "categories_tags", "nutriscore_grade",
        "nova_group", "energy_kcal_100g", "sugars_100g", "salt_100g",
        "saturated_fat_100g", "fiber_100g", "proteins_100g", "code",
    ]
    for field in key_fields:
        if field in df.columns:
            missing = df[field].isna().sum()
            profile[f"missing_{field}"] = missing
            profile[f"missing_{field}_pct"] = round(missing / total * 100, 1)

    # Nutri-Score distribution
    if "nutriscore_grade" in df.columns:
        ns_dist = df["nutriscore_grade"].dropna().value_counts().to_dict()
        profile["nutriscore_distribution"] = ns_dist
        profile["nutriscore_coverage_pct"] = round(
            df["nutriscore_grade"].notna().sum() / total * 100, 1
        )

    # NOVA distribution
    if "nova_group" in df.columns:
        nova_dist = df["nova_group"].dropna().value_counts().to_dict()
        profile["nova_distribution"] = nova_dist
        profile["nova_coverage_pct"] = round(
            df["nova_group"].notna().sum() / total * 100, 1
        )

    # Country distribution (top 10)
    if "countries_tags" in df.columns:
        # countries_tags is a list column from Parquet
        countries = df["countries_tags"].dropna().explode().value_counts().head(10)
        profile["top_countries"] = countries.to_dict()

    return profile
