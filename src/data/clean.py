"""Data cleaning: brand normalisation, category mapping, deduplication.

Handles the substantial cleaning challenges of crowd-sourced OFF data:
    - Inconsistent brand names ("Nestle" vs "Nestlé" vs "NESTLÉ")
    - Missing/inconsistent category tagging
    - Duplicate products (same EAN code)
    - Harmonisation of OFF tag hierarchies into a unified 2-level system
    - Private label detection across major EU retailers
"""

from __future__ import annotations

import logging
import re
import unicodedata

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Known private label brands across EU retailers ──────────────────────
# Maps normalised brand name -> retailer. Covers major EU grocery chains.
KNOWN_PL_BRANDS: dict[str, str] = {
    # Spain — Mercadona
    "hacendado": "mercadona", "deliplus": "mercadona", "bosque verde": "mercadona",
    "compy": "mercadona", "tododia": "mercadona", "solcare": "mercadona",
    "dermik": "mercadona", "cave": "mercadona", "belsia": "mercadona",
    "esencia": "mercadona", "casa juncal": "mercadona", "polesa": "mercadona",
    "quirus": "mercadona", "steinburg": "mercadona",
    # Spain — others
    "bonarea": "bonarea", "dia": "dia", "eroski": "eroski",
    "eroski basic": "eroski", "eroski sannia": "eroski",
    # Netherlands — Albert Heijn
    "albert heijn": "albert_heijn", "ah": "albert_heijn",
    "ah biologisch": "albert_heijn", "ah excellent": "albert_heijn",
    "ah terra": "albert_heijn", "ah basic": "albert_heijn",
    # Netherlands — Jumbo
    "jumbo": "jumbo",
    # France — Carrefour
    "carrefour": "carrefour", "carrefour bio": "carrefour",
    "carrefour classic": "carrefour", "carrefour extra": "carrefour",
    "carrefour discount": "carrefour", "carrefour veggie": "carrefour",
    "carrefour sensation": "carrefour", "carrefour selection": "carrefour",
    "carrefour baby": "carrefour", "reflets de france": "carrefour",
    "simpl": "carrefour",
    # France — Auchan
    "auchan": "auchan", "auchan bio": "auchan", "auchan gourmet": "auchan",
    "mmm!": "auchan", "pouce": "auchan",
    # France — Leclerc
    "marque repere": "leclerc", "eco+": "leclerc",
    # France — Casino / Leader Price
    "casino": "casino", "leader price": "leader_price",
    # France — U
    "u": "systeme_u", "u bio": "systeme_u", "u saveurs": "systeme_u",
    # France — Intermarche
    "paturages": "intermarche", "chabrior": "intermarche",
    "top budget": "intermarche",
    # Belgium — Delhaize / Colruyt
    "delhaize": "delhaize", "365": "delhaize", "boni": "colruyt",
    "boni selection": "colruyt", "everyday": "colruyt",
    # Germany — Lidl
    "lidl": "lidl", "milbona": "lidl", "cien": "lidl",
    "solevita": "lidl", "freeway": "lidl", "combino": "lidl",
    "italiamo": "lidl", "favorina": "lidl", "deluxe": "lidl",
    "biotrend": "lidl", "vitasia": "lidl", "crivit": "lidl",
    "silvercrest": "lidl",
    # Germany — Aldi
    "aldi": "aldi", "gut bio": "aldi", "grandessa": "aldi",
    "trader joe's": "aldi", "moser roth": "aldi", "specially selected": "aldi",
    "river queen": "aldi", "beaumont": "aldi",
    # Germany — others
    "ja!": "rewe", "rewe": "rewe", "rewe bio": "rewe", "rewe beste wahl": "rewe",
    "penny": "penny", "edeka": "edeka", "edeka bio": "edeka",
    "gut & gunstig": "edeka",
    # Italy — Coop
    "coop": "coop_it",
    # International — Spar
    "spar": "spar", "spar natural": "spar",
}

# Compile set for fast lookup
_PL_BRAND_SET = set(KNOWN_PL_BRANDS.keys())

# ── OFF L1 category mapping ────────────────────────────────────────────
# Maps the first en: tag to a clean broad food category.
# OFF's taxonomy uses en: prefixed slug tags.
_L1_TAG_MAP = {
    "plant-based-foods-and-beverages": "Plant-Based",
    "plant-based-foods": "Plant-Based",
    "dairies": "Dairy",
    "beverages": "Beverages",
    "meats-and-their-products": "Meat & Poultry",
    "meats": "Meat & Poultry",
    "cereals-and-potatoes": "Cereals & Grains",
    "cereals-and-their-products": "Cereals & Grains",
    "snacks": "Snacks",
    "sweet-snacks": "Snacks",
    "salty-snacks": "Snacks",
    "frozen-foods": "Frozen",
    "meals": "Prepared Meals",
    "prepared-meals": "Prepared Meals",
    "groceries": "Groceries",
    "condiments": "Condiments & Sauces",
    "sauces": "Condiments & Sauces",
    "fats": "Fats & Oils",
    "fats-and-oils": "Fats & Oils",
    "seafood": "Seafood",
    "fishes": "Seafood",
    "breakfasts": "Breakfast",
    "spreads": "Spreads",
    "baby-foods": "Baby Food",
    "sugary-snacks": "Confectionery",
    "confectioneries": "Confectionery",
    "chocolates": "Confectionery",
    "desserts": "Desserts",
    "fruits-and-vegetables-based-foods": "Fruits & Vegetables",
    "canned-foods": "Canned Foods",
    "breads": "Bread & Bakery",
    "biscuits-and-cakes": "Bread & Bakery",
    "pastas": "Pasta & Rice",
    "rice": "Pasta & Rice",
    "dried-products": "Dried Products",
    "eggs": "Eggs",
    "nuts": "Nuts & Seeds",
    "legumes-and-their-products": "Legumes",
    "sweeteners": "Sweeteners",
}


