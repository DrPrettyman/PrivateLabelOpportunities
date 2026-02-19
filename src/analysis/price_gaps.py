"""Price gap analysis: brand vs. private label pricing by category and retailer.

Enabled by supermarket scraping data. For each category, compute:
    - Median branded price vs. median PL price (per kg/litre)
    - The "PL discount" percentage
    - Price distribution overlap (are brands and PL in the same tier?)
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def compute_price_gaps(
    df: pd.DataFrame,
    category_col: str,
    retailer_col: str = "retailer",
    price_col: str = "unit_price_eur",
    pl_col: str = "is_private_label",
) -> pd.DataFrame:
    """Compute brand vs. PL price statistics per category per retailer."""
    df = df.dropna(subset=[price_col])

    branded = df[~df[pl_col]].groupby([retailer_col, category_col])[price_col].median()
    pl = df[df[pl_col]].groupby([retailer_col, category_col])[price_col].median()

    result = pd.DataFrame({
        "branded_median_price": branded,
        "pl_median_price": pl,
    }).dropna()

    result["pl_discount_pct"] = (
        (result["branded_median_price"] - result["pl_median_price"])
        / result["branded_median_price"]
        * 100
    )
    result["price_gap_abs"] = result["branded_median_price"] - result["pl_median_price"]

    return result.reset_index().sort_values("pl_discount_pct", ascending=False)
