"""Price comparison visualisations.

- Price gap waterfall: brand vs. PL price per kg/litre at each retailer
- Distribution plots: price distributions for brand vs. PL by category
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd


def plot_price_gap_waterfall(
    df: pd.DataFrame,
    top_n: int = 15,
    output_path: str | None = None,
):
    """Waterfall chart showing brand vs. PL price gap by category."""
    top = df.nlargest(top_n, "pl_discount_pct")

    fig, ax = plt.subplots(figsize=(14, 6))
    x = range(len(top))

    ax.bar(x, top["branded_median_price"], label="National Brand", alpha=0.7)
    ax.bar(x, top["pl_median_price"], label="Private Label", alpha=0.7)

    ax.set_xticks(x)
    ax.set_xticklabels(top["category_l2"] if "category_l2" in top.columns else top.index,
                       rotation=45, ha="right")
    ax.set_ylabel("Median Unit Price (EUR)")
    ax.set_title("Brand vs. Private Label Price Gap by Category")
    ax.legend()

    plt.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
    return fig
