"""Mercadona (Spain) product catalogue scraper.

Uses the internal REST API at tienda.mercadona.es/api/.
No authentication required — just a valid postal code cookie.

API structure (verified Feb 2026):
    /api/categories/           — returns paginated list of 26 top-level categories,
                                 each containing subcategories with IDs
    /api/categories/{sub_id}/  — returns subcategory detail with nested sub-sub-
                                 categories, each containing a list of products

Product response contains:
    id, display_name, packaging, price_instructions (unit_price, reference_price,
    reference_format, unit_size, size_format), thumbnail, categories, share_url

Limitations:
    - No explicit 'brand' field — brand is embedded in display_name
      (e.g., "Aceite de oliva 0,4º Hacendado")
    - No nutritional data or EAN barcodes
    - Join to Open Food Facts via fuzzy name+brand+weight matching
"""

from __future__ import annotations

import logging
import re

import requests

from src.data.scrapers.base import BaseScraper, Product

logger = logging.getLogger(__name__)

BASE_URL = "https://tienda.mercadona.es/api"

# Mercadona private label brands (lowercase)
MERCADONA_PL_BRANDS = {
    "hacendado", "deliplus", "bosque verde", "compy", "tododia",
    "solcare", "dermik", "cave", "belsia", "alesto", "mercadona",
    "esencia", "dulcesol", "casa juncal", "polesa", "quirus",
    "steinburg", "el pozo", "dia",  # additional PL brands
}

# Non-food categories to skip (we only want food products)
SKIP_CATEGORIES = {
    "limpieza y hogar", "cuidado del cabello", "cuidado facial y corporal",
    "maquillaje", "fitoterapia y parafarmacia", "mascotas",
}


class MercadonaScraper(BaseScraper):
    """Scraper for Mercadona's internal product API."""

    def __init__(self, postal_code: str = "46001", include_non_food: bool = False, **kwargs):
        super().__init__(retailer_name="mercadona", **kwargs)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        })
        self.session.cookies.set("postal_code", postal_code)
        self.include_non_food = include_non_food

    def scrape_categories(self) -> list[dict]:
        """Fetch the subcategory list from Mercadona API.

        Returns only leaf-level subcategory IDs (the ones that contain products),
        along with their parent category name for the category path.
        """
        resp = self._request_with_retry(self.session, f"{BASE_URL}/categories/")
        data = resp.json()

        subcategories = []
        for top_cat in data.get("results", []):
            top_name = top_cat.get("name", "")

            # Skip non-food categories unless explicitly requested
            if not self.include_non_food and top_name.lower() in SKIP_CATEGORIES:
                logger.info("Skipping non-food category: %s", top_name)
                continue

            for subcat in top_cat.get("categories", []):
                subcategories.append({
                    "id": str(subcat["id"]),
                    "name": subcat.get("name", ""),
                    "parent_name": top_name,
                })

        logger.info("Found %d food subcategories to scrape", len(subcategories))
        return subcategories

    def scrape_products(self, category_id: str) -> list[Product]:
        """Fetch all products in a Mercadona subcategory.

        The subcategory endpoint returns further nested sub-sub-categories,
        each containing a products list.
        """
        self._rate_limit()
        resp = self._request_with_retry(
            self.session, f"{BASE_URL}/categories/{category_id}/"
        )
        data = resp.json()

        # Find the parent category name from our category list
        parent_name = ""
        cat_name = data.get("name", "")

        products = []
        for sub in data.get("categories", []):
            sub_name = sub.get("name", "")
            for raw_product in sub.get("products", []):
                products.append(
                    self._parse_product(raw_product, [parent_name, cat_name, sub_name])
                )

        return products

    def run(self) -> "pd.DataFrame":
        """Execute full scrape with category path tracking."""
        import pandas as pd

        logger.info("Starting scrape for %s", self.retailer_name)
        categories = self.scrape_categories()
        logger.info("Found %d subcategories", len(categories))

        for cat in categories:
            products = self.scrape_products(cat["id"])
            # Inject the parent name we stored during category fetch
            for p in products:
                p.category_path[0] = cat["parent_name"]
            self._products.extend(products)
            logger.info(
                "  %s > %s: %d products", cat["parent_name"], cat["name"], len(products)
            )

        df = self.to_dataframe()
        logger.info("Scraped %d total products from %s", len(df), self.retailer_name)
        return df

    def _parse_product(self, raw: dict, category_path: list[str]) -> Product:
        """Convert raw Mercadona API product to a Product record."""
        display_name = raw.get("display_name", "")
        price_info = raw.get("price_instructions", {})

        # Extract brand from display_name (brand is usually the last word(s))
        brand = self._extract_brand(display_name)

        # Parse prices — API returns strings
        unit_price = self._parse_float(price_info.get("unit_price"))
        ref_price = self._parse_float(price_info.get("reference_price"))
        unit_size = price_info.get("unit_size")
        size_format = price_info.get("size_format", "")
        ref_format = price_info.get("reference_format", "")

        return Product(
            retailer="mercadona",
            product_id=str(raw.get("id", "")),
            name=display_name,
            brand=brand,
            price_eur=unit_price,
            unit_price_eur=ref_price,
            unit_price_unit=ref_format or size_format,
            category_path=category_path,
            is_private_label=self._is_private_label(brand),
        )

    @staticmethod
    def _extract_brand(display_name: str) -> str:
        """Extract brand name from Mercadona product display_name.

        Mercadona product names typically end with the brand:
        "Aceite de oliva 0,4º Hacendado" -> "Hacendado"
        "Cerveza Mahou" -> "Mahou"
        """
        # Check for known PL brands anywhere in the name
        name_lower = display_name.lower()
        for pl_brand in MERCADONA_PL_BRANDS:
            if pl_brand in name_lower:
                return pl_brand.title()

        # Fallback: last capitalised word(s) are often the brand
        # This is a heuristic — won't be perfect
        words = display_name.split()
        if len(words) >= 2:
            # Look for the last word that starts with uppercase
            for i in range(len(words) - 1, -1, -1):
                if words[i][0].isupper() and not words[i].replace(",", "").replace(".", "").isdigit():
                    return words[i]
        return ""

    @staticmethod
    def _is_private_label(brand: str) -> bool:
        """Check if a brand is one of Mercadona's private labels."""
        return brand.lower().strip() in MERCADONA_PL_BRANDS

    @staticmethod
    def _parse_float(value) -> float | None:
        """Safely parse a string or number to float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
