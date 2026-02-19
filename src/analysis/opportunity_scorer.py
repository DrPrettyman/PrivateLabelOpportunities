"""Multi-factor opportunity scoring and ranking.

Combines all signals into a single ranked opportunity table:
    opportunity = w1 * nutritional_gap
               + w2 * (1 - brand_concentration)
               + w3 * category_size
               + w4 * reformulation_feasibility
               + w5 * (1 - private_label_saturation)
               + w6 * price_gap_margin

Includes sensitivity analysis on weight parameters.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class OpportunityWeights:
    """Weights for the composite opportunity score."""

    nutritional_gap: float = 0.25
    brand_fragmentation: float = 0.15  # 1 - HHI
    category_size: float = 0.15
    reformulation_feasibility: float = 0.15
    pl_opportunity: float = 0.15  # 1 - current PL saturation
    price_gap_margin: float = 0.15


def compute_opportunity_score(
    df: pd.DataFrame,
    weights: OpportunityWeights | None = None,
) -> pd.DataFrame:
    """Compute composite opportunity score per category.

    All component scores should be pre-normalised to [0, 1].
    """
    weights = weights or OpportunityWeights()
    df = df.copy()

    df["opportunity_score"] = (
        weights.nutritional_gap * df.get("nutritional_gap_norm", 0)
        + weights.brand_fragmentation * df.get("brand_fragmentation_norm", 0)
        + weights.category_size * df.get("category_size_norm", 0)
        + weights.reformulation_feasibility * df.get("reformulation_feasibility_norm", 0)
        + weights.pl_opportunity * df.get("pl_opportunity_norm", 0)
        + weights.price_gap_margin * df.get("price_gap_margin_norm", 0)
    )

    return df.sort_values("opportunity_score", ascending=False)


def sensitivity_analysis(
    df: pd.DataFrame,
    n_simulations: int = 1000,
    seed: int = 42,
) -> pd.DataFrame:
    """Vary weights randomly and check ranking stability.

    If top opportunities are robust to weight changes, the recommendation
    is strong. Returns rank statistics (mean rank, std, min, max) per category.
    """
    rng = np.random.default_rng(seed)
    ranks = []

    for _ in range(n_simulations):
        # Random Dirichlet weights (sum to 1)
        raw_weights = rng.dirichlet(np.ones(6))
        w = OpportunityWeights(*raw_weights)
        scored = compute_opportunity_score(df.copy(), w)
        scored["rank"] = range(1, len(scored) + 1)
        cat_col = "category_l1" if "category_l1" in scored.columns else "category_l2"
        ranks.append(scored[[cat_col, "rank"]].set_index(cat_col))

    all_ranks = pd.concat(ranks, axis=1)
    return pd.DataFrame({
        "mean_rank": all_ranks.mean(axis=1),
        "std_rank": all_ranks.std(axis=1),
        "min_rank": all_ranks.min(axis=1),
        "max_rank": all_ranks.max(axis=1),
    }).sort_values("mean_rank")


def normalise_column(series: pd.Series) -> pd.Series:
    """Min-max normalise a series to [0, 1]."""
    min_val = series.min()
    max_val = series.max()
    if max_val == min_val:
        return pd.Series(0.5, index=series.index)
    return (series - min_val) / (max_val - min_val)
