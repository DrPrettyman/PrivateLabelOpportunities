"""Reformulation feasibility analysis.

For each high-gap category, identifies what nutrient changes would shift
a typical product from Nutri-Score C/D to A/B.

E.g., "Reducing sugar from 25g to 12g per 100g in chocolate breakfast
cereals would shift Nutri-Score from D to B."

This is computable directly from the Nutri-Score algorithm.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.data.nutriscore import compute_nutriscore

logger = logging.getLogger(__name__)


@dataclass
class ReformulationTarget:
    """A specific nutrient change to improve Nutri-Score."""

    nutrient: str
    current_median: float
    target_value: float
    reduction_pct: float
    resulting_grade: str


def analyse_reformulation(
    df: pd.DataFrame,
    category_col: str,
    target_grade: str = "b",
) -> dict[str, list[ReformulationTarget]]:
    """For each category, find the minimum nutrient changes to reach target grade.

    Returns a dict mapping category -> list of ReformulationTarget.
    """
    results = {}

    for category, group in df.groupby(category_col):
        # Get median nutrient profile for poorly-scored products (C/D/E)
        poor = group[group["nutriscore_grade"].isin(["c", "d", "e"])]
        if len(poor) < 5:
            continue

        median_profile = {
            "energy_kcal": _safe_median(poor, "energy_kcal_100g"),
            "sugars_g": _safe_median(poor, "sugars_100g"),
            "saturated_fat_g": _safe_median(poor, "saturated_fat_100g"),
            "salt_g": _safe_median(poor, "salt_100g"),
            "fibre_g": _safe_median(poor, "fiber_100g"),
            "proteins_g": _safe_median(poor, "proteins_100g"),
        }

        targets = _find_reformulation_path(median_profile, target_grade)
        if targets:
            results[category] = targets

    return results


def _safe_median(df: pd.DataFrame, col: str) -> float:
    """Get median of a column, returning 0 if column missing or all NaN."""
    if col not in df.columns:
        return 0.0
    val = df[col].median()
    return 0.0 if pd.isna(val) else float(val)


def _find_reformulation_path(
    profile: dict[str, float],
    target_grade: str,
) -> list[ReformulationTarget]:
    """Search for nutrient reductions that achieve the target grade.

    Tests reducing each negative nutrient (sugar, salt, sat fat) individually.
    """
    targets = []
    reducible = ["sugars_g", "saturated_fat_g", "salt_g"]

    # Check current grade first
    current = compute_nutriscore(**profile)
    if current["grade"] <= target_grade:
        return []  # Already at or better than target

    for nutrient in reducible:
        current_val = profile.get(nutrient, 0) or 0
        if current_val <= 0:
            continue

        # Binary search for the minimum value that achieves target grade
        low, high = 0.0, current_val
        best = None
        for _ in range(20):
            mid = (low + high) / 2
            test_profile = profile.copy()
            test_profile[nutrient] = mid
            result = compute_nutriscore(**test_profile)
            if result["grade"] <= target_grade:
                best = mid
                low = mid  # Try higher (less reduction needed)
            else:
                high = mid  # Need to reduce more

        if best is not None and best < current_val:
            targets.append(ReformulationTarget(
                nutrient=nutrient,
                current_median=round(current_val, 1),
                target_value=round(best, 1),
                reduction_pct=round((1 - best / current_val) * 100, 1),
                resulting_grade=target_grade,
            ))

    return targets
