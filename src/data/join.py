"""Join supermarket scrape data to Open Food Facts.

Two join strategies:
    1. EAN/barcode match (highest confidence) — used when EAN available
    2. Fuzzy name+brand match (fallback) — for Mercadona, AH

Performance: country-filtered candidate pools + rapidfuzz batch matching
keep the fuzzy join tractable (3K products × 10K candidates ≈ 30M comparisons).

Reports match rates and confidence levels for documentation.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

# Minimum similarity score for fuzzy matching
FUZZY_THRESHOLD = 75

# Country tag mapping for pre-filtering OFF candidates
RETAILER_COUNTRY_TAGS = {
    "mercadona": "en:spain",
    "albert_heijn": "en:netherlands",
    "carrefour": "en:france",
}


def join_on_ean(
    supermarket_df: pd.DataFrame,
    off_df: pd.DataFrame,
    ean_col_super: str = "ean",
    ean_col_off: str = "code",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Join on EAN barcode. Returns (matched, unmatched_supermarket)."""
    super_clean = supermarket_df.dropna(subset=[ean_col_super]).copy()
    super_clean[ean_col_super] = super_clean[ean_col_super].astype(str).str.strip()

    off_clean = off_df.dropna(subset=[ean_col_off]).copy()
    off_clean[ean_col_off] = off_clean[ean_col_off].astype(str).str.strip()

    matched = super_clean.merge(
        off_clean, left_on=ean_col_super, right_on=ean_col_off,
        how="inner", suffixes=("", "_off"),
    )
    unmatched = super_clean[~super_clean[ean_col_super].isin(matched[ean_col_super])]

    logger.info(
        "EAN join: %d matched, %d unmatched out of %d supermarket products",
        len(matched), len(unmatched), len(super_clean),
    )
    return matched, unmatched


def _build_match_key(name: str, brand: str) -> str:
    """Build a normalised string for fuzzy matching."""
    parts = []
    if isinstance(name, str) and name.strip():
        parts.append(name.strip().lower())
    if isinstance(brand, str) and brand.strip():
        parts.append(brand.strip().lower())
    return " ".join(parts)


def join_on_fuzzy_name(
    supermarket_df: pd.DataFrame,
    off_df: pd.DataFrame,
    retailer: str,
    threshold: int = FUZZY_THRESHOLD,
    max_off_candidates: int = 50_000,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fuzzy join supermarket products to OFF using name+brand matching.

    Pre-filters OFF to the retailer's country to keep the search space
    manageable, then uses rapidfuzz for batch matching.

    Returns (matched_df, unmatched_supermarket_df).
    matched_df contains supermarket columns + OFF columns (suffixed _off)
    + match_score column.
    """
    # Pre-filter OFF to retailer's country
    country_tag = RETAILER_COUNTRY_TAGS.get(retailer)
    if country_tag and "countries_tags" in off_df.columns:
        mask = off_df["countries_tags"].apply(
            lambda tags: country_tag in list(tags) if isinstance(tags, (list, np.ndarray)) else False
        )
        off_candidates = off_df[mask].copy()
        logger.info(
            "Filtered OFF to %s: %d candidates (from %d total)",
            country_tag, len(off_candidates), len(off_df),
        )
    else:
        off_candidates = off_df.copy()

    # Further limit if still too large (take products with brands first)
    if len(off_candidates) > max_off_candidates:
        has_brand = off_candidates["brands"].notna() & (off_candidates["brands"] != "")
        branded = off_candidates[has_brand]
        if len(branded) > max_off_candidates:
            off_candidates = branded.head(max_off_candidates)
        else:
            off_candidates = branded
        logger.info("Capped OFF candidates to %d (branded products)", len(off_candidates))

    # Build match keys
    super_keys = supermarket_df.apply(
        lambda r: _build_match_key(r.get("name", ""), r.get("brand", "")), axis=1
    ).tolist()

    off_keys = off_candidates.apply(
        lambda r: _build_match_key(r.get("product_name", ""), r.get("brands", "")), axis=1
    ).tolist()

    logger.info(
        "Starting fuzzy matching: %d supermarket × %d OFF candidates",
        len(super_keys), len(off_keys),
    )

    # Batch fuzzy matching using rapidfuzz
    matched_rows = []
    unmatched_indices = []
    off_idx_list = off_candidates.index.tolist()

    for i, query in enumerate(super_keys):
        if not query.strip():
            unmatched_indices.append(supermarket_df.index[i])
            continue

        result = process.extractOne(
            query, off_keys,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=threshold,
        )

        if result is not None:
            match_text, score, match_idx = result
            matched_rows.append({
                "super_idx": supermarket_df.index[i],
                "off_idx": off_idx_list[match_idx],
                "match_score": score,
            })
        else:
            unmatched_indices.append(supermarket_df.index[i])

        if (i + 1) % 1000 == 0:
            logger.info("  Matched %d/%d (%.0f%%)", i + 1, len(super_keys), (i + 1) / len(super_keys) * 100)

    logger.info(
        "Fuzzy join: %d matched (>=%d%%), %d unmatched out of %d",
        len(matched_rows), threshold, len(unmatched_indices), len(supermarket_df),
    )

    if not matched_rows:
        return pd.DataFrame(), supermarket_df

    # Build matched DataFrame
    match_info = pd.DataFrame(matched_rows)
    matched_super = supermarket_df.loc[match_info["super_idx"]].reset_index(drop=True)
    matched_off = off_candidates.loc[match_info["off_idx"]].reset_index(drop=True)

    # Add OFF columns with suffix
    for col in matched_off.columns:
        matched_super[f"{col}_off"] = matched_off[col].values

    matched_super["match_score"] = match_info["match_score"].values
    unmatched = supermarket_df.loc[unmatched_indices]

    return matched_super, unmatched


def join_supermarket_to_off(
    supermarket_df: pd.DataFrame,
    off_df: pd.DataFrame,
    retailer: str,
    threshold: int = FUZZY_THRESHOLD,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Main entry point: try EAN join first, then fuzzy for remainder.

    Returns (matched, unmatched).
    """
    has_ean = (
        "ean" in supermarket_df.columns
        and supermarket_df["ean"].notna().any()
    )

    if has_ean:
        logger.info("Attempting EAN join first...")
        ean_matched, ean_unmatched = join_on_ean(supermarket_df, off_df)

        if len(ean_unmatched) > 0:
            logger.info("Falling back to fuzzy join for %d unmatched products", len(ean_unmatched))
            fuzzy_matched, still_unmatched = join_on_fuzzy_name(
                ean_unmatched, off_df, retailer=retailer, threshold=threshold,
            )
            matched = pd.concat([ean_matched, fuzzy_matched], ignore_index=True)
            return matched, still_unmatched
        return ean_matched, ean_unmatched
    else:
        logger.info("No EAN available, using fuzzy join only")
        return join_on_fuzzy_name(
            supermarket_df, off_df, retailer=retailer, threshold=threshold,
        )
