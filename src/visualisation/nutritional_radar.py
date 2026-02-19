"""Nutritional radar charts comparing brand vs. private label products.

For each high-opportunity category, shows a radar chart comparing
the median nutritional profile of national brands vs. private labels.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_nutritional_radar(
    brand_profile: dict[str, float],
    pl_profile: dict[str, float],
    category_name: str,
    output_path: str | None = None,
):
    """Radar chart comparing nutritional profiles of brand vs. PL products."""
    nutrients = list(brand_profile.keys())
    n = len(nutrients)

    angles = [i / n * 2 * np.pi for i in range(n)]
    angles += angles[:1]

    brand_values = list(brand_profile.values()) + [list(brand_profile.values())[0]]
    pl_values = list(pl_profile.values()) + [list(pl_profile.values())[0]]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    ax.plot(angles, brand_values, "o-", linewidth=2, label="National Brand", color="#e74c3c")
    ax.fill(angles, brand_values, alpha=0.1, color="#e74c3c")

    ax.plot(angles, pl_values, "o-", linewidth=2, label="Private Label", color="#2ecc71")
    ax.fill(angles, pl_values, alpha=0.1, color="#2ecc71")

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(nutrients)
    ax.set_title(f"Nutritional Profile: {category_name}", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.0))

    plt.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
    return fig
