# CPG Private Label Opportunity Engine

**A data-driven framework that identifies food categories where European retailers can launch health-positioned private label products into underserved nutritional gaps.**

## Problem Statement

European grocery retailers earn 25-30% margins on private label vs. ~1% on national brands. The question: which product categories have the largest gap between consumer demand for healthier options and what's currently on shelves — and where is a private label best positioned to fill that gap?

## Business Impact

Analysis of 2.57M food products across 27 EU markets reveals that **73% of products score Nutri-Score C or worse** (unhealthy), while private label penetration among healthy (A/B) alternatives is only ~10%. The top opportunities:

- **Snacks** (119K products, 88% unhealthy, gap 0.88) — largest market with almost no healthy PL
- **Condiments & Sauces** (31K products, 77% gap) — salt reduction path is technically feasible
- **Breakfast** (8K products, 93% gap) — highest nutritional gap but requires aggressive reformulation

At published private label margin rates (25-30%), these categories represent significant annual revenue opportunity per retail chain.

## Key Findings

1. **Massive nutritional gap**: 30 of 45 food categories have >70% unhealthy products with minimal healthy PL alternatives
2. **Reformulation is feasible in many categories**: Crepes & Galettes needs only 37% sugar reduction to reach Nutri-Score B; Meat Products needs 80% salt reduction
3. **Markets are fragmented**: Almost all categories have low brand concentration (HHI <0.05) — easy to enter
4. **Cross-country variation**: The same category can be 95% CDE in one country but 70% in another, enabling targeted launches
5. **PL leaders have slightly better nutrition**: Lower sugar (2.8 vs 3.6g/100g) than average products

## Methodology

- Analysed 2,568,269 food products from the Open Food Facts database across 27 EU countries, enriched with pricing scraped from Mercadona (Spain, 3,225 products) and Albert Heijn (Netherlands, 11,209 products)
- Built multi-retailer scraping pipeline handling different API structures (REST, mobile auth), joined to nutritional database via EAN barcode and fuzzy name matching (51% and 41% match rates)
- Computed Nutri-Score for 706K products missing official scores using the published 2023 algorithm, increasing coverage from 32% to 59%
- Built brand concentration (HHI), nutritional gap, and reformulation feasibility metrics per product category
- Ranked categories by 6-component composite opportunity score with Monte Carlo sensitivity analysis (1000 Dirichlet weight simulations)
- Trained interpretable gradient boosted classifier (CV AUC 0.65) and brand classifier (CV F1 0.996) identifying attributes of successful private label products

## Tech Stack

Python (pandas, numpy, scikit-learn, matplotlib, seaborn, requests, rapidfuzz, DuckDB), Open Food Facts bulk data, Mercadona/Albert Heijn scraped data

## Project Structure

```
├── src/
│   ├── data/               # Data loading, scrapers, joining, cleaning, Nutri-Score
│   │   ├── scrapers/       # Mercadona, Albert Heijn API clients
│   │   ├── load_off.py     # Open Food Facts loader
│   │   ├── clean.py        # Brand normalisation, category mapping, PL flagging
│   │   ├── join.py         # EAN + fuzzy name matching
│   │   └── nutriscore.py   # Vectorised Nutri-Score computation
│   ├── analysis/           # Category landscape, nutritional gaps, pricing, scoring
│   └── models/             # Brand classifier, PL success predictor
├── notebooks/              # Numbered analysis notebooks (01–06 + 05b)
├── scripts/                # Pipeline scripts (build_dataset.py, scrapers)
├── data/sample/            # Small sample for reviewers
├── results/                # 18 PNG charts + analysis outputs
└── notes.md                # Detailed data findings log
```

## Setup

```bash
# Clone and install
git clone <repo-url>
cd PrivateLabelOpportunities
pip install -e ".[dev]"

# Download data (4.4GB Open Food Facts Parquet)
python scripts/download_off.py

# Run scrapers
python scripts/scrape_mercadona.py
python scripts/scrape_albert_heijn.py

# Build dataset (cleaning + Nutri-Score + joining, ~6 min)
PYTHONPATH=. python scripts/build_dataset.py

# Run notebooks
jupyter notebook notebooks/
```

## Notebooks

| # | Notebook | Description |
|---|----------|-------------|
| 01 | Data Loading & Cleaning | OFF data profiling, format discoveries, cleaning pipeline |
| 02 | Supermarket Scraping | Scraper results, API structures, join quality |
| 03 | Category Landscape EDA | Nutri-Score landscape, HHI, PL penetration, price gaps |
| 04 | Nutritional Gap Analysis | Top-10 deep dives, nutrient heatmap, reformulation paths |
| 05 | Opportunity Scoring | Composite scores, Monte Carlo sensitivity, weight scenarios |
| 05b | Predictive Model | PL success predictor, brand classifier, feature importances |
| 06 | Findings & Recommendations | Executive summary, strategic recommendations |
