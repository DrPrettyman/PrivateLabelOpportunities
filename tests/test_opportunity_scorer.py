"""Tests for src.analysis.opportunity_scorer — scoring, normalisation, sensitivity."""

import pandas as pd
import pytest

from src.analysis.opportunity_scorer import (
    OpportunityWeights,
    compute_opportunity_score,
    normalise_column,
    sensitivity_analysis,
)


class TestNormaliseColumn:
    def test_basic_normalisation(self):
        s = pd.Series([10, 20, 30])
        result = normalise_column(s)
        assert result.iloc[0] == pytest.approx(0.0)
        assert result.iloc[1] == pytest.approx(0.5)
        assert result.iloc[2] == pytest.approx(1.0)

    def test_all_same_value(self):
        s = pd.Series([5, 5, 5])
        result = normalise_column(s)
        assert (result == 0.5).all()

    def test_range_zero_to_one(self):
        s = pd.Series([100, 200, 50, 300, 150])
        result = normalise_column(s)
        assert result.min() == pytest.approx(0.0)
        assert result.max() == pytest.approx(1.0)


class TestComputeOpportunityScore:
    def _df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"category_l1": "Snacks", "nutritional_gap_norm": 0.9,
             "brand_fragmentation_norm": 0.8, "category_size_norm": 0.7,
             "reformulation_feasibility_norm": 0.6, "pl_opportunity_norm": 0.9,
             "price_gap_margin_norm": 0.5},
            {"category_l1": "Dairy", "nutritional_gap_norm": 0.3,
             "brand_fragmentation_norm": 0.4, "category_size_norm": 0.5,
             "reformulation_feasibility_norm": 0.8, "pl_opportunity_norm": 0.3,
             "price_gap_margin_norm": 0.6},
        ])

    def test_score_added(self):
        result = compute_opportunity_score(self._df())
        assert "opportunity_score" in result.columns

    def test_sorted_descending(self):
        result = compute_opportunity_score(self._df())
        scores = result["opportunity_score"].tolist()
        assert scores == sorted(scores, reverse=True)

    def test_weights_applied(self):
        """Verify that changing weights changes the score."""
        df = self._df()
        default = compute_opportunity_score(df.copy())
        custom = compute_opportunity_score(
            df.copy(),
            OpportunityWeights(
                nutritional_gap=0.5, brand_fragmentation=0.1,
                category_size=0.1, reformulation_feasibility=0.1,
                pl_opportunity=0.1, price_gap_margin=0.1,
            ),
        )
        # Scores should differ
        assert not default["opportunity_score"].values == pytest.approx(
            custom["opportunity_score"].values
        )

    def test_default_weights_sum_to_one(self):
        w = OpportunityWeights()
        total = (w.nutritional_gap + w.brand_fragmentation + w.category_size
                 + w.reformulation_feasibility + w.pl_opportunity + w.price_gap_margin)
        assert total == pytest.approx(1.0)

    def test_score_range(self):
        """Score should be in [0, 1] when inputs are in [0, 1] and weights sum to 1."""
        result = compute_opportunity_score(self._df())
        assert (result["opportunity_score"] >= 0).all()
        assert (result["opportunity_score"] <= 1.0 + 1e-6).all()


class TestSensitivityAnalysis:
    def _df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"category_l1": f"Cat_{i}",
             "nutritional_gap_norm": i / 5, "brand_fragmentation_norm": (5 - i) / 5,
             "category_size_norm": i / 5, "reformulation_feasibility_norm": 0.5,
             "pl_opportunity_norm": i / 5, "price_gap_margin_norm": 0.5}
            for i in range(1, 6)
        ])

    def test_returns_rank_statistics(self):
        result = sensitivity_analysis(self._df(), n_simulations=50)
        assert "mean_rank" in result.columns
        assert "std_rank" in result.columns
        assert "min_rank" in result.columns
        assert "max_rank" in result.columns

    def test_rank_range_valid(self):
        result = sensitivity_analysis(self._df(), n_simulations=50)
        n = len(self._df())
        assert (result["min_rank"] >= 1).all()
        assert (result["max_rank"] <= n).all()

    def test_deterministic_with_seed(self):
        df = self._df()
        r1 = sensitivity_analysis(df.copy(), n_simulations=20, seed=123)
        r2 = sensitivity_analysis(df.copy(), n_simulations=20, seed=123)
        pd.testing.assert_frame_equal(r1, r2)
