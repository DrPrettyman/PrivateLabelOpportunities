"""Category landscape visualisations.

- Treemap: category hierarchy sized by product count, coloured by PL penetration
- Bar chart: top 20 categories by brand concentration (HHI)
- Scatter: PL penetration vs. number of brands per category
- Heatmap: PL penetration by category x country/retailer
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import plotly.express as px
import pandas as pd


def plot_category_treemap(df: pd.DataFrame, output_path: str | None = None):
    """Treemap of category hierarchy, sized by product count, coloured by PL penetration."""
    fig = px.treemap(
        df,
        path=["category_l1", "category_l2"],
        values="total_products",
        color="pl_penetration",
        color_continuous_scale="RdYlGn",
        title="Product Categories: Size by SKU Count, Colour by Private Label Penetration",
    )
    if output_path:
        fig.write_html(output_path)
    return fig


def plot_hhi_bar(df: pd.DataFrame, top_n: int = 20, output_path: str | None = None):
    """Bar chart of top N categories by brand concentration (HHI)."""
    top = df.nlargest(top_n, "hhi")
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.barh(top["category_l2"], top["hhi"])
    ax.set_xlabel("HHI (Brand Concentration)")
    ax.set_title(f"Top {top_n} Categories by Brand Concentration")
    ax.invert_yaxis()
    plt.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
    return fig


def plot_pl_penetration_heatmap(df: pd.DataFrame, output_path: str | None = None):
    """Heatmap of PL penetration by category x retailer."""
    pivot = df.pivot_table(
        values="pl_penetration", index="category_l2", columns="retailer", fill_value=0
    )
    fig = px.imshow(
        pivot,
        color_continuous_scale="Blues",
        title="Private Label Penetration by Category and Retailer",
    )
    if output_path:
        fig.write_html(output_path)
    return fig
