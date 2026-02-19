"""Opportunity matrix visualisations.

Quadrant charts showing categories by competition level vs. nutritional gap,
helping identify the "sweet spot" categories for PL entry.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd


def plot_opportunity_quadrant(
    df: pd.DataFrame,
    x_col: str = "hhi",
    y_col: str = "nutritional_gap",
    size_col: str = "total_products",
    output_path: str | None = None,
):
    """Quadrant chart: brand concentration vs. nutritional gap.

    Top-right = high gap + high concentration = hardest to enter but biggest reward
    Top-left = high gap + fragmented = sweet spot for PL entry
    """
    fig, ax = plt.subplots(figsize=(12, 8))

    scatter = ax.scatter(
        df[x_col],
        df[y_col],
        s=df[size_col] / df[size_col].max() * 500,
        alpha=0.6,
        edgecolors="black",
        linewidth=0.5,
    )

    # Label top opportunities
    top = df.nlargest(10, y_col)
    for _, row in top.iterrows():
        ax.annotate(
            row.get("category_l2", ""),
            (row[x_col], row[y_col]),
            fontsize=8,
            ha="center",
        )

    ax.axhline(y=df[y_col].median(), color="grey", linestyle="--", alpha=0.5)
    ax.axvline(x=df[x_col].median(), color="grey", linestyle="--", alpha=0.5)

    ax.set_xlabel("Brand Concentration (HHI)")
    ax.set_ylabel("Nutritional Gap")
    ax.set_title("Private Label Opportunity Matrix")

    plt.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
    return fig
