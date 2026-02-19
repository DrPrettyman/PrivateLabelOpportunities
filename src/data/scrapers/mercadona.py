"""Mercadona (Spain) product catalogue scraper.

Uses the internal REST API at tienda.mercadona.es/api/.
No authentication required — just a valid postal code cookie.

Endpoints:
    /api/categories/           — list all top-level categories
    /api/categories/{id}/      — products per category (3 levels deep)
    /api/products/{id}/        — individual product detail

Private label identification:
    Mercadona's own brands (Hacendado, Deliplus, Bosque Verde, etc.)
    dominate ~50% of shelves. Brand field in API response makes PL
    identification straightforward.

Limitation:
    API does NOT return nutritional data or EAN barcodes.
    Join to Open Food Facts via fuzzy name+brand+weight matching.
"""

from __future__ import annotations

import logging

import requests

from src.data.scrapers.base import BaseScraper, Product

logger = logging.getLogger(__name__)

BASE_URL = "https://tienda.mercadona.es/api"

# Mercadona private label brands
MERCADONA_PL_BRANDS = {
    "hacendado", "deliplus", "bosque verde", "compy", "tododia",
    "solcare", "dermik", "cave", "belsia", "alesto",
}


class MercadonaScraper(BaseScraper):
    """Scraper for Mercadona's internal product API."""

    def __init__(self, postal_code: str = "46001", **kwargs):
        super().__init__(retailer_name="mercadona", **kwargs)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; research-project)",
        })
        self.session.cookies.set("postal_code", postal_code)

    def scrape_categories(self) -> list[dict]:
        """Fetch full category tree from Mercadona API."""
        resp = self._request_with_retry(self.session, f"{BASE_URL}/categories/")
        data = resp.json()
        categories = []
        for cat in data.get("results", data) if isinstance(data, dict) else data:
            categories.append({"id": str(cat["id"]), "name": cat.get("name", "")})
            for subcat in cat.get("categories", []):
                categories.append({"id": str(subcat["id"]), "name": subcat.get("name", "")})
        return categories

    def scrape_products(self, category_id: str) -> list[Product]:
        """Fetch all products in a Mercadona category."""
        self._rate_limit()
        resp = self._request_with_retry(
            self.session, f"{BASE_URL}/categories/{category_id}/"
        )
        data = resp.json()
        products = []
        for cat in data.get("categories", [data]):
            for prod in cat.get("products", []):
                products.append(self._parse_product(prod, category_id))
        return products

    def _parse_product(self, raw: dict, category_id: str) -> Product:
        """Convert raw API response to a Product record."""
        brand = raw.get("brand", "")
        price_info = raw.get("price_instructions", {})
        return Product(
            retailer="mercadona",
            product_id=str(raw.get("id", "")),
            name=raw.get("display_name", ""),
            brand=brand,
            price_eur=price_info.get("unit_price"),
            unit_price_eur=price_info.get("reference_price"),
            unit_price_unit=price_info.get("reference_format"),
            category_path=[category_id],
            is_private_label=self._is_private_label(brand),
        )

    @staticmethod
    def _is_private_label(brand: str) -> bool:
        """Check if a brand is one of Mercadona's private labels."""
        return brand.lower().strip() in MERCADONA_PL_BRANDS
