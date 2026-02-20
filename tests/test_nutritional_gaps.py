"""Tests for src.analysis.nutritional_gaps — gap metric correctness."""

import pandas as pd
import pytest

from src.analysis.nutritional_gaps import (
    compute_nutritional_gap,
    compute_nutritional_landscape,
)


class TestComputeNutritionalLandscape:
    def _products(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"category": "Snacks", "nutriscore_grade": "d"},
            {"category": "Snacks", "nutriscore_grade": "d"},
            {"category": "Snacks", "nutriscore_grade": "c"},
            {"category": "Snacks", "nutriscore_grade": "a"},
            {"category": "Dairy", "nutriscore_grade": "a"},
            {"category": "Dairy", "nutriscore_grade": "b"},
        ])

    def test_grade_percentages_sum_to_one(self):
        result = compute_nutritional_landscape(self._products(), "category")
        grade_cols = [c for c in result.columns if c.startswith("pct_grade_")]
        # Exclude the aggregated pct_grade_cde from the sum
        letter_cols = [c for c in grade_cols if c in [f"pct_grade_{g}" for g in "abcde"]]
        row_sums = result[letter_cols].sum(axis=1)
        for s in row_sums:
            assert s == pytest.approx(1.0, abs=1e-6)

    def test_cde_percentage_computed(self):
        result = compute_nutritional_landscape(self._products(), "category")
        assert "pct_grade_cde" in result.columns
        snacks = result[result["category"] == "Snacks"].iloc[0]
        # 3 out of 4 products are C/D → 75%
        assert snacks["pct_grade_cde"] == pytest.approx(0.75)

    def test_all_grades_present_in_output(self):
        result = compute_nutritional_landscape(self._products(), "category")
        for grade in "abcde":
            assert f"pct_grade_{grade}" in result.columns

    def test_missing_grades_filled_with_zero(self):
        # Dairy has only grades a and b — c, d, e should be 0
        result = compute_nutritional_landscape(self._products(), "category")
        dairy = result[result["category"] == "Dairy"].iloc[0]
        assert dairy["pct_grade_c"] == 0.0
        assert dairy["pct_grade_d"] == 0.0
        assert dairy["pct_grade_e"] == 0.0


class TestComputeNutritionalGap:
    def test_gap_formula(self):
        landscape = pd.DataFrame([
            {"category": "Snacks", "pct_grade_cde": 0.80},
            {"category": "Dairy", "pct_grade_cde": 0.30},
        ])
        pl = pd.DataFrame([
            {"category": "Snacks", "pl_penetration_at_ab": 0.10},
            {"category": "Dairy", "pl_penetration_at_ab": 0.60},
        ])
        result = compute_nutritional_gap(landscape, pl, "category")
        snacks = result[result["category"] == "Snacks"].iloc[0]
        dairy = result[result["category"] == "Dairy"].iloc[0]
        assert snacks["nutritional_gap"] == pytest.approx(0.80 * 0.90)
        assert dairy["nutritional_gap"] == pytest.approx(0.30 * 0.40)

    def test_sorted_descending(self):
        landscape = pd.DataFrame([
            {"category": "A", "pct_grade_cde": 0.50},
            {"category": "B", "pct_grade_cde": 0.90},
        ])
        pl = pd.DataFrame([
            {"category": "A", "pl_penetration_at_ab": 0.0},
            {"category": "B", "pl_penetration_at_ab": 0.0},
        ])
        result = compute_nutritional_gap(landscape, pl, "category")
        assert result.iloc[0]["category"] == "B"

    def test_full_pl_penetration_means_no_gap(self):
        landscape = pd.DataFrame([{"category": "X", "pct_grade_cde": 0.80}])
        pl = pd.DataFrame([{"category": "X", "pl_penetration_at_ab": 1.0}])
        result = compute_nutritional_gap(landscape, pl, "category")
        assert result.iloc[0]["nutritional_gap"] == pytest.approx(0.0)
