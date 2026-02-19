"""Load and parse the Open Food Facts bulk database.

Handles downloading, filtering to EU countries, and initial parsing of
the ~3M product Parquet/CSV dump from Open Food Facts.

Key fields extracted:
    - product_name, brands, categories_tags, countries_tags
    - nutriscore_grade (A-E), nova_group (1-4)
    - nutriments (energy, fat, saturated fat, sugars, salt, fibre, protein per 100g)
    - labels_tags (organic, vegan, gluten-free, etc.)
    - stores_tags, manufacturing_places_tags, code (EAN barcode)
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# EU countries to filter on (ISO 2-letter codes used in OFF tags)
EU_COUNTRIES = {
    "fr", "de", "es", "it", "nl", "be", "pt", "at", "ie", "gr",
    "pl", "se", "dk", "fi", "cz", "ro", "hu", "bg", "hr", "sk",
    "si", "lt", "lv", "ee", "lu", "mt", "cy",
}

# Columns we actually need from the bulk download
KEEP_COLUMNS = [
    "code",
    "product_name",
    "brands",
    "categories_tags",
    "countries_tags",
    "nutriscore_grade",
    "nova_group",
    "energy-kcal_100g",
    "fat_100g",
    "saturated-fat_100g",
    "sugars_100g",
    "salt_100g",
    "fiber_100g",
    "proteins_100g",
    "labels_tags",
    "stores_tags",
    "manufacturing_places_tags",
]


def load_off_parquet(
    path: Path,
    countries: set[str] | None = None,
) -> pd.DataFrame:
    """Load Open Food Facts Parquet dump and filter to specified countries.

    Args:
        path: Path to the OFF .parquet file.
        countries: Set of country codes to keep. Defaults to EU_COUNTRIES.

    Returns:
        Filtered DataFrame with standardised column names.
    """
    countries = countries or EU_COUNTRIES

    logger.info("Loading Open Food Facts from %s", path)
    df = pd.read_parquet(path, columns=[c for c in KEEP_COLUMNS if c != "code"] + ["code"])

    initial_count = len(df)
    logger.info("Loaded %d products total", initial_count)

    # Filter to products available in target countries
    df = _filter_countries(df, countries)
    logger.info("Filtered to %d products in %d EU countries", len(df), len(countries))

    return df


def _filter_countries(df: pd.DataFrame, countries: set[str]) -> pd.DataFrame:
    """Keep rows where countries_tags contains at least one target country."""
    mask = df["countries_tags"].fillna("").apply(
        lambda tags: any(
            f"en:{c}" in tags or c in tags
            for c in countries
        )
    )
    return df[mask].copy()
