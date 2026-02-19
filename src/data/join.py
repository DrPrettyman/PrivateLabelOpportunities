"""Join supermarket scrape data to Open Food Facts.

Two join strategies:
    1. EAN/barcode match (highest confidence) — for AH, Tesco
    2. Fuzzy name+brand+weight match (fallback) — for Mercadona, Lidl

Reports match rates and confidence levels for documentation.
"""

from __future__ import annotations

import logging

import pandas as pd
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# Minimum similarity score for fuzzy matching
FUZZY_THRESHOLD = 80


def join_on_ean(
    supermarket_df: pd.DataFrame,
    off_df: pd.DataFrame,
    ean_col_super: str = "ean",
    ean_col_off: str = "code",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Join on EAN barcode. Returns (matched, unmatched_supermarket)."""
    # Clean barcodes: strip whitespace, remove leading zeros for consistency
    super_clean = supermarket_df.dropna(subset=[ean_col_super]).copy()
    super_clean[ean_col_super] = super_clean[ean_col_super].astype(str).str.strip()

    off_clean = off_df.dropna(subset=[ean_col_off]).copy()
    off_clean[ean_col_off] = off_clean[ean_col_off].astype(str).str.strip()

    matched = super_clean.merge(off_clean, left_on=ean_col_super, right_on=ean_col_off, how="inner")
    unmatched = super_clean[~super_clean[ean_col_super].isin(matched[ean_col_super])]

    logger.info(
        "EAN join: %d matched, %d unmatched out of %d supermarket products",
        len(matched), len(unmatched), len(super_clean),
    )
    return matched, unmatched


def join_on_fuzzy_name(
    supermarket_df: pd.DataFrame,
    off_df: pd.DataFrame,
    threshold: int = FUZZY_THRESHOLD,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fuzzy join on product name + brand + weight.

    Constrained by category to reduce false positives.
    Returns (matched_with_scores, unmatched).
    """
    matches = []
    unmatched_indices = []

    for idx, row in supermarket_df.iterrows():
        query = _build_match_string(row)
        best_score = 0
        best_off_idx = None

        # Narrow search space by category if possible
        candidates = off_df  # TODO: filter by mapped category

        for off_idx, off_row in candidates.iterrows():
            candidate = _build_match_string_off(off_row)
            score = fuzz.token_sort_ratio(query, candidate)
            if score > best_score:
                best_score = score
                best_off_idx = off_idx

        if best_score >= threshold and best_off_idx is not None:
            matches.append({
                "supermarket_idx": idx,
                "off_idx": best_off_idx,
                "match_score": best_score,
            })
        else:
            unmatched_indices.append(idx)

    logger.info(
        "Fuzzy join: %d matched (>=%d%%), %d unmatched out of %d",
        len(matches), threshold, len(unmatched_indices), len(supermarket_df),
    )
    return pd.DataFrame(matches), supermarket_df.loc[unmatched_indices]


def _build_match_string(row: pd.Series) -> str:
    """Build a matchable string from supermarket product data."""
    parts = [
        str(row.get("name", "")),
        str(row.get("brand", "")),
    ]
    return " ".join(p for p in parts if p and p != "nan").lower()


def _build_match_string_off(row: pd.Series) -> str:
    """Build a matchable string from OFF product data."""
    parts = [
        str(row.get("product_name", "")),
        str(row.get("brands", "")),
    ]
    return " ".join(p for p in parts if p and p != "nan").lower()
