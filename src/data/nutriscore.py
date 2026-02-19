"""Compute Nutri-Score from raw nutrient values.

Implements the published Nutri-Score algorithm (2023 revision) to fill
in scores for products missing an official grade.

Cross-validation: where AH or Carrefour display Nutri-Score and we
also compute it from OFF raw nutrients, we verify our computation matches.

Limitation: fruits/vegetables/nuts percentage is not available in OFF
and cannot be computed. This component is set to 0, which may
underestimate positive points for products rich in these ingredients.

Reference: https://www.santepubliquefrance.fr/en/nutri-score
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Nutri-Score negative points thresholds (per 100g, general foods)
# Points 0-10 for energy, sugars, saturated fat, sodium
ENERGY_THRESHOLDS = [335, 670, 1005, 1340, 1675, 2010, 2345, 2680, 3015, 3350]
SUGARS_THRESHOLDS = [4.5, 9, 13.5, 18, 22.5, 27, 31, 36, 40, 45]
SAT_FAT_THRESHOLDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
SODIUM_THRESHOLDS = [90, 180, 270, 360, 450, 540, 630, 720, 810, 900]

# Nutri-Score positive points thresholds (per 100g)
FIBRE_THRESHOLDS = [0.9, 1.9, 2.8, 3.7, 4.7]
PROTEIN_THRESHOLDS = [1.6, 3.2, 4.8, 6.4, 8.0]

# Grade thresholds (general foods)
GRADE_THRESHOLDS = [
    (-15, -1, "a"),
    (0, 2, "b"),
    (3, 10, "c"),
    (11, 18, "d"),
    (19, 40, "e"),
]


def _vectorised_threshold_score(values: pd.Series, thresholds: list[float]) -> pd.Series:
    """Vectorised scoring against ascending thresholds. Returns 0-len(thresholds)."""
    scores = pd.Series(0, index=values.index, dtype="int8")
    for i, t in enumerate(thresholds):
        scores = scores.where(values <= t, i + 1)
    # Cap at max points
    scores = scores.clip(upper=len(thresholds))
    # NaN values get 0 points
    scores = scores.fillna(0)
    return scores


def _score_to_grade_vectorised(scores: pd.Series) -> pd.Series:
    """Vectorised conversion of numeric scores to letter grades."""
    grades = pd.Series(pd.NA, index=scores.index, dtype="string")
    for low, high, grade in GRADE_THRESHOLDS:
        mask = (scores >= low) & (scores <= high)
        grades = grades.where(~mask, grade)
    # Handle out-of-range
    grades = grades.where(scores <= 40, "e")
    grades = grades.where(scores >= -15, "a")
    return grades


def compute_nutriscore(
    energy_kcal: float | None,
    sugars_g: float | None,
    saturated_fat_g: float | None,
    salt_g: float | None,
    fibre_g: float | None = None,
    proteins_g: float | None = None,
) -> dict:
    """Compute Nutri-Score grade and numeric score from raw nutrients (single product)."""
    def _score(value, thresholds):
        if value is None or np.isnan(value):
            return 0
        for i, t in enumerate(thresholds):
            if value <= t:
                return i
        return len(thresholds)

    neg_energy = _score(energy_kcal, ENERGY_THRESHOLDS)
    neg_sugars = _score(sugars_g, SUGARS_THRESHOLDS)
    neg_sat_fat = _score(saturated_fat_g, SAT_FAT_THRESHOLDS)
    sodium_mg = (salt_g or 0) * 400
    neg_sodium = _score(sodium_mg, SODIUM_THRESHOLDS)

    negative_total = neg_energy + neg_sugars + neg_sat_fat + neg_sodium

    pos_fibre = _score(fibre_g, FIBRE_THRESHOLDS)
    pos_protein = _score(proteins_g, PROTEIN_THRESHOLDS)
    positive_total = pos_fibre + pos_protein

    score = negative_total - positive_total

    # Determine grade
    grade = "e"
    for low, high, g in GRADE_THRESHOLDS:
        if low <= score <= high:
            grade = g
            break

    return {
        "score": score,
        "grade": grade,
        "negative_total": negative_total,
        "positive_total": positive_total,
    }


def compute_nutriscore_column(df: pd.DataFrame) -> pd.DataFrame:
    """Add computed Nutri-Score columns to a DataFrame.

    Only computes for rows missing an existing nutriscore_grade AND
    that have the required base nutrients (energy, sugars, sat fat, salt).
    Uses vectorised operations for performance.
    """
    df = df.copy()

    # Identify rows needing computation
    missing_grade = df["nutriscore_grade"].isna()

    # Required nutrients for computation
    required = ["energy_kcal_100g", "sugars_100g", "saturated_fat_100g", "salt_100g"]
    has_required = df[required].notna().all(axis=1)

    compute_mask = missing_grade & has_required
    n_compute = compute_mask.sum()
    logger.info(
        "Computing Nutri-Score for %d products (%d missing grade, %d have required nutrients)",
        n_compute, missing_grade.sum(), has_required.sum(),
    )

    if n_compute == 0:
        df["nutriscore_computed"] = False
        return df

    subset = df.loc[compute_mask]

    # Negative points (vectorised)
    neg_energy = _vectorised_threshold_score(subset["energy_kcal_100g"], ENERGY_THRESHOLDS)
    neg_sugars = _vectorised_threshold_score(subset["sugars_100g"], SUGARS_THRESHOLDS)
    neg_sat_fat = _vectorised_threshold_score(subset["saturated_fat_100g"], SAT_FAT_THRESHOLDS)
    sodium_mg = subset["salt_100g"].fillna(0) * 400
    neg_sodium = _vectorised_threshold_score(sodium_mg, SODIUM_THRESHOLDS)

    negative_total = neg_energy + neg_sugars + neg_sat_fat + neg_sodium

    # Positive points (vectorised) — fibre/protein may be missing
    pos_fibre = _vectorised_threshold_score(subset["fiber_100g"].fillna(0), FIBRE_THRESHOLDS)
    pos_protein = _vectorised_threshold_score(subset["proteins_100g"].fillna(0), PROTEIN_THRESHOLDS)
    positive_total = pos_fibre + pos_protein

    # Final score
    scores = negative_total - positive_total
    grades = _score_to_grade_vectorised(scores)

    # Write computed values back
    df.loc[compute_mask, "nutriscore_grade"] = grades.values
    df.loc[compute_mask, "nutriscore_score"] = scores.values.astype(float)
    df["nutriscore_computed"] = False
    df.loc[compute_mask, "nutriscore_computed"] = True

    # Summary stats
    grade_dist = grades.value_counts().to_dict()
    logger.info("Computed grades: %s", grade_dist)
    total_coverage = df["nutriscore_grade"].notna().sum()
    logger.info(
        "Nutri-Score coverage after computation: %d/%d (%.1f%%)",
        total_coverage, len(df), total_coverage / len(df) * 100,
    )

    return df
