# Data Collection & Cleaning Notes

## Phase 1 Progress Log

### 1. Open Food Facts (OFF) Data Download

**Source**: Hugging Face — `openfoodfacts/product-database` → `food.parquet`
**Full file**: 4.4 GB (4,216 MB), ~4.29M products worldwide

**Download challenges**:
- **DuckDB remote Parquet streaming fails**: DuckDB makes many HTTP range requests to read remote Parquet files. Hugging Face rate-limits these (HTTP 429). Even with retries, the stream stalls after a few hundred MB. Also tried `urllib.request.urlretrieve` — also hit 429s.
- **Solution**: Download the full 4.4 GB file via `curl -L` first, then filter locally with DuckDB. This works reliably because curl makes a single streaming request.

**Parquet schema discovery**:
- Used `SELECT * FROM parquet_schema('file.parquet')` — the column name field is `name`, not `column_name`.
- The `nutriments` column is NOT a flat set of columns like `nutriments.energy-kcal_100g`. It's a **nested array of structs**: `STRUCT(name VARCHAR, value DOUBLE, "100g" DOUBLE, ...)[]`. Each nutrient is an element in the array.
- Extraction required DuckDB's `list_filter` + `list_extract`: `(list_extract(list_filter(nutriments, x -> x.name = 'energy-kcal'), 1))."100g" AS "energy_kcal_100g"`
- DuckDB's `UNNEST` in `SELECT` doesn't work directly — need a subquery: `SELECT country FROM (SELECT UNNEST(countries_tags) AS country FROM ...) GROUP BY country`.

**EU filtering**: Filtered to 27 EU countries using `list_contains(countries_tags, 'en:france')` OR clauses. Result: **2,568,322 EU products** in 105.5 MB.

**Country distribution (top 5)**:
| Country | Products |
|---------|----------|
| France | 1,204,960 |
| Germany | 385,542 |
| Spain | 349,853 |
| Italy | 263,110 |
| Belgium | 95,729 |

### 2. OFF Data Loading & Profiling

**Key format issues discovered when loading into pandas**:
- `product_name` comes as a list of structs `[{lang: 'main', text: '...'}, {lang: 'fr', text: '...'}]` — actually numpy arrays of dicts. Needed a custom `_extract_product_name()` function to pull the 'main' language text.
- `categories_tags`, `countries_tags`, `brands_tags`, `labels_tags`, `stores_tags` are all numpy arrays, not Python lists. Important for `isinstance` checks and `in` operator.
- `nutriscore_grade` includes "not-applicable" (72,920 products) — these need to be treated as missing, not as a grade.
- Empty string `""` in brands needs to be treated as missing.

**Data quality profile (2,568,322 EU products)**:

| Field | Missing | Pct |
|-------|---------|-----|
| product_name | 183,290 | 7.1% |
| brands | 925,933 | 36.1% |
| categories_tags | 1,309,406 | 51.0% |
| nutriscore_grade | 1,752,420 | 68.2% (after removing "not-applicable") |
| nova_group | 2,001,173 | 77.9% |
| energy_kcal_100g | 803,849 | 31.3% |
| fiber_100g | 1,921,519 | 74.8% |
| proteins_100g | 786,928 | 30.6% |

**Nutri-Score distribution (official only, 815,902 products)**:
- E: 219,618 (27%) — worst
- D: 214,240 (26%)
- C: 173,494 (21%)
- A: 114,087 (14%) — best
- B: 94,463 (12%)

Observation: the E+D categories dominate official scores (53%), suggesting the "healthiest" products are underrepresented in OFF (selection bias — products with health claims are more likely to have Nutri-Score displayed and therefore entered).

### 3. Mercadona Scraper

**API structure** (verified Feb 2026):
- `GET /api/categories/` → returns `{results: [{id, name, categories: [{id, name}]}]}`
- `GET /api/categories/{sub_id}/` → returns `{name, categories: [{name, products: [...]}]}`
- Three levels of nesting: top category → subcategory → sub-sub-category → products

