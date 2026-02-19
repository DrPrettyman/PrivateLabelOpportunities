"""Predict private label category leadership.

Identifies product/category attributes that predict PL success.
The point is feature importances, not prediction accuracy.

Label: PL products in "top 3 by scan count" within their category
(scans on Open Food Facts as a rough popularity proxy — document this
limitation clearly).

Honest caveats:
    - OFF scans are a noisy proxy for sales
    - This model identifies correlations, not causes
"""

from __future__ import annotations

import logging

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import cross_val_score

logger = logging.getLogger(__name__)


def build_success_predictor(
    df: pd.DataFrame,
    feature_cols: list[str],
    label_col: str = "is_category_leader",
) -> tuple:
    """Train a gradient boosted classifier for PL success prediction.

    Returns (model, feature_importances_df, cv_scores).
    """
    X = df[feature_cols].fillna(0)
    y = df[label_col].astype(int)

    model = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
    )

    scores = cross_val_score(model, X, y, cv=5, scoring="roc_auc")
    logger.info("Success predictor CV AUC: %.3f (+/- %.3f)", scores.mean(), scores.std())

    model.fit(X, y)

    importances = pd.DataFrame({
        "feature": feature_cols,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False)

    return model, importances, scores
