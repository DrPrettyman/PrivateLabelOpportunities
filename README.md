# CPG Private Label Opportunity Engine

**A data-driven framework that identifies food categories where European retailers can launch health-positioned private label products into underserved nutritional gaps.**

## Problem Statement

European grocery retailers earn 25-30% margins on private label vs. ~1% on national brands. The question: which product categories have the largest gap between consumer demand for healthier options and what's currently on shelves — and where is a private label best positioned to fill that gap?

## Business Impact

*Analysis in progress. Results will quantify:*
- Product categories where 75%+ of offerings score Nutri-Score C or worse
- Private label alternatives scoring A or B in those categories
- Reformulation paths (specific nutrient reductions) to achieve top grades
- Brand-vs-PL price premiums from actual shelf data across 3+ European retailers

## Methodology

- Analyse food products from the Open Food Facts database across European countries, enriched with pricing and assortment data scraped from supermarket websites (Mercadona, Albert Heijn, Carrefour)
- Multi-retailer scraping pipeline handling 3+ different API structures, joined to nutritional database via EAN barcode and fuzzy name matching
- Compute Nutri-Score for products missing official scores using the published algorithm
- Brand concentration (HHI), nutritional gap, and reformulation feasibility metrics per category
- Composite opportunity score with sensitivity analysis on weight parameters
- Interpretable classifier identifying attributes of successful private label products

## Key Findings

*Pending analysis completion.*

## Action Items

*Pending analysis completion.*

## Tech Stack

Python (pandas, numpy, scikit-learn, matplotlib, seaborn, plotly, requests, rapidfuzz, beautifulsoup4, playwright), Open Food Facts bulk data, Mercadona/AH/Carrefour scraped data

## Project Structure

```
├── src/                    # Modular source code
│   ├── data/               # Data loading, scrapers, joining, cleaning
│   ├── analysis/           # Category landscape, nutritional gaps, pricing, scoring
│   ├── models/             # Brand classifier, success predictor
│   └── visualisation/      # Charts and figures
├── notebooks/              # Numbered analysis notebooks (01-06)
├── data/sample/            # Small sample for reviewers
└── results/                # Figures and tables
```

## Setup

```bash
pip install -e ".[dev]"
# or
conda env create -f environment.yml
```
