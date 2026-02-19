"""Classify products as private label vs. national brand.

Supplements known PL brand lists to catch edge cases.
Trained on labelled examples from supermarket scrapes where PL
identification is trivial (Mercadona, AH brand field).
"""

from __future__ import annotations

import logging

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)


def build_pl_classifier(
    train_df: pd.DataFrame,
    text_col: str = "brands",
    label_col: str = "is_private_label",
) -> Pipeline:
    """Train a simple TF-IDF + logistic regression classifier for PL detection."""
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), max_features=5000)),
        ("clf", LogisticRegression(max_iter=1000)),
    ])

    X = train_df[text_col].fillna("")
    y = train_df[label_col].astype(int)

    scores = cross_val_score(pipeline, X, y, cv=5, scoring="f1")
    logger.info("PL classifier CV F1: %.3f (+/- %.3f)", scores.mean(), scores.std())

    pipeline.fit(X, y)
    return pipeline
