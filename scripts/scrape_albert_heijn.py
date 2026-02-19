"""Run the full Albert Heijn product catalogue scrape."""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.scrapers.albert_heijn import AlbertHeijnScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "scraped"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

scraper = AlbertHeijnScraper(request_delay=1.0)
df = scraper.run()

output_path = OUTPUT_DIR / "albert_heijn_products.parquet"
df.to_parquet(output_path, index=False)

print(f"\nSaved {len(df)} products to {output_path}")
print(f"Columns: {list(df.columns)}")
print(f"\nPL vs branded breakdown:")
print(df["is_private_label"].value_counts())
print(f"\nTop 10 brands:")
print(df["brand"].value_counts().head(10))
print(f"\nCategory distribution (top 10):")
cat_counts = df["category_path"].apply(lambda x: x[0] if x else "").value_counts()
print(cat_counts.head(10))
