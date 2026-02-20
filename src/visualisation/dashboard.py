"""Streamlit dashboard for CPG Private Label Opportunity Engine.

Run:
    streamlit run src/visualisation/dashboard.py
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

SAMPLE_DIR = Path("data/sample")
RESULTS_DIR = Path("results")


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load pre-computed data for the dashboard."""
    category = pd.read_parquet(SAMPLE_DIR / "category_summary.parquet")
    opportunity = pd.read_parquet(SAMPLE_DIR / "opportunity_scores.parquet")
    return category, opportunity


def main() -> None:
    """Streamlit app entry point."""
    try:
        import streamlit as st
    except ImportError:
        print("Streamlit not installed. Run: pip install streamlit")
        return

    st.set_page_config(page_title="CPG Private Label Opportunities", layout="wide")
    st.title("CPG Private Label Opportunity Engine")
    st.markdown(
        "Identifying food categories where European retailers can launch "
        "health-positioned private label products into underserved nutritional gaps."
    )

    category_df, opportunity_df = load_data()

    # --- Tabs ---
    tab_landscape, tab_gaps, tab_ranking, tab_quality = st.tabs([
        "Category Landscape", "Nutritional Gaps", "Opportunity Ranking", "Data Quality",
    ])

    # ── Category Landscape ────────────────────────────────────────────────

    with tab_landscape:
        st.subheader("Market Structure by Category")

        col1, col2, col3 = st.columns(3)
        col1.metric("Categories Analysed", len(category_df))
        col2.metric(
            "Total Products",
            f"{category_df['total_products'].sum():,.0f}",
        )
        median_hhi = category_df["hhi"].median()
        col3.metric("Median HHI", f"{median_hhi:.3f}", help="<0.15 = fragmented")

        # Treemap: category size coloured by PL penetration
        st.markdown("#### Category Size by Private Label Penetration")
        fig_tree = px.treemap(
            category_df,
            path=["category_l1"],
            values="total_products",
            color="pl_penetration",
            color_continuous_scale="RdYlGn",
            title="Category treemap — size = products, colour = PL penetration",
        )
        fig_tree.update_layout(margin=dict(t=40, l=10, r=10, b=10))
        st.plotly_chart(fig_tree, use_container_width=True)

        # HHI bar chart
        st.markdown("#### Brand Concentration (HHI)")
        hhi_sorted = category_df.sort_values("hhi", ascending=True)
        fig_hhi = px.bar(
            hhi_sorted, x="hhi", y="category_l1", orientation="h",
            color="hhi", color_continuous_scale="Reds",
            labels={"hhi": "HHI", "category_l1": ""},
        )
        fig_hhi.update_layout(height=max(400, len(category_df) * 20), showlegend=False)
        st.plotly_chart(fig_hhi, use_container_width=True)

    # ── Nutritional Gaps ──────────────────────────────────────────────────

    with tab_gaps:
        st.subheader("Nutritional Gap Analysis")
        st.markdown(
            "**Key metric:** `gap = % unhealthy (C/D/E) × (1 − PL penetration at A/B)`. "
            "High gap = most products are unhealthy AND no private label fills the healthy niche."
        )

        # Headline metrics
        col1, col2, col3 = st.columns(3)
        avg_cde = category_df["pct_grade_cde"].mean()
        avg_pl = category_df["pl_penetration"].mean()
        high_gap = (category_df["nutritional_gap"] > 0.7).sum()
        col1.metric("Avg % Unhealthy (C/D/E)", f"{avg_cde:.0%}")
        col2.metric("Avg PL Penetration", f"{avg_pl:.0%}")
        col3.metric("Categories with Gap > 0.7", high_gap)

        # Scatter: % CDE vs PL penetration at AB
        st.markdown("#### Nutritional Quality vs. Private Label Health Coverage")
        fig_scatter = px.scatter(
            category_df, x="pct_grade_cde", y="pl_penetration_ab",
            size="total_products", text="category_l1",
            labels={
                "pct_grade_cde": "% Products Scoring C/D/E (Unhealthy)",
                "pl_penetration_ab": "PL Penetration at A/B (Healthy)",
            },
            color="nutritional_gap",
            color_continuous_scale="YlOrRd",
        )
        fig_scatter.update_traces(textposition="top center", textfont_size=8)
        fig_scatter.update_layout(height=550)
        # Add quadrant lines
        fig_scatter.add_hline(y=0.15, line_dash="dash", line_color="grey", opacity=0.5)
        fig_scatter.add_vline(x=0.7, line_dash="dash", line_color="grey", opacity=0.5)
        fig_scatter.add_annotation(
            x=0.9, y=0.05, text="HIGH OPPORTUNITY", showarrow=False,
            font=dict(size=12, color="red"),
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

        # Top gap categories
        st.markdown("#### Top 10 Nutritional Gap Categories")
        top_gaps = category_df.nlargest(10, "nutritional_gap")[
            ["category_l1", "pct_grade_cde", "pl_penetration_ab",
             "nutritional_gap", "total_products"]
        ].rename(columns={
            "category_l1": "Category",
            "pct_grade_cde": "% Unhealthy",
            "pl_penetration_ab": "PL at A/B",
            "nutritional_gap": "Gap Score",
            "total_products": "Products",
        })
        st.dataframe(
            top_gaps.style.format({
                "% Unhealthy": "{:.0%}",
                "PL at A/B": "{:.1%}",
                "Gap Score": "{:.3f}",
                "Products": "{:,.0f}",
            }),
            use_container_width=True,
            hide_index=True,
        )

    # ── Opportunity Ranking ───────────────────────────────────────────────

    with tab_ranking:
        st.subheader("Composite Opportunity Ranking")
        st.markdown(
            "Six-factor composite score: nutritional gap, brand fragmentation, "
            "category size, reformulation feasibility, PL opportunity, and price gap margin."
        )

        # Sortable table
        display_cols = [
            "category_l1", "opportunity_score", "nutritional_gap",
            "hhi", "pl_penetration", "total_products", "pct_grade_cde",
            "min_reduction_pct",
        ]
        available = [c for c in display_cols if c in opportunity_df.columns]
        display_df = opportunity_df[available].rename(columns={
            "category_l1": "Category",
            "opportunity_score": "Opportunity Score",
            "nutritional_gap": "Nutritional Gap",
            "hhi": "HHI",
            "pl_penetration": "PL Penetration",
            "total_products": "Products",
            "pct_grade_cde": "% Unhealthy",
            "min_reduction_pct": "Min Reformulation %",
        })
        st.dataframe(
            display_df.style.format({
                "Opportunity Score": "{:.3f}",
                "Nutritional Gap": "{:.3f}",
                "HHI": "{:.4f}",
                "PL Penetration": "{:.1%}",
                "Products": "{:,.0f}",
                "% Unhealthy": "{:.0%}",
                "Min Reformulation %": "{:.0f}%",
            }),
            use_container_width=True,
            hide_index=True,
        )

        # Score breakdown chart for top 10
        st.markdown("#### Score Component Breakdown — Top 10")
        top10 = opportunity_df.nlargest(10, "opportunity_score")
        component_cols = [
            "nutritional_gap_norm", "brand_fragmentation_norm",
            "category_size_norm", "reformulation_feasibility_norm",
            "pl_opportunity_norm", "price_gap_margin_norm",
        ]
        avail_components = [c for c in component_cols if c in top10.columns]
        if avail_components:
            fig_bar = go.Figure()
            labels = {
                "nutritional_gap_norm": "Nutritional Gap",
                "brand_fragmentation_norm": "Brand Fragmentation",
                "category_size_norm": "Category Size",
                "reformulation_feasibility_norm": "Reformulation",
                "pl_opportunity_norm": "PL Opportunity",
                "price_gap_margin_norm": "Price Gap",
            }
            for col in avail_components:
                fig_bar.add_trace(go.Bar(
                    name=labels.get(col, col),
                    x=top10["category_l1"],
                    y=top10[col],
                ))
            fig_bar.update_layout(
                barmode="group", height=450,
                xaxis_title="", yaxis_title="Normalised Score",
            )
            st.plotly_chart(fig_bar, use_container_width=True)

    # ── Data Quality ──────────────────────────────────────────────────────

    with tab_quality:
        st.subheader("Data Quality Summary")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Dataset Overview")
            st.markdown(f"""
            - **Categories:** {len(category_df)}
            - **Total products:** {category_df['total_products'].sum():,.0f}
            - **Data source:** Open Food Facts (bulk download)
            - **Enrichment:** Mercadona + Albert Heijn scraped pricing
            """)

        with col2:
            st.markdown("#### Coverage Notes")
            st.markdown("""
            - Nutri-Score computed for products missing official grades
            - Open Food Facts is crowd-sourced; coverage varies by country
            - Price data from scrapes are point-in-time snapshots
            - HHI computed from brand field (may undercount store brands)
            """)

        # Distribution of products across categories
        st.markdown("#### Products per Category")
        cat_sorted = category_df.sort_values("total_products", ascending=True)
        fig_cat = px.bar(
            cat_sorted, x="total_products", y="category_l1", orientation="h",
            labels={"total_products": "Number of Products", "category_l1": ""},
        )
        fig_cat.update_layout(height=max(400, len(category_df) * 20))
        st.plotly_chart(fig_cat, use_container_width=True)


if __name__ == "__main__":
    main()
