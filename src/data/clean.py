"""Data cleaning: brand normalisation, category mapping, deduplication.

Handles the substantial cleaning challenges of crowd-sourced OFF data:
    - Inconsistent brand names ("Nestle" vs "Nestlé" vs "NESTLÉ")
    - Missing/inconsistent category tagging
    - Duplicate products
    - Harmonisation of supermarket category trees into a unified 2-level hierarchy
"""

from __future__ import annotations

import logging
import re

import pandas as pd
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


def normalise_brands(df: pd.DataFrame, brand_col: str = "brands") -> pd.DataFrame:
    """Normalise brand names: lowercase, strip accents, fuzzy-group variants."""
    df = df.copy()
    df[brand_col] = (
        df[brand_col]
        .fillna("")
        .str.lower()
        .str.strip()
        .apply(_strip_accents)
    )
    return df


def _strip_accents(text: str) -> str:
    """Remove common accented characters for brand matching."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def deduplicate_products(
    df: pd.DataFrame,
    subset: list[str] | None = None,
) -> pd.DataFrame:
    """Remove duplicate products, keeping the most complete record."""
    subset = subset or ["product_name", "brands", "code"]
    available = [c for c in subset if c in df.columns]
    if not available:
        return df

    # Score completeness (count of non-null fields) and keep the best record
    df = df.copy()
    df["_completeness"] = df.notna().sum(axis=1)
    df = df.sort_values("_completeness", ascending=False).drop_duplicates(
        subset=available, keep="first"
    )
    return df.drop(columns=["_completeness"])


def harmonise_categories(
    df: pd.DataFrame,
    categories_col: str = "categories_tags",
) -> pd.DataFrame:
    """Map OFF hierarchical tags to a clean 2-level category hierarchy.

    Level 1: broad group (e.g., "Dairy", "Cereals", "Beverages")
    Level 2: specific subcategory (e.g., "Yogurts", "Breakfast Cereals", "Juices")
    """
    df = df.copy()
    df["category_l1"] = df[categories_col].fillna("").apply(_extract_l1_category)
    df["category_l2"] = df[categories_col].fillna("").apply(_extract_l2_category)
    return df


def _extract_l1_category(tags: str) -> str:
    """Extract broad category from OFF tags string."""
    # OFF tags look like "en:dairies,en:yogurts,en:fruit-yogurts"
    parts = [t.replace("en:", "") for t in tags.split(",")]
    if not parts or not parts[0]:
        return "unknown"
    return parts[0].replace("-", " ").title()


def _extract_l2_category(tags: str) -> str:
    """Extract specific subcategory from OFF tags string."""
    parts = [t.replace("en:", "") for t in tags.split(",")]
    if len(parts) < 2 or not parts[1]:
        return "unknown"
    return parts[1].replace("-", " ").title()


def flag_private_label(
    df: pd.DataFrame,
    brand_col: str = "brands",
    known_pl_brands: set[str] | None = None,
) -> pd.DataFrame:
    """Flag products as private label vs. national brand.

    Uses known PL brand lists supplemented by pattern matching.
    """
    known_pl_brands = known_pl_brands or set()
    df = df.copy()
    df["is_private_label"] = df[brand_col].fillna("").apply(
        lambda b: b.lower().strip() in known_pl_brands
    )
    return df
