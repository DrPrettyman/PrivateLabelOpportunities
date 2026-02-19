"""Download Open Food Facts EU data.

Strategy: Download the full Parquet file first, then filter locally with DuckDB.
This avoids the HTTP 429 rate limiting that occurs with DuckDB's remote Parquet
streaming (which makes many range requests).

Usage:
    python scripts/download_off.py
"""

import duckdb
import time
import urllib.request
from pathlib import Path

OFF_PARQUET_URL = (
    "https://huggingface.co/datasets/openfoodfacts/product-database"
    "/resolve/main/food.parquet?download=true"
)

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw"

# EU country tags as used in OFF (en:<country-name>)
EU_COUNTRY_TAGS = [
    "en:france", "en:germany", "en:spain", "en:italy", "en:netherlands",
    "en:belgium", "en:portugal", "en:austria", "en:ireland", "en:greece",
    "en:poland", "en:sweden", "en:denmark", "en:finland",
    "en:czech-republic", "en:romania", "en:hungary", "en:bulgaria",
    "en:croatia", "en:slovakia", "en:slovenia", "en:lithuania",
    "en:latvia", "en:estonia", "en:luxembourg", "en:malta", "en:cyprus",
]

# Nutrients to extract from the nested struct
NUTRIENTS_TO_EXTRACT = {
    "energy-kcal": "energy_kcal_100g",
    "fat": "fat_100g",
    "saturated-fat": "saturated_fat_100g",
    "sugars": "sugars_100g",
    "salt": "salt_100g",
    "fiber": "fiber_100g",
    "proteins": "proteins_100g",
    "carbohydrates": "carbohydrates_100g",
    "sodium": "sodium_100g",
}


def download_with_progress(url: str, dest: Path) -> None:
    """Download a file with progress reporting."""
    print(f"Downloading {url}")
    print(f"Destination: {dest}")

    def report(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(downloaded / total_size * 100, 100)
            mb_done = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            print(f"\r  {mb_done:.0f}/{mb_total:.0f} MB ({pct:.1f}%)", end="", flush=True)

    urllib.request.urlretrieve(url, dest, reporthook=report)
    print()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    full_path = OUTPUT_DIR / "off_full.parquet"
    output_path = OUTPUT_DIR / "off_eu.parquet"

    # Step 1: Download full file if not already present
    if not full_path.exists():
        print("Step 1: Downloading full Open Food Facts Parquet...")
        start = time.time()
        download_with_progress(OFF_PARQUET_URL, full_path)
        elapsed = time.time() - start
        size_mb = full_path.stat().st_size / (1024 * 1024)
        print(f"Downloaded {size_mb:.0f} MB in {elapsed:.0f}s")
    else:
        size_mb = full_path.stat().st_size / (1024 * 1024)
        print(f"Step 1: Full file already exists ({size_mb:.0f} MB), skipping download")

    # Step 2: Filter to EU countries and extract nutrients
    print("\nStep 2: Filtering to EU countries and extracting nutrients...")
    con = duckdb.connect()

    country_filters = " OR ".join(
        f"list_contains(countries_tags, '{tag}')" for tag in EU_COUNTRY_TAGS
    )

    nutrient_selects = []
    for nutrient_name, col_name in NUTRIENTS_TO_EXTRACT.items():
        nutrient_selects.append(
            f"""(list_extract(list_filter(nutriments, x -> x.name = '{nutrient_name}'), 1))."100g" AS "{col_name}" """
        )
    nutrient_sql = ",\n        ".join(nutrient_selects)

    start = time.time()
    con.execute(f"""
        COPY (
            SELECT
                code,
                product_name,
                brands,
                brands_tags,
                categories_tags,
                countries_tags,
                nutriscore_grade,
                nutriscore_score,
                nova_group,
                labels_tags,
                stores_tags,
                quantity,
                product_quantity,
                unique_scans_n,
                {nutrient_sql}
            FROM read_parquet('{full_path}')
            WHERE {country_filters}
        ) TO '{output_path}' (FORMAT 'parquet', COMPRESSION 'zstd')
    """)
    elapsed = time.time() - start

    # Verify
    count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{output_path}')").fetchone()[0]
    file_size_mb = output_path.stat().st_size / (1024 * 1024)

    print(f"\nDone in {elapsed:.0f}s")
    print(f"Saved {count:,} EU products to {output_path}")
    print(f"File size: {file_size_mb:.1f} MB")

    # Country distribution
    print("\nProducts per country (top 10):")
    country_dist = con.execute(f"""
        SELECT country, COUNT(*) as n
        FROM (
            SELECT UNNEST(countries_tags) AS country
            FROM read_parquet('{output_path}')
        )
        GROUP BY country
        ORDER BY n DESC
        LIMIT 10
    """).fetchall()
    for country, n in country_dist:
        print(f"  {country}: {n:,}")

    # Nutri-Score coverage
    ns = con.execute(f"""
        SELECT
            COUNT(*) as total,
            COUNT(nutriscore_grade) as has_nutriscore,
            COUNT(nova_group) as has_nova
        FROM read_parquet('{output_path}')
    """).fetchone()
    print(f"\nNutri-Score coverage: {ns[1]:,}/{ns[0]:,} ({ns[1]/ns[0]*100:.1f}%)")
    print(f"NOVA coverage: {ns[2]:,}/{ns[0]:,} ({ns[2]/ns[0]*100:.1f}%)")

    # Optionally remove full file to save space
    # full_path.unlink()
    # print(f"\nRemoved full file to save disk space")

    con.close()


if __name__ == "__main__":
    main()
