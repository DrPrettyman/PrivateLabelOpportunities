"""Nutritional gap analysis — THE HEADLINE analysis.

Identifies categories where existing products are nutritionally poor,
creating an opening for a health-positioned private label.

Core insight: if most breakfast cereals score Nutri-Score C-D, a retailer
who launches an A-B cereal captures the health-conscious segment AND
benefits from the regulatory push toward mandatory Nutri-Score labelling.

Key metric:
    gap = (% products scoring C/D/E) * (1 - PL penetration at A or B)
    High gap = most products unhealthy AND no PL has filled the healthy niche
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def compute_nutritional_landscape(
    df: pd.DataFrame,
    category_col: str,
    nutriscore_col: str = "nutriscore_grade",
) -> pd.DataFrame:
    """For each category, compute Nutri-Score grade distribution.

    Returns DataFrame with columns for % of products at each grade A-E,
    plus median NOVA group and key nutrient stats.
    """
    # Grade distribution
    grade_dist = (
        df.groupby([category_col, nutriscore_col])
        .size()
        .unstack(fill_value=0)
    )
    grade_pct = grade_dist.div(grade_dist.sum(axis=1), axis=0)

    # Ensure all grades present
    for grade in ["a", "b", "c", "d", "e"]:
        if grade not in grade_pct.columns:
            grade_pct[grade] = 0.0

    grade_pct = grade_pct.rename(columns={g: f"pct_grade_{g}" for g in "abcde"})
    grade_pct["pct_grade_cde"] = (
        grade_pct.get("pct_grade_c", 0)
        + grade_pct.get("pct_grade_d", 0)
        + grade_pct.get("pct_grade_e", 0)
    )

    return grade_pct.reset_index()


def compute_nutritional_gap(
    landscape_df: pd.DataFrame,
    pl_df: pd.DataFrame,
    category_col: str,
) -> pd.DataFrame:
    """Compute the 'nutritional gap' metric per category.

    gap = pct_grade_CDE * (1 - pl_penetration_at_AB)

    High gap = opportunity for a healthy private label.
    """
    merged = landscape_df.merge(pl_df, on=category_col, how="left")

    # PL penetration at good grades (A or B)
    # This needs to be computed from the product-level data
    merged["nutritional_gap"] = (
        merged["pct_grade_cde"] * (1 - merged.get("pl_penetration_at_ab", 0))
    )

    return merged.sort_values("nutritional_gap", ascending=False)


def compute_nutrient_stats(
    df: pd.DataFrame,
    category_col: str,
) -> pd.DataFrame:
    """Compute per-category summary stats for key nutrients."""
    nutrient_cols = [
        "sugars_100g", "salt_100g", "saturated_fat_100g",
        "fiber_100g", "proteins_100g", "energy_kcal_100g",
    ]
    available = [c for c in nutrient_cols if c in df.columns]

    return df.groupby(category_col)[available].agg(["median", "mean", "std"]).reset_index()