**Key findings**:
- 26 top-level categories, 112 food subcategories (after filtering out non-food: cleaning, cosmetics, pets, etc.)
- No `brand` field in API response. Brand is embedded in `display_name` (e.g., "Aceite de oliva 0,4° Hacendado").
- Brand extraction heuristic: check for known PL brands first (Hacendado, Deliplus, etc.), then fall back to last capitalised word. The fallback is imperfect — picks up product descriptors like "Filetes", "Barra", "Zero".
- No EAN barcodes or nutritional data in the API.
- Prices are strings in the API — need `float()` conversion.
- `price_instructions.unit_price` = total product price; `price_instructions.reference_price` = per-unit price; `reference_format` = unit (e.g., "€/L", "€/kg").

**Result**: 3,225 food products scraped. 1,954 PL (60.6%) / 1,271 branded (39.4%).
Hacendado dominates PL at ~60% of all products.

### 4. Albert Heijn Scraper

**API structure** (verified Feb 2026):
- Auth: `POST /mobile-auth/v1/auth/token/anonymous` with body `{"clientId": "appie"}`. The `clientId` is required — empty JSON returns 400.
- Headers must include `User-Agent: Appie/8.22.3` and `x-application: AHWEBSHOP`.
- Search: `GET /mobile-services/product/search/v2` with params `taxonomyId`, `size` (max 100), `page`.
- Categories available from TAXONOMY filter in any search response.

**Key findings**:
- 67 taxonomy categories total, 47 food categories after filtering.
- Has nutriscore grade directly in the API — no need to compute.
- Has brand, mainCategory, subCategory, priceBeforeBonus, currentPrice.
- `salesUnitSize` contains weight/volume (e.g., "1 kg", "750 ml").
- `unitPriceDescription` has per-unit price as text (e.g., "prijs per liter €0.95").
- No EAN barcode or detailed nutrition (fat, sugar, salt) in search results.
- Products appear across multiple taxonomy categories → requires deduplication on product_id.

**Bug fixed**: `__init__` passed `request_delay=1.0` explicitly AND inherited via `**kwargs`, causing TypeError. Fixed with `kwargs.setdefault("request_delay", 1.0)`.

**Result**: 11,209 food products after deduplication. 2,937 PL (26.2%) / 8,272 branded (73.8%).
AH PL brands: AH, AH Biologisch, AH Excellent, AH Terra, AH Basic.

### 5. Data Cleaning (OFF)

**Brand normalisation**:
- Take first brand if comma-separated (OFF has multi-brand entries).
- Lowercase, strip accents, trim whitespace.
- Empty strings → NA.
- 1,557,265 non-null brands after cleaning (60.6%).

**Deduplication**:
- On EAN code (`code` column). Only 53 duplicates found — OFF data is already very clean on EAN uniqueness.

**Category harmonisation**:
- OFF uses hierarchical `en:` tags in arrays: `['en:dairies', 'en:yogurts', 'en:fruit-yogurts']`.
- Mapped first meaningful `en:` tag to 30+ L1 categories (Dairy, Beverages, Snacks, etc.).
- Last `en:` tag used as L2 subcategory.
- Only 42.4% of products (1,088,223) had mappable categories. 57.6% categorised as "Unknown" (mostly because 51% of products lack `categories_tags` entirely).

**Private label flagging**:
- Compiled 80+ known PL brand names across 15+ EU retailers.
- 210,122 products flagged as PL (8.2% of OFF EU).
- Top PL retailers in OFF: Carrefour (26K), Lidl (22K), U (16K), Auchan (14K), Bonarea (12K), Mercadona (11K).

### 6. Nutri-Score Computation

**Algorithm**: Vectorised implementation of 2023 Nutri-Score formula.
- Negative points (0-10 each): energy, sugars, saturated fat, sodium.
- Positive points (0-5 each): fibre, protein.
- Score = negative_total - positive_total.
- Grade thresholds: A(-15 to -1), B(0-2), C(3-10), D(11-18), E(19-40).

**Limitation**: Fruits/vegetables/nuts percentage not available in OFF → set to 0. This may underestimate positive points for produce-rich products.

