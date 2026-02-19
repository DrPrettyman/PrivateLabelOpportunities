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
