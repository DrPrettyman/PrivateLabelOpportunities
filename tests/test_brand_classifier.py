"""Tests for src.models.brand_classifier — PL classification pipeline."""

import pandas as pd
import pytest

from src.models.brand_classifier import build_pl_classifier


class TestBuildPlClassifier:
    def _train_data(self) -> pd.DataFrame:
        """Synthetic training data with clearly separable PL vs brand patterns."""
        pl_brands = ["hacendado", "marca blanca", "auchan", "eroski", "dia"]
        national_brands = ["nestle", "danone", "coca cola", "ferrero", "unilever"]
        rows = []
        for brand in pl_brands:
            for i in range(20):
                rows.append({"brands": f"{brand} {i}", "is_private_label": True})
        for brand in national_brands:
            for i in range(20):
                rows.append({"brands": f"{brand} product {i}", "is_private_label": False})
        return pd.DataFrame(rows)

    def test_returns_pipeline(self):
        pipeline = build_pl_classifier(self._train_data())
        assert hasattr(pipeline, "predict")

    def test_predictions_are_binary(self):
        pipeline = build_pl_classifier(self._train_data())
        preds = pipeline.predict(pd.Series(["hacendado test", "nestle cereal"]))
        assert set(preds).issubset({0, 1})

    def test_predicts_known_pl(self):
        pipeline = build_pl_classifier(self._train_data())
        pred = pipeline.predict(pd.Series(["hacendado olive oil"]))
        assert pred[0] == 1

    def test_predicts_known_brand(self):
        pipeline = build_pl_classifier(self._train_data())
        pred = pipeline.predict(pd.Series(["nestle chocolate bar"]))
        assert pred[0] == 0

    def test_handles_empty_brand(self):
        pipeline = build_pl_classifier(self._train_data())
        pred = pipeline.predict(pd.Series([""]))
        assert pred[0] in (0, 1)  # should not error
