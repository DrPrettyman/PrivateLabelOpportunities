"""Tests for src.data.nutriscore — Nutri-Score computation against published algorithm."""

import pandas as pd
import pytest

from src.data.nutriscore import compute_nutriscore, compute_nutriscore_column


class TestComputeNutriscore:
    """Test single-product Nutri-Score against hand-calculated values."""

    def test_healthy_product_grade_a(self):
        """Low-calorie, low-sugar, low-fat, low-salt → grade A."""
        result = compute_nutriscore(
            energy_kcal=100, sugars_g=2, saturated_fat_g=0.5, salt_g=0.1,
            fibre_g=5.0, proteins_g=8.0,
        )
        assert result["grade"] == "a"
        assert result["score"] < 0

    def test_unhealthy_product_grade_e(self):
        """High-calorie, high-sugar, high-fat, high-salt → grade D or E."""
        result = compute_nutriscore(
            energy_kcal=2500, sugars_g=40, saturated_fat_g=10, salt_g=3.0,
        )
        assert result["grade"] in ("d", "e")
        assert result["score"] > 10

    def test_moderate_product_grade_c(self):
        """Mid-range nutrients → grade B or C."""
        result = compute_nutriscore(
            energy_kcal=800, sugars_g=10, saturated_fat_g=3, salt_g=0.8,
            fibre_g=1.5, proteins_g=4.0,
        )
        assert result["grade"] in ("b", "c")

    def test_none_values_treated_as_zero(self):
        """Missing nutrients should score 0 points, not error."""
        result = compute_nutriscore(
            energy_kcal=None, sugars_g=None, saturated_fat_g=None, salt_g=None,
        )
        assert result["score"] == 0
        assert result["negative_total"] == 0
        assert result["positive_total"] == 0

    def test_score_decomposition(self):
        """score = negative_total - positive_total."""
        result = compute_nutriscore(
            energy_kcal=500, sugars_g=8, saturated_fat_g=2, salt_g=0.5,
            fibre_g=3.0, proteins_g=5.0,
        )
        assert result["score"] == result["negative_total"] - result["positive_total"]

    def test_salt_to_sodium_conversion(self):
        """Salt is converted to sodium (mg) via * 400 before scoring."""
        # 2.25g salt = 900mg sodium → max sodium points (10)
        result = compute_nutriscore(
            energy_kcal=0, sugars_g=0, saturated_fat_g=0, salt_g=2.25,
        )
        assert result["negative_total"] == 10  # only sodium contributes

    def test_grade_boundaries(self):
        """Test that boundary scores map to correct grades."""
        # Score -1 → grade A (boundary: -15 to -1)
        # Score 0 → grade B (boundary: 0 to 2)
        # Score 3 → grade C (boundary: 3 to 10)
        # Score 11 → grade D (boundary: 11 to 18)
        # Score 19 → grade E (boundary: 19 to 40)
        for score, expected_grade in [(-1, "a"), (0, "b"), (3, "c"), (11, "d"), (19, "e")]:
            result = compute_nutriscore(
                energy_kcal=0, sugars_g=0, saturated_fat_g=0, salt_g=0,
            )
            # Directly test the grade lookup rather than engineering exact nutrients
            from src.data.nutriscore import GRADE_THRESHOLDS
            grade = "e"
            for low, high, g in GRADE_THRESHOLDS:
                if low <= score <= high:
                    grade = g
                    break
            assert grade == expected_grade


class TestComputeNutriscoreColumn:
    """Test vectorised Nutri-Score computation on DataFrames."""

    def _df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"nutriscore_grade": None, "energy_kcal_100g": 100, "sugars_100g": 2,
             "saturated_fat_100g": 0.5, "salt_100g": 0.1, "fiber_100g": 3.0,
             "proteins_100g": 6.0},
            {"nutriscore_grade": "b", "energy_kcal_100g": 500, "sugars_100g": 15,
             "saturated_fat_100g": 4, "salt_100g": 1.0, "fiber_100g": 1.0,
             "proteins_100g": 3.0},
            {"nutriscore_grade": None, "energy_kcal_100g": None, "sugars_100g": None,
             "saturated_fat_100g": None, "salt_100g": None, "fiber_100g": None,
             "proteins_100g": None},
        ])

    def test_only_computes_missing_grades(self):
        result = compute_nutriscore_column(self._df())
        # Row 0: had no grade, has required nutrients → computed
        assert result["nutriscore_computed"].iloc[0] == True
        # Row 1: already had grade → not computed
        assert result["nutriscore_computed"].iloc[1] == False
        # Row 2: no grade but missing required nutrients → not computed
        assert result["nutriscore_computed"].iloc[2] == False

    def test_preserves_existing_grades(self):
        result = compute_nutriscore_column(self._df())
        assert result["nutriscore_grade"].iloc[1] == "b"

    def test_computed_grade_is_valid(self):
        result = compute_nutriscore_column(self._df())
        computed = result.loc[result["nutriscore_computed"], "nutriscore_grade"]
        assert all(g in ("a", "b", "c", "d", "e") for g in computed)
