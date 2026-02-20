"""Tests for src.analysis.category_landscape — HHI and PL penetration."""

import pandas as pd
import pytest

from src.analysis.category_landscape import (
    compute_assortment_depth,
    compute_hhi,
    compute_pl_penetration,
)


class TestComputeHhi:
    def test_monopoly_hhi_is_one(self):
        """One brand owns all products → HHI = 1.0."""
        df = pd.DataFrame([
            {"category": "Snacks", "brand": "BrandA"},
            {"category": "Snacks", "brand": "BrandA"},
            {"category": "Snacks", "brand": "BrandA"},
        ])
        result = compute_hhi(df, "category", "brand")
        assert result.iloc[0]["hhi"] == pytest.approx(1.0)

    def test_duopoly_equal_shares(self):
        """Two equal brands → HHI = 0.5² + 0.5² = 0.5."""
        df = pd.DataFrame([
            {"category": "Dairy", "brand": "A"},
            {"category": "Dairy", "brand": "B"},
        ])
        result = compute_hhi(df, "category", "brand")
        assert result.iloc[0]["hhi"] == pytest.approx(0.5)

    def test_fragmented_market(self):
        """Many small brands → low HHI."""
        df = pd.DataFrame([
            {"category": "Snacks", "brand": f"Brand{i}"}
            for i in range(100)
        ])
        result = compute_hhi(df, "category", "brand")
        assert result.iloc[0]["hhi"] == pytest.approx(0.01)

    def test_hhi_range(self):
        """HHI should always be in [0, 1]."""
        df = pd.DataFrame([
            {"category": "A", "brand": "X"},
            {"category": "A", "brand": "X"},
            {"category": "A", "brand": "Y"},
            {"category": "B", "brand": "Z"},
        ])
        result = compute_hhi(df, "category", "brand")
        assert (result["hhi"] >= 0).all()
        assert (result["hhi"] <= 1).all()

    def test_per_category(self):
        """Each category gets its own HHI."""
        df = pd.DataFrame([
            {"category": "A", "brand": "X"},
            {"category": "A", "brand": "X"},
            {"category": "B", "brand": "Y"},
            {"category": "B", "brand": "Z"},
        ])
        result = compute_hhi(df, "category", "brand")
        assert len(result) == 2
        a = result[result["category"] == "A"].iloc[0]["hhi"]
        b = result[result["category"] == "B"].iloc[0]["hhi"]
        assert a == pytest.approx(1.0)  # monopoly
        assert b == pytest.approx(0.5)  # duopoly


class TestComputePlPenetration:
    def test_all_private_label(self):
        df = pd.DataFrame([
            {"category": "A", "is_private_label": True},
            {"category": "A", "is_private_label": True},
        ])
        result = compute_pl_penetration(df, "category")
        assert result.iloc[0]["pl_penetration"] == pytest.approx(1.0)

    def test_no_private_label(self):
        df = pd.DataFrame([
            {"category": "A", "is_private_label": False},
            {"category": "A", "is_private_label": False},
        ])
        result = compute_pl_penetration(df, "category")
        assert result.iloc[0]["pl_penetration"] == pytest.approx(0.0)

    def test_mixed(self):
        df = pd.DataFrame([
            {"category": "A", "is_private_label": True},
            {"category": "A", "is_private_label": False},
            {"category": "A", "is_private_label": False},
            {"category": "A", "is_private_label": False},
        ])
        result = compute_pl_penetration(df, "category")
        assert result.iloc[0]["pl_penetration"] == pytest.approx(0.25)

    def test_per_category(self):
        df = pd.DataFrame([
            {"category": "A", "is_private_label": True},
            {"category": "A", "is_private_label": False},
            {"category": "B", "is_private_label": True},
            {"category": "B", "is_private_label": True},
        ])
        result = compute_pl_penetration(df, "category")
        a = result[result["category"] == "A"].iloc[0]["pl_penetration"]
        b = result[result["category"] == "B"].iloc[0]["pl_penetration"]
        assert a == pytest.approx(0.5)
        assert b == pytest.approx(1.0)


class TestComputeAssortmentDepth:
    def test_counts_skus(self):
        df = pd.DataFrame([
            {"retailer": "Mercadona", "category": "Snacks"},
            {"retailer": "Mercadona", "category": "Snacks"},
            {"retailer": "Mercadona", "category": "Dairy"},
            {"retailer": "AH", "category": "Snacks"},
        ])
        result = compute_assortment_depth(df, "category")
        merc_snacks = result[
            (result["retailer"] == "Mercadona") & (result["category"] == "Snacks")
        ].iloc[0]["sku_count"]
        assert merc_snacks == 2
