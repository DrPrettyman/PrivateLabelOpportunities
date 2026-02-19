# CPG Private Label Opportunity Engine — Project Plan

## Problem Statement

> Which food product categories represent the highest-value opportunities for a European retailer to launch or expand private label lines — and can we quantify the gap between what national brands offer nutritionally and what a health-positioned store brand could deliver?

## Why This Project

Private label is the hottest growth story in retail: $280B in the US alone (projected 2025), growing at 2× the rate of national brands. McKinsey, Circana, and EY all publish consulting reports helping retailers decide *where* to launch private labels. This project replicates that analysis programmatically using open data.

| Article Principle | How This Project Addresses It |
|---|---|
| *"Answer a business question, don't just make predictions"* | The deliverable is a ranked list of product categories where a private label has the best shot at competing, with quantified nutritional and competitive gaps |
| *Real business problems > toy datasets* | "Where should we launch our next store brand?" is the question every grocery chain category manager asks — Mintel charges thousands for this report |
| *End-to-end pipeline* | Combines Open Food Facts bulk database (3M+ products), scraped product catalogues from 3+ European supermarkets (Mercadona, Albert Heijn, Carrefour), and EU regulatory data (Nutri-Score algorithm). Multiple API types, web scraping, fuzzy matching, significant cleaning challenges |
| *Industry-specific: retail/e-commerce/fintech alignment* | Directly relevant to Revolut (they've explored retail analytics), Clarity AI (ESG/health angles), and any retail-adjacent company |
| *Quantified business impact with stated assumptions* | Revenue estimates grounded in real market data: private label margins are 25-30% vs. 1.3% for national brands (published Capstone/McKinsey figures) |
| *No Kaggle competitions* | Open Food Facts EDA exists on Kaggle, but the private label opportunity framing has zero matching portfolio projects |
| *Professional code quality* | Modular package, not a monolithic notebook |

### Timeliness Bonus

France voted in November 2025 to mandate Nutri-Score labelling on all pre-packaged foods. The EU abandoned EU-wide Nutri-Score plans in early 2025, creating regulatory fragmentation. Ultra-processed food (NOVA classification) is a massive consumer trend. All of this makes nutritional positioning a live business concern, not a stale academic exercise.

---

## Data Sources & Pipeline

### Source 1: Open Food Facts Database (Product & Nutritional Data)

**What it provides:** 3M+ food products globally with brand, category, ingredients, Nutri-Score (A-E), NOVA group (1-4 ultra-processing scale), full nutrient breakdown per 100g, labels/certifications (organic, fair trade, etc.), country availability, and packaging info.

**Access method:**
- Bulk download: CSV/Parquet dump (~1.5GB compressed) from Hugging Face or OFF servers — entire database in one file
- API: For targeted lookups during enrichment/validation
- Download frequency: nightly dumps available

**Key fields:**
- `product_name`, `brands`, `categories_tags`, `countries_tags`
- `nutriscore_grade` (A-E), `nova_group` (1-4)
- `nutriments` (energy, fat, saturated fat, sugars, salt, fibre, protein per 100g)
- `labels_tags` (organic, vegan, gluten-free, etc.)
- `stores_tags`, `manufacturing_places_tags`

**Data quality challenges to document:**
- Crowd-sourced → inconsistent categorisation, missing fields, duplicate products
- Coverage varies by country (France/Germany strong, others patchy)
- Some products lack Nutri-Score/NOVA (can be computed from raw nutrients using the published algorithm)
- Brand names not standardised ("Nestlé" vs "Nestle" vs "NESTLÉ")

**Cleaning is substantial and demonstrable work** — exactly what the article wants: *"Obtaining messy data... cleaning with documented problems and solutions."*

### Source 2: European Supermarket Product Catalogues (Price & Assortment Intelligence)

Instead of relying on thin crowdsourced price data, we scrape actual product catalogues directly from supermarket websites. This gives us **real current prices, real assortment depth, and real private label identification** — the kind of data consulting firms charge for.

The project scrapes **3-5 retailers across 2-3 countries**, each with a different access pattern. This is genuine pipeline engineering: different API structures, rate limits, authentication, data formats, and category taxonomies that must all be normalised into a unified schema.

#### Tier 1 — Primary Targets (scrape these first)

**Mercadona (Spain) — ~8,000-10,000 products**
- **Access:** Internal REST API at `tienda.mercadona.es/api/`. No authentication needed, just set a valid postal code cookie.
- **Endpoints:** `/api/categories/` (list all), `/api/categories/{id}/` (products per category, 3 levels deep), `/api/products/{id}/` (individual product detail)
- **Data fields:** product name, price, unit price, packaging, thumbnail image, category hierarchy, brand (implicitly: everything is Hacendado/Mercadona's own brands or the handful of national brands they stock)
- **Rate limiting:** ~1.5s delay between requests is sufficient. Full catalogue crawlable in a few hours.
- **Existing tooling:** Multiple open-source scrapers on GitHub; Medium article by @ablancodev documents the full API structure.
- **Private label relevance:** Mercadona is the *ultimate* private label case study — their Hacendado, Deliplus, Bosque Verde etc. brands dominate ~50% of their shelves. This gives us a near-complete view of a retailer that has already executed the strategy we're analysing.
- **Limitation:** Mercadona's API does NOT return nutritional data or EAN barcodes — we join to Open Food Facts by fuzzy-matching product name + brand + weight.

**Albert Heijn (Netherlands) — ~24,000 products**
- **Access:** Undocumented mobile API at `api.ah.nl/mobile-services/`. Anonymous token obtainable via POST to `/mobile-auth/v1/auth/token/anonymous`.
- **Endpoints:** Product search (`/product/search/v2?query=`), category listing, product details with full nutritional info.
- **Data fields:** product name, brand, price (EUR cents), unit price, category hierarchy, **EAN barcode**, **full nutritional values per 100g**, allergy info, discount/promotion status, product features (organic, recyclable, etc.)
- **Existing tooling:** `SupermarktConnector` Python package on PyPI (`pip install supermarktconnector`) wraps the AH and Jumbo APIs. Also `appiepy` package for individual product lookups with nutritional data.
- **Private label relevance:** AH's "AH" and "AH Biologisch" private labels are clearly branded. The API returns brand field, making PL identification trivial. The Netherlands has one of the highest private label penetrations in Europe (~30%+).
- **Key advantage:** AH returns **EAN barcodes AND nutritional data directly** — meaning we can join to Open Food Facts with high confidence AND cross-validate their nutrition values.

**Carrefour (France and/or Spain) — varies by country**
- **Access:** Web scraping of `carrefour.fr` or `carrefour.es` product pages. No clean internal API has been publicly documented; the site uses dynamic rendering.
- **Approach:** Use `requests` + BeautifulSoup or Playwright for JS-rendered pages. Category crawling via sitemap or navigating category tree. Alternatively, Carrefour's Spain marketplace runs on Mirakl platform with EAN-based product identification.
- **Data fields:** product name, brand, price, price per kg/l, nutritional values (Carrefour France shows Nutri-Score on product pages), country of origin, product description, ingredients.
- **Private label relevance:** Carrefour has extensive PL lines — "Carrefour", "Carrefour Bio", "Carrefour Classic", "Simpl" (budget tier). Operates in both France (strongest Nutri-Score market) and Spain (where you can compare against Mercadona).
- **Complexity:** Hardest to scrape of the three — anti-bot measures, dynamic rendering. This is a plus for the portfolio: demonstrates handling of real-world scraping challenges.

#### Tier 2 — Supplementary (add if time permits, adds cross-country depth)

**Jumbo (Netherlands) — ~20,000 products**
- **Access:** Internal mobile API, no auth required. `SupermarktConnector` Python package supports it out of the box alongside Albert Heijn.
- **Data fields:** product name, price, unit price, brand, category, images. Less nutritional detail than AH but good for price comparisons within the same market.
- **Value:** Paired with Albert Heijn, gives us **two competing retailers in the same country** — enables same-product price comparison (brand X costs €Y at AH vs. €Z at Jumbo).

**Lidl (Germany/Spain/any EU country)**
- **Access:** Web scraping of country-specific Lidl sites (e.g., `lidl.de`, `lidl.es`). Sitemap-based crawling documented in `supermarket_scrapy` GitHub project for `lidl.de`.
- **Data fields:** product name, price, delivery dates, category, product description, images.
- **Private label relevance:** Your observation is exactly right — Lidl's assortment is ~80%+ own-brand. This actually makes Lidl *very* valuable for the project, just differently: Lidl represents the *endpoint* of the private label strategy. We can measure "what does a shelf look like when a retailer has fully committed to PL?" — the category mix, price points, nutritional quality of an almost-entirely-PL catalogue. Comparing Lidl's PL product quality (nutrition, NOVA) against Carrefour's or AH's PL products in the same categories shows whether discounters cut corners nutritionally.
- **Limitation:** Lidl's online catalogue is patchy — heavily weighted toward non-food special-buy items in some countries. The food range online may underrepresent what's actually in-store. Document this honestly.

**Tesco (UK)**
- **Access:** Official Tesco Labs API (`devportal.tescolabs.com`) **has stopped issuing new subscriptions** as of recent checks. Fallback is web scraping of `tesco.com/groceries` — product pages include GTIN/EAN, full nutritional data, price, and Tesco Clubcard pricing.
- **Value:** Adds UK market dimension. Tesco has extensive PL tiers (Tesco Finest, Tesco, Tesco Everyday Value) — three-tier PL strategy is an interesting interview talking point.

#### How Supermarket Data Ties into the Analysis

The supermarket catalogues serve three distinct analytical purposes:

1. **Real price data replacing crowdsourced estimates.** Instead of the thin Open Prices dataset (125K crowdsourced entries concentrated in France), we have actual shelf prices for every product a retailer stocks. This makes the price gap analysis between national brands and private label *credible*: "In the breakfast cereal category at Mercadona, Hacendado products average €2.10/kg vs. branded at €4.80/kg — a 56% discount" is a statement grounded in real data, not projections.

2. **Assortment depth as a market signal.** The number of SKUs a retailer stocks per category reveals strategic priorities. If Mercadona stocks 40 private label yogurts but only 8 branded ones, while Carrefour stocks 15 PL vs. 60 branded, that's a measurable difference in PL strategy by category — and it tells us which categories retailers have already identified as PL-friendly.

3. **Cross-validation of Open Food Facts.** By joining supermarket product data to Open Food Facts on EAN barcode (where available) or fuzzy name+brand+weight matching, we can: validate that OFF's nutritional data matches what retailers display, identify products that are on shelves but missing from OFF (coverage gap), and enrich OFF records with current pricing.

#### Joining Strategy

The join between supermarket data and Open Food Facts is non-trivial and showcases data engineering skills:

- **EAN/barcode match (highest confidence):** Albert Heijn returns EAN codes. Tesco returns GTIN. Match directly to OFF's `code` field. Expected high match rate for branded products, lower for private label.
- **Fuzzy name+brand+weight match (fallback):** For Mercadona and others without EAN in API responses. Use `rapidfuzz` or similar for string similarity, constrained by category and package weight to reduce false positives. Document precision/recall of matching.
- **Unmatched products:** Products in supermarket data but not in OFF are interesting — they represent shelf products with no open nutritional data. Report these as coverage gaps. Products in OFF but not on any supermarket shelf may be discontinued.

### Source 3: Open Prices API (Supplementary Validation Only)

Demoted from primary to supplementary. The crowdsourced Open Prices dataset (~125K prices, concentrated in France) is now used only to:
- Validate our scraped prices where overlap exists
- Fill gaps for retailers/countries we don't scrape directly
- Provide historical price context (the supermarket scrapes are point-in-time snapshots)

This is honest scoping: we acknowledge the limitation rather than pretending 125K crowdsourced entries constitute comprehensive price intelligence.

### Source 4: Derived / Computed Data

**Nutri-Score algorithm:** Published and open. For products missing a score, compute it from raw nutrient values + category. This demonstrates:
- Understanding of the scoring methodology (interview talking point)
- Ability to implement a domain-specific algorithm
- Data augmentation to increase coverage
- **Cross-validation opportunity:** Where Albert Heijn or Carrefour display Nutri-Score and we also compute it from OFF raw nutrients, we can verify our computation matches

**NOVA classification heuristics:** NOVA groups (1-4, from unprocessed to ultra-processed) can be partially inferred from ingredient lists using keyword matching (e.g., presence of emulsifiers, flavour enhancers, hydrogenated oils → NOVA 4). Document the precision/recall of your heuristic vs. the ground-truth labels that exist.

---

## Pipeline Architecture

```
private_label_intel/
├── README.md                          # < 500 words
├── requirements.txt
├── environment.yml
│
├── src/
│   ├── __init__.py
│   ├── data/
│   │   ├── load_off.py               # Load/parse Open Food Facts bulk download
│   │   ├── scrapers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # Abstract scraper class (shared rate-limiting, retry logic)
│   │   │   ├── mercadona.py          # tienda.mercadona.es API client
│   │   │   ├── albert_heijn.py       # api.ah.nl mobile API client
│   │   │   ├── carrefour.py          # carrefour.fr/es web scraper
│   │   │   ├── jumbo.py              # Jumbo NL API client (optional)
│   │   │   └── lidl.py               # Lidl web scraper (optional)
│   │   ├── join.py                   # EAN-match + fuzzy name/brand/weight join
│   │   ├── clean.py                  # Brand normalisation, category mapping, dedup
│   │   └── nutriscore.py             # Compute Nutri-Score from raw nutrients
│   ├── analysis/
│   │   ├── category_landscape.py     # Brand concentration per category
│   │   ├── nutritional_gaps.py       # Nutri-Score/NOVA distributions by category
│   │   ├── price_gaps.py             # Brand vs. PL price analysis per retailer/category
│   │   ├── opportunity_scorer.py     # Multi-factor opportunity ranking
│   │   └── reformulation.py          # "What would it take to make a Nutri-Score A?"
│   ├── models/
│   │   ├── brand_classifier.py       # Classify products as private label vs. national brand
│   │   └── success_predictor.py      # Which product attributes predict category leadership?
│   └── visualisation/
│       ├── category_map.py           # Treemap / sunburst of the category landscape
│       ├── opportunity_matrix.py     # Quadrant charts (competition vs. gap)
│       ├── price_comparison.py       # Brand vs. PL price distributions by retailer
│       └── nutritional_radar.py      # Radar charts comparing brand vs. private label nutrition
│
├── notebooks/
│   ├── 01_data_loading_cleaning.ipynb
│   ├── 02_supermarket_scraping.ipynb  # Scraping + joining walkthrough
│   ├── 03_eda_category_landscape.ipynb
│   ├── 04_nutritional_gap_analysis.ipynb
│   ├── 05_opportunity_scoring.ipynb
│   └── 06_findings_recommendations.ipynb
│
├── data/
│   ├── raw/                          # .gitignore'd — download instructions
│   ├── scraped/                      # .gitignore'd — scraper outputs (timestamped)
│   ├── processed/
│   └── sample/                       # Small sample for reviewers
│
└── results/
    ├── figures/
    └── tables/
```

---

## Analysis Plan

### Phase 1: Data Collection & Cleaning (Week 1-2)

**Objective:** Collect product data from Open Food Facts and 3+ European supermarket websites, join them, and produce an analysis-ready dataset.

**Steps:**
1. Download Open Food Facts Parquet dump, filter to EU countries (France, Germany, Spain, Italy, Netherlands, Belgium, etc.)
2. **Build supermarket scrapers:**
   - Mercadona: hit `/api/categories/` → iterate sub-categories → collect all products with prices. ~8-10K products, few hours with 1.5s delay.
   - Albert Heijn: obtain anonymous token, paginate through categories via mobile API. ~24K products. Extract EAN barcodes and nutritional data.
   - Carrefour (FR or ES): crawl category pages, parse product detail pages for price, nutrition, Nutri-Score. Handle JS rendering if needed.
   - Each scraper inherits from a base class with shared rate-limiting, retry, and output schema.
3. **Join supermarket data to Open Food Facts:**
   - EAN match (AH, Tesco if included) → high-confidence join
   - Fuzzy name+brand+weight match (Mercadona, Lidl) → medium-confidence join, document match rate
   - Log unmatched products in both directions
4. Brand normalisation: fuzzy-match brand strings, identify corporate parents (e.g., "Buitoni" → Nestlé)
5. Category harmonisation: reconcile OFF's hierarchical tag system with each supermarket's own category tree into a clean 2-level hierarchy
6. Compute Nutri-Score for products missing it (using the published algorithm from nutrients + category). Cross-validate against AH/Carrefour displayed scores where available.
7. Build NOVA heuristic for products without NOVA classification
8. Flag products as "private label" vs. "national brand" — this is now much easier with supermarket data:
   - Mercadona: if brand is Hacendado/Deliplus/Bosque Verde/etc. → PL (and the vast majority of their catalogue)
   - Albert Heijn: if brand field starts with "AH" → PL
   - Carrefour: if brand contains "Carrefour"/"Simpl" → PL
   - Supplement with known PL brand lists for other retailers in OFF data
   - Train a simple classifier on labelled examples to catch edge cases

**Deliverables:** Clean joined dataset, data quality report, scraper documentation, join match-rate report, brand/category mapping documentation

### Phase 2: Exploratory Analysis — Category Landscape (Week 2-3)

**Objective:** Map the competitive landscape of European food categories.

**Key analyses:**
1. **Brand concentration by category:** For each food category, compute HHI (Herfindahl-Hirschman Index) or equivalent concentration metric. Which categories are dominated by 2-3 brands vs. fragmented across many?
2. **Private label penetration by category:** What % of products in each category are already private label? Now measurable *per retailer* — Mercadona's PL penetration in dairy vs. Carrefour's.
3. **Category size and assortment depth:** SKU counts per category per retailer as a strategic signal. A retailer stocking 40 PL yogurts but 8 branded yogurts has made a deliberate bet.
4. **Geographic variation:** Which categories have strong private label presence in the Netherlands but not Spain? Compare AH's PL portfolio vs. Mercadona's.
5. **Price tier analysis (NEW — enabled by supermarket data):** For each category, compute median brand price vs. median PL price. The "PL discount" varies enormously by category — quantify it.

**Visualisations:**
- Treemap: category hierarchy sized by product count, coloured by private label penetration
- Bar chart: top 20 categories by brand concentration (HHI)
- Scatter: private label penetration vs. number of brands per category
- Heatmap: private label penetration by category × country/retailer
- **NEW — Price gap waterfall:** For top categories, show brand vs. PL price per kg/litre at each retailer

### Phase 3: Nutritional Gap Analysis (Week 3-4) — THE HEADLINE

**Objective:** Identify categories where existing products are nutritionally poor, creating an opening for a health-positioned private label.

This is the novel contribution. The insight: *if most breakfast cereals on shelves are Nutri-Score C-D, a retailer who launches a Nutri-Score A-B cereal line under their own brand captures the health-conscious segment AND benefits from the regulatory push toward mandatory Nutri-Score labelling.*

**Method:**

1. **For each category, compute the nutritional landscape:**
   - Distribution of Nutri-Score grades (% A through E)
   - Median NOVA group (how ultra-processed is this category?)
   - Key nutrient distributions: sugar, salt, saturated fat, fibre per 100g

2. **Compute the "nutritional gap":**
   - `gap = (% of products scoring C, D, or E) × (1 - private_label_penetration_at_A_or_B)`
   - High gap = most products are unhealthy AND no private label has filled the healthy niche
   - This is the actionable metric: "In category X, 78% of products score C or worse, and only 2 private label products score A or B"

3. **Reformulation feasibility analysis:**
   - For each high-gap category, identify what nutrient changes would shift a typical product from C/D to A/B
   - E.g., "Reducing sugar from 25g to 12g per 100g in chocolate breakfast cereals would shift Nutri-Score from D to B"
   - This is computable directly from the Nutri-Score algorithm — not speculation
   - Frame as: "the reformulation cost" of capturing the health niche

4. **NOVA-based analysis (ultra-processing angle):**
   - Which categories are dominated by NOVA 4 (ultra-processed) products?
   - Where could a "clean label" private brand (NOVA 1-2) differentiate?
   - Cross with consumer trend data: UPF avoidance is a top-3 food trend in 2025

### Phase 4: Opportunity Scoring & Ranking (Week 4-5)

**Objective:** Combine all signals into a single ranked opportunity table.

**Opportunity score formula:**

```
opportunity = w1 × nutritional_gap
            + w2 × (1 - brand_concentration)
            + w3 × category_size
            + w4 × reformulation_feasibility
            + w5 × (1 - private_label_saturation)
            + w6 × price_gap_margin
```

Where:
- `nutritional_gap`: proportion of poor-scoring products without healthy PL alternatives
- `brand_concentration`: inverted HHI — fragmented = easier to enter
- `category_size`: proxy for market size (product count × country availability)
- `reformulation_feasibility`: how achievable is it to make a Nutri-Score A/B product (inverse of nutrient reduction required)
- `private_label_saturation`: existing PL penetration (high = less opportunity)
- `price_gap_margin` (NEW): the larger the gap between branded and PL prices in a category, the more margin room a new PL entrant has — computed from scraped supermarket prices

**Sensitivity analysis:** Vary weights w1-w5 and show ranking stability. If the top opportunities are robust to weight changes, the recommendation is strong.

**Deliverable — the ranked table:**

| Rank | Category | # Products | PL Penetration | % Nutri-Score C-E | Healthy PL Gap | HHI | Opportunity Score | Recommended Position |
|------|----------|-----------|----------------|-------------------|----------------|-----|-------------------|---------------------|
| 1 | Chocolate Breakfast Cereals | 847 | 18% | 91% | 89% | 0.15 | 8.7 | Nutri-Score A, low sugar, whole grain |
| 2 | ... | ... | ... | ... | ... | ... | ... | ... |

### Phase 5: Predictive Model — What Makes a PL Category Leader? (Week 5)

**Objective:** Build a lightweight model that predicts private label success from product/category attributes.

**Approach:**
- Label: private label products that appear in the "top 3 by review/popularity proxy" within their category (this is tricky — Open Food Facts has scans-per-product as a rough popularity signal)
- Features: Nutri-Score grade, NOVA group, price tier (if price data available), organic/label certifications, ingredient count, nutrient profile
- Model: logistic regression or gradient boosted trees — keep it interpretable
- **The point is not prediction accuracy** — it's the feature importances
- "Private label products that lead their categories tend to have X, Y, Z characteristics"

**Honest caveats:**
- "Scans on Open Food Facts" is a noisy proxy for sales. State this clearly
- This model identifies correlations, not causes. A Nutri-Score A label doesn't cause success — but the association is informative for a retailer

### Phase 6: Communication & Polish (Week 5-6)

**Package for the 3-minute review.**

---

## README Template (< 500 words)

```markdown
# CPG Private Label Opportunity Engine

**One-line summary:** A data-driven framework that identifies food categories
where European retailers can launch health-positioned private label products
into underserved nutritional gaps.

## Problem Statement

European grocery retailers earn 25-30% margins on private label vs. ~1%
on national brands. The question: which product categories have the largest
gap between consumer demand for healthier options and what's currently on
shelves — and where is a private label best positioned to fill that gap?

## Business Impact

Analysis of [N] products across [M] European markets reveals [X] product
categories where 75%+ of offerings score Nutri-Score C or worse, with
fewer than [Y] private label alternatives scoring A or B. The top
opportunity — [specific category] — has [Z] branded products averaging
Nutri-Score [grade], with a reformulation path to A requiring [specific
nutrient reduction]. At published private label margin rates, this
represents an estimated [revenue figure] annual opportunity per retail chain.

## Methodology

- Analysed [N] food products from the Open Food Facts database across
  [M] European countries, enriched with real-time pricing and assortment
  data scraped from [X] supermarket websites (Mercadona, Albert Heijn,
  Carrefour, et al.)
- Built multi-retailer scraping pipeline handling 3+ different API
  structures and joined to nutritional database via EAN barcode and
  fuzzy name matching
- Computed Nutri-Score for [X]K products missing official scores using
  the published algorithm
- Built brand concentration (HHI), nutritional gap, and reformulation
  feasibility metrics per product category
- Ranked categories by composite opportunity score with sensitivity
  analysis on weight parameters
- Trained interpretable classifier to identify attributes of successful
  private label products

## Key Findings

- [Finding 1: top underserved category with numbers]
- [Finding 2: reformulation feasibility insight]
- [Finding 3: geographic variation — opportunities differ by country]
- [Finding 4: NOVA/ultra-processing gap in specific category]

## Action Items

- Retailers targeting [category X] should position at Nutri-Score A/B by
  reducing [nutrient] below [threshold]g/100g
- [Category Y] in [country Z] has the lowest private label penetration
  despite high brand fragmentation — low barrier to entry
- [Specific recommendation 3]

## Tech Stack

Python (pandas, numpy, scikit-learn, matplotlib, seaborn, plotly,
requests, rapidfuzz, beautifulsoup4),
Open Food Facts bulk data, Mercadona/AH/Carrefour scraped data
```

---

## Resume Line

> Built a private label opportunity engine analysing [N]M+ food products across European markets by combining Open Food Facts nutritional data with real-time pricing scraped from 3+ supermarket websites (Mercadona, Albert Heijn, Carrefour). Identified [X] high-opportunity categories with nutritional gaps (75%+ Nutri-Score C-E) and low private label penetration, with quantified brand-vs-PL price premiums from actual shelf data. [GitHub link]

---

## Interview Talking Points

This project naturally generates discussion across multiple dimensions:

- **Business strategy:** Private label economics (margin structure), category management, competitive positioning, why retailers are the new CPG companies
- **Domain knowledge:** Nutri-Score algorithm (can explain exactly how it's computed), NOVA classification, EU regulatory landscape (France mandate vs. EU abandonment), ultra-processed food trends
- **Data engineering:** Built scrapers for 3+ European supermarket APIs/websites, each with different access patterns (REST API, mobile API, web scraping with JS rendering). Joined scraped data to 3M+ row crowd-sourced database via EAN barcode matching AND fuzzy name matching with documented precision/recall. Brand normalisation, category harmonisation across incompatible taxonomies.
- **Statistics:** HHI for concentration measurement, sensitivity analysis on composite scores, dealing with noisy proxies, observational vs. causal claims
- **ML (lightweight but purposeful):** Brand/PL classifier, feature importance for category success — kept interpretable because the business audience needs to understand it
- **Causal inference:** Why you can't claim "launching a Nutri-Score A product causes X% market share." What experiment would you design? (A/B test with shelf placement randomisation)
- **Ethics/fairness:** Nutri-Score has known biases (penalises olive oil, cheese — why Italy opposes it). Web scraping ethics — respectful rate limiting, robots.txt compliance, data used for research not commercial exploitation

### Differentiation from Existing Work

- Open Food Facts EDA exists on Kaggle and GitHub: nutritional analysis, clustering products, comparing countries → **none of these frame a business question**
- Supermarket scraping projects exist (Apify actors, GitHub repos) → **none of these do analysis on the data, they just extract it**
- Private label opportunity identification is done by paid consultancies (Circana, Mintel, McKinsey) → **no open-source / portfolio version exists**
- Nutri-Score computation from raw data exists → but nobody has used it as a **gap analysis tool for market entry**
- The combination of multi-retailer scraping + nutritional positioning + reformulation feasibility + opportunity scoring is **the novel contribution**

---

## Checklist

### GitHub Requirements
- [ ] README under 500 words with all 5 required sections
- [ ] Commented, organised code with docstrings
- [ ] `requirements.txt` AND `environment.yml`
- [ ] No API keys or passwords
- [ ] Sample data included
- [ ] Download/reproduction instructions for full dataset

### Project Quality
- [ ] Business context is the headline
- [ ] End-to-end: supermarket scraping → OFF download → joining → cleaning → analysis → model → recommendations
- [ ] Scrapers are modular, well-documented, with respectful rate limiting
- [ ] Join methodology documented with match rates and confidence levels
- [ ] No copied tutorials — the PL opportunity framing is original
- [ ] Assumptions stated alongside every estimate
- [ ] Data limitations (crowd-sourced OFF, point-in-time scrapes, coverage bias) documented honestly

### Presentation Standards
- [ ] Professional visualisations with consistent styling
- [ ] Concise notebook narrative
- [ ] Quantified results with sensitivity analysis
- [ ] Specific, actionable category recommendations
- [ ] Easy navigation: numbered notebooks, clear modules

---

## Timeline

| Week | Phase | Key Deliverable |
|------|-------|----------------|
| 1 | Download OFF bulk data, build supermarket scrapers (Mercadona + AH), initial scrape runs | Raw datasets from 3+ sources |
| 2 | Join scraped data to OFF (EAN + fuzzy matching), clean, normalise brands | Analysis-ready joined dataset, match-rate report |
| 3 | Category mapping, PL classification, EDA, price gap analysis | Category landscape + price tier visualisations |
| 4 | Nutritional gap analysis, Nutri-Score computation, reformulation feasibility | Gap metrics per category |
| 5 | Opportunity scoring, sensitivity analysis, predictive model | Ranked opportunity table, feature importances |
| 6 | README, polish, final review | Publishable repository |

---

## How This Complements the Steam Project

Together, these two projects cover:

| Dimension | Steam Project | Private Label Project |
|-----------|--------------|----------------------|
| Domain | Entertainment/gaming | Retail/CPG/food |
| Data source | Three APIs (crawled) | Bulk DB + 3-5 supermarket scrapers (mixed access methods) |
| Core technique | Recommendation engine (collaborative + content) | Competitive analysis + scoring framework |
| ML component | Matrix factorisation (ALS) | Classification + feature importance |
| Business framing | Publisher investment strategy | Retailer private label strategy |
| Novel metric | Revenue-weighted hit rate | Nutritional gap × PL penetration × price premium |
| Regulatory angle | None | Nutri-Score mandate, UPF regulation |
| Data joining | Three APIs by game ID | EAN barcode + fuzzy name matching across 4+ sources |
| Interview strength | Rec-sys, cold start, A/B testing | Scraping, causal inference, domain expertise, ethics |

No overlap in domain, technique, or framing — but both demonstrate the same core competency: taking a question companies pay consultants to answer and building the data-driven version from open sources.