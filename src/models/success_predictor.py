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

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import cross_val_score

logger = logging.getLogger(__name__)


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build model-ready feature matrix from OFF product data.

    Returns DataFrame with numeric features suitable for tree-based models.
    """
    features = pd.DataFrame(index=df.index)

    # Nutrient features
    nutrient_cols = [
        "energy_kcal_100g", "sugars_100g", "saturated_fat_100g",
        "salt_100g", "fiber_100g", "proteins_100g", "fat_100g",
        "carbohydrates_100g", "sodium_100g",
    ]
    for col in nutrient_cols:
        if col in df.columns:
            features[col] = df[col]

    # Nutri-Score as ordinal (a=1, b=2, ..., e=5)
    grade_map = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}
    if "nutriscore_grade" in df.columns:
        features["nutriscore_ordinal"] = df["nutriscore_grade"].map(grade_map)

    # NOVA group
    if "nova_group" in df.columns:
        features["nova_group"] = df["nova_group"]

    # Label-based binary features (vectorised via str representation for speed)
    if "labels_tags" in df.columns:
        tags_str = df["labels_tags"].astype(str).str.lower()
        features["is_organic"] = tags_str.str.contains("organic", na=False).astype(int)
        features["is_vegan"] = tags_str.str.contains("vegan", na=False).astype(int)
        features["is_vegetarian"] = tags_str.str.contains("vegetarian", na=False).astype(int)
        features["is_gluten_free"] = tags_str.str.contains("gluten-free", na=False).astype(int)
        features["n_labels"] = df["labels_tags"].apply(
            lambda tags: len(tags) if isinstance(tags, (list, np.ndarray)) else 0
        )

    # Whether Nutri-Score was computed vs official
    if "nutriscore_computed" in df.columns:
        features["nutriscore_computed"] = df["nutriscore_computed"].astype(int)

    return features


def _tag_contains(tags, keyword: str) -> int:
    """Check if any tag in a list/array contains the keyword."""
    if not isinstance(tags, (list, np.ndarray)):
        return 0
    return int(any(keyword in str(t).lower() for t in tags))


def label_category_leaders(
    df: pd.DataFrame,
    category_col: str = "category_l1",
    scan_col: str = "unique_scans_n",
    top_n: int = 3,
) -> pd.Series:
    """Label top-N PL products by scan count within each category.

    Returns boolean Series: True if the product is a PL category leader.
    """
    pl_mask = df["is_private_label"] == True
    has_scans = df[scan_col].notna() & (df[scan_col] > 0)

    is_leader = pd.Series(False, index=df.index)

    for category, group in df[pl_mask & has_scans].groupby(category_col):
        top_indices = group.nlargest(top_n, scan_col).index
        is_leader.loc[top_indices] = True

    logger.info(
        "Labelled %d PL category leaders (top %d per category)",
        is_leader.sum(), top_n,
    )
    return is_leader


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