def strip_accents(text: str) -> str:
    """Remove diacritics for brand matching."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalise_brands(df: pd.DataFrame, brand_col: str = "brands") -> pd.DataFrame:
    """Normalise brand names: lowercase, strip accents, trim whitespace.

    Also splits multi-brand entries (OFF uses comma-separated brands)
    and keeps only the first brand.
    """
    df = df.copy()
    brands = df[brand_col].fillna("").astype(str)

    # Take first brand if comma-separated
    brands = brands.str.split(",").str[0]

    # Normalise
    brands = brands.str.lower().str.strip().apply(strip_accents)

    # Treat empty string as missing
    brands = brands.replace("", pd.NA)

    df["brand_clean"] = brands
    logger.info("Brand normalisation complete. %d non-null brands", brands.notna().sum())
    return df


def deduplicate_products(
    df: pd.DataFrame,
    code_col: str = "code",
) -> pd.DataFrame:
    """Remove duplicate products by EAN code, keeping the most complete record."""
    before = len(df)

    # Score completeness and keep best record per code
    df = df.copy()
    df["_completeness"] = df.notna().sum(axis=1)
    df = df.sort_values("_completeness", ascending=False).reset_index(drop=True)

    # Only dedup where code is a real barcode (not empty/nan)
    has_code = df[code_col].notna() & (df[code_col] != "") & (df[code_col] != "nan")

    # Dedup only rows with valid codes; keep all rows without codes
    deduped_with_code = df.loc[has_code].drop_duplicates(subset=[code_col], keep="first")
    no_code = df.loc[~has_code]
    df = pd.concat([deduped_with_code, no_code], ignore_index=True)
    df = df.drop(columns=["_completeness"])

    after = len(df)
    logger.info("Deduplication: %d -> %d (removed %d duplicates)", before, after, before - after)
    return df


def harmonise_categories(
    df: pd.DataFrame,
    categories_col: str = "categories_tags",
) -> pd.DataFrame:
    """Map OFF tag arrays to a clean 2-level category hierarchy.

    Level 1: broad group (e.g., "Dairy", "Snacks", "Beverages")
    Level 2: specific subcategory from the most specific en: tag
    """
    df = df.copy()

    def _extract_en_tags(tags) -> list[str]:
        """Pull out en:-prefixed tags, stripped of prefix."""
        if tags is None or (isinstance(tags, float) and np.isnan(tags)):
            return []
        if isinstance(tags, (list, np.ndarray)):
            return [t.replace("en:", "") for t in tags if isinstance(t, str) and t.startswith("en:")]
        return []

    def _get_l1(tags) -> str:
        en_tags = _extract_en_tags(tags)
        if not en_tags:
            return "Unknown"
        # Try to map the first few tags to a known L1 category
        for tag in en_tags[:3]:
            if tag in _L1_TAG_MAP:
                return _L1_TAG_MAP[tag]
        # Fallback: clean up the first tag
        return en_tags[0].replace("-", " ").title()

    def _get_l2(tags) -> str:
        en_tags = _extract_en_tags(tags)
        if len(en_tags) < 2:
            return "Other"
        # Use the most specific (last) en: tag as L2
        specific = en_tags[-1]
        return specific.replace("-", " ").title()

    df["category_l1"] = df[categories_col].apply(_get_l1)
    df["category_l2"] = df[categories_col].apply(_get_l2)

    n_categorised = (df["category_l1"] != "Unknown").sum()
    logger.info(
        "Category harmonisation: %d/%d products categorised (%.1f%%)",
        n_categorised, len(df), n_categorised / len(df) * 100,
    )
    return df


def flag_private_label(
    df: pd.DataFrame,
    brand_col: str = "brand_clean",
) -> pd.DataFrame:
    """Flag products as private label vs. national brand.

    Uses the KNOWN_PL_BRANDS dictionary for matching.
    Also adds the retailer name for PL products.
    """
    df = df.copy()
    brands_lower = df[brand_col].fillna("").astype(str)

    df["is_private_label"] = brands_lower.isin(_PL_BRAND_SET)
    df["pl_retailer"] = brands_lower.map(KNOWN_PL_BRANDS).fillna("")

    n_pl = df["is_private_label"].sum()
    logger.info(
        "PL flagging: %d/%d products flagged as private label (%.1f%%)",
        n_pl, len(df), n_pl / len(df) * 100,
    )
    return df


def clean_off_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """Run the full OFF cleaning pipeline.

    Steps:
        1. Normalise brands
        2. Deduplicate on EAN code
        3. Harmonise categories to 2-level hierarchy
        4. Flag private label products
    """
    logger.info("Starting OFF cleaning pipeline on %d products", len(df))

    df = normalise_brands(df)
    df = deduplicate_products(df)
    df = harmonise_categories(df)
    df = flag_private_label(df)

    logger.info("Cleaning pipeline complete: %d products", len(df))
    return df
