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
            "energy_kcal": poor.get("energy-kcal_100g", pd.Series()).median(),
            "sugars_g": poor.get("sugars_100g", pd.Series()).median(),
            "saturated_fat_g": poor.get("saturated-fat_100g", pd.Series()).median(),
            "salt_g": poor.get("salt_100g", pd.Series()).median(),
            "fibre_g": poor.get("fiber_100g", pd.Series()).median(),
            "proteins_g": poor.get("proteins_100g", pd.Series()).median(),
        }

        targets = _find_reformulation_path(median_profile, target_grade)
        if targets:
            results[category] = targets

    return results


def _find_reformulation_path(
    profile: dict[str, float],
    target_grade: str,
) -> list[ReformulationTarget]:
    """Search for nutrient reductions that achieve the target grade.

    Tests reducing each negative nutrient (sugar, salt, sat fat) and
    increasing each positive nutrient (fibre, protein) incrementally.
    """
    targets = []
    reducible = ["sugars_g", "saturated_fat_g", "salt_g"]

    for nutrient in reducible:
        current = profile.get(nutrient, 0) or 0
        if current <= 0:
            continue

        # Binary search for the threshold
        low, high = 0.0, current
        best = None
        for _ in range(20):  # enough precision
            mid = (low + high) / 2
            test_profile = profile.copy()
            test_profile[nutrient] = mid
            result = compute_nutriscore(**test_profile)
            if result["grade"].lower() <= target_grade.lower():
                best = mid
                low = mid
            else:
                high = mid

        if best is not None and best < current:
            targets.append(ReformulationTarget(
                nutrient=nutrient,
                current_median=current,
                target_value=round(best, 1),
                reduction_pct=round((1 - best / current) * 100, 1),
                resulting_grade=target_grade,
            ))

    return targets
