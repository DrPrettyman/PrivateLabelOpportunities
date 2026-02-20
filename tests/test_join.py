"""Tests for src.data.join — EAN and fuzzy matching."""

import pandas as pd
import pytest

from src.data.join import _build_match_key, join_on_ean


class TestJoinOnEan:
    def test_exact_ean_match(self):
        supermarket = pd.DataFrame([
            {"name": "Product A", "ean": "8410032001"},
            {"name": "Product B", "ean": "8410032002"},
        ])
        off = pd.DataFrame([
            {"product_name": "OFF A", "code": "8410032001", "brands": "Brand X"},
            {"product_name": "OFF C", "code": "9999999999", "brands": "Brand Z"},
        ])
        matched, unmatched = join_on_ean(supermarket, off)
        assert len(matched) == 1
        assert len(unmatched) == 1

    def test_strips_whitespace(self):
        supermarket = pd.DataFrame([{"name": "A", "ean": " 1234 "}])
        off = pd.DataFrame([{"product_name": "A", "code": "1234", "brands": "B"}])
        matched, _ = join_on_ean(supermarket, off)
        assert len(matched) == 1

    def test_handles_nan_ean(self):
        supermarket = pd.DataFrame([
            {"name": "A", "ean": "1234"},
            {"name": "B", "ean": None},
        ])
        off = pd.DataFrame([{"product_name": "A", "code": "1234", "brands": "B"}])
        matched, unmatched = join_on_ean(supermarket, off)
        assert len(matched) == 1
        # NaN row is dropped from matching, so unmatched only contains non-NaN misses
        assert len(unmatched) == 0

    def test_no_matches_returns_all_unmatched(self):
        supermarket = pd.DataFrame([
            {"name": "A", "ean": "1111"},
            {"name": "B", "ean": "2222"},
        ])
        off = pd.DataFrame([{"product_name": "X", "code": "9999", "brands": "Y"}])
        matched, unmatched = join_on_ean(supermarket, off)
        assert len(matched) == 0
        assert len(unmatched) == 2

    def test_matched_contains_off_columns(self):
        supermarket = pd.DataFrame([{"name": "A", "ean": "1234", "price": 1.99}])
        off = pd.DataFrame([{"product_name": "A", "code": "1234", "brands": "B", "nutriscore_grade": "a"}])
        matched, _ = join_on_ean(supermarket, off)
        assert "nutriscore_grade" in matched.columns or "nutriscore_grade_off" in matched.columns


class TestBuildMatchKey:
    def test_combines_name_and_brand(self):
        key = _build_match_key("Olive Oil Extra Virgin", "Hacendado")
        assert key == "olive oil extra virgin hacendado"

    def test_handles_none(self):
        assert _build_match_key(None, "Brand") == "brand"
        assert _build_match_key("Product", None) == "product"

    def test_handles_empty_strings(self):
        assert _build_match_key("", "") == ""
        assert _build_match_key("  ", "  ") == ""