**Coverage**:
- 706,373 products had missing grade but sufficient nutrients (energy + sugars + sat fat + salt) to compute.
- After computation: 1,522,252 / 2,568,269 = **59.3% coverage** (up from 31.8%).
- Computed grade distribution: C (252K, 36%), D (168K, 24%), B (159K, 22%), A (112K, 16%), E (15K, 2%).
- The computed products skew healthier than official grades — likely because products with complete nutrient data tend to be more mainstream/regulated.

### 7. Fuzzy Joining (Supermarket → OFF)

**Approach**:
- Pre-filter OFF to retailer's country (Spain for Mercadona, Netherlands for AH) to reduce candidate pool.
- Cap at 50K branded OFF products per retailer.
- Use rapidfuzz `process.extractOne` with `token_sort_ratio` scorer, threshold 75%.
- Match on concatenated `name + brand` string.

**Mercadona results**: 1,644 / 3,225 matched (51.0%), mean score 82.9.
- Perfect matches at top (e.g., "Refresco Coca-Cola" → "Refresco Coca-Cola").
- Some false positives near threshold (e.g., "Canela en rama Hacendado" → "Helado Crema de Nata" at 75).

**AH results**: 4,556 / 11,209 matched (40.6%), mean score 83.7.
- Perfect matches at top (e.g., "Amstel Radler citroen 0.0 6-pack" → exact match).

**Known limitations**:
- 50K candidate cap means some matches are missed.
- Threshold 75 admits some false positives — could raise to 80 for stricter matching at the cost of fewer matches.
- No category-based pre-filtering yet — this could improve precision.
- Products without brands in OFF cannot be matched well.

### 8. Category Landscape Analysis (Notebook 03)

**Analysis-ready subset**: 694,313 products (filtered to those with Nutri-Score + category + brand, in categories with >=100 products). 45 L1 categories.

**Key findings from Nutri-Score landscape**:
- Most food categories are dominated by unhealthy products: median %CDE across categories is ~80%
- **Worst categories** (95-100% CDE): Taralli, Sweet Pies, Breakfast, Bread Coverings, Pies, Spreads, Desserts, Snacks
- **Best categories** (low CDE): Eggs (4%), Vegetables (4-6%), Baby Food (20%), Dietary Supplements (34%)
- Beverages are mixed at 66% CDE

**Brand concentration (HHI)**:
- Almost all categories are highly fragmented (HHI < 0.05) — easy to enter
- Only 3 categories show concentration: Vegetables Prepared (0.47-0.68), Taralli (0.42), Capsules (0.15)
- This means most categories are wide open for new private label entry

**Private label penetration**:
- Median PL penetration: ~13% across categories
- Highest PL: Bread Coverings (25%), Sandwiches (22%), Eggs (21%), Meat & Poultry (21%)
- Lowest PL: Taralli (0%), Meat Products (0%), Capsules (1%), Dietary Supplements (2%)
- PL at healthy grades (A+B) is much lower — median ~10%. The healthy niche is underserved.

**Top Nutritional Gap Opportunities (Gap = %CDE × (1 - PL@AB))**:
1. Breakfast (gap=0.935): 98% CDE, only 5% PL among healthy products
2. Snacks (gap=0.879): 96% CDE, only 9% PL among healthy — HUGE market (119K products)
3. Desserts (gap=0.839): 95% CDE, only 12% PL among healthy
4. Fats & Oils (gap=0.834): 86% CDE, almost no healthy PL (4%)
5. Condiments & Sauces (gap=0.767): 89% CDE, 14% PL among healthy — large market (30K products)

**Price gaps (supermarket data)**:
- Median PL discount: 22.4% cheaper than national brands
- 16 categories have >30% PL discount — strong margin potential
- Price data available from both Mercadona (Spain) and AH (Netherlands)

**numpy array gotcha**: `category_path` in supermarket data is a numpy array, not a Python list. Must use `isinstance(p, (list, np.ndarray))` for type checks.

### 9. Nutritional Gap Deep Dives (Notebook 04)

