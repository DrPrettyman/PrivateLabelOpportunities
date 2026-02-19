"""Category landscape analysis: brand concentration and PL penetration.

Key metrics computed per food category:
    - HHI (Herfindahl-Hirschman Index) for brand concentration
    - Private label penetration (% of products that are PL)
    - SKU count per category per retailer (assortment depth)
    - Geographic variation in PL presence
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def compute_hhi(df: pd.DataFrame, category_col: str, brand_col: str) -> pd.DataFrame:
    """Compute Herfindahl-Hirschman Index per category.

    HHI = sum of squared market shares. Range [0, 1].
    High HHI (>0.25) = concentrated (few brands dominate).
    Low HHI (<0.15) = fragmented (many small brands).
    """
    brand_counts = df.groupby([category_col, brand_col]).size().reset_index(name="count")
    category_totals = brand_counts.groupby(category_col)["count"].transform("sum")
    brand_counts["share"] = brand_counts["count"] / category_totals
    brand_counts["share_sq"] = brand_counts["share"] ** 2

    hhi = brand_counts.groupby(category_col)["share_sq"].sum().reset_index()
    hhi.columns = [category_col, "hhi"]
    return hhi


def compute_pl_penetration(
    df: pd.DataFrame,
    category_col: str,
    pl_col: str = "is_private_label",
) -> pd.DataFrame:
    """Compute private label penetration per category.

    Returns % of products flagged as private label.
    """
    result = df.groupby(category_col).agg(
        total_products=(pl_col, "count"),
        pl_products=(pl_col, "sum"),
    ).reset_index()
    result["pl_penetration"] = result["pl_products"] / result["total_products"]
    return result


def compute_assortment_depth(
    df: pd.DataFrame,
    category_col: str,
    retailer_col: str = "retailer",
) -> pd.DataFrame:
    """Count SKUs per category per retailer."""
    return df.groupby([retailer_col, category_col]).size().reset_index(name="sku_count")