**Analysis-ready subset**: 837,912 products with Nutri-Score + valid category.

**Top 10 gap categories**: Taralli, Breakfast, Fish And Meat And Eggs, Festive Foods, Snacks, Meat Products, Crepes And Galettes, Desserts, Fats & Oils, Spreads.

**Reformulation feasibility** (7 of 10 categories had viable paths to Nutri-Score B):
- **Breakfast**: Requires 84% sugar reduction (55g → 9g) — very challenging, suggests reformulation alone won't work; need fundamentally different product concepts.
- **Crepes & Galettes**: Most achievable — 37% sugar, 56% sat fat, 27% salt reductions.
- **Fats & Oils / Fish Meat Eggs**: 96% sat fat reduction needed — essentially impossible without changing product category.
- **Meat Products**: 80% salt reduction (2.2g → 0.4g) — aggressive but commercially possible.
- **Spreads**: Salt reduction viable.
- **Snacks and Desserts**: No single-nutrient path found — likely need simultaneous multi-nutrient reformulation.

**PL vs National Brand nutritional quality**:
- PL column derived from `pl_retailer` (not `is_pl`).
- Chart generated comparing % A/B products between PL and national brands across top 10 categories.

**Cross-country variation** (top 5 categories across FR, DE, ES, IT, NL):
- Heatmap shows %CDE varies by country, enabling country-specific launch strategies.
- France dominates sample sizes due to OFF data concentration.

### 10. Opportunity Scoring & Sensitivity (Notebook 05)

**Composite score formula** (6 normalised [0,1] components):
- Nutritional gap (25% weight) — from notebook 03
- Brand fragmentation (15%) — `1 - HHI`
- Category size (15%) — `log(n_products)`, min-max normalised
- Reformulation feasibility (15%) — `100 - min_reduction_pct`, inverted so easier = higher
- PL opportunity (15%) — `1 - pl_penetration`
- Price gap margin (15%) — uniform 0.5 placeholder (no per-category price data from OFF)

**Top 5 opportunities (by composite score)**:
1. **Crepes & Galettes** (0.689): moderate gap (0.84) but highest reformulation feasibility
2. **Condiments & Sauces** (0.672): large market (30K products), gap 0.77
3. **Breakfast** (0.663): highest gap (0.93) but difficult reformulation (84% sugar reduction)
4. **Snacks** (0.657): HUGE market (119K products), gap 0.88
5. **Spreads** (0.655): gap 0.81, moderate market

**Sensitivity analysis** (1000 Monte Carlo simulations with random Dirichlet weights):
- Ranking stability tested — robust top categories remain in top 5 regardless of weight assumptions.
- Weight sensitivity heatmap shows which categories are sensitive to specific factor emphasis.

**Key bug fixed**: `for i, (cat, row)` loop variable shadowed the `cat` DataFrame — renamed to `cat_name`.
**Module fix**: `sensitivity_analysis()` referenced `category_l2` column; updated to auto-detect `category_l1`.

### 11. Findings & Recommendations (Notebook 06)

**Executive summary headline**: 73% of EU food products score C/D/E (unhealthy), while PL penetration among healthy (A/B) products is only ~10%. This creates a clear market opening.

**Top 3 actionable picks** (categories with >=1000 products):
1. **Crepes & Galettes**: Score 0.689, easiest reformulation (37% sugar, 56% sat fat, 27% salt reductions)
2. **Condiments & Sauces**: Score 0.672, large market (31K products), mainly needs salt reduction
3. **Breakfast**: Score 0.663, highest gap but challenging reformulation (84% sugar reduction needed)

**Strategic recommendations split** by retailer type:
- Discount retailers (Lidl, Aldi, Mercadona): focus on Snacks, Condiments, Breakfast — volume play
- Premium supermarkets (AH, Carrefour): focus on Spreads, Crêpes, Desserts — premium health tier

**Outputs**: `results/executive_dashboard.png` (4-panel summary), `results/final_opportunity_map.png`

**All 6 analysis notebooks complete and executing successfully.**
