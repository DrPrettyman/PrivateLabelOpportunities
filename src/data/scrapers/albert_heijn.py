"""Albert Heijn (Netherlands) product catalogue scraper.

Uses the undocumented mobile API at api.ah.nl/mobile-services/.
Anonymous token obtainable via POST to /mobile-auth/v1/auth/token/anonymous.

Key advantage:
    AH returns EAN barcodes AND full nutritional data directly,
    enabling high-confidence joins to Open Food Facts and cross-validation
    of nutritional values.

Private label identification:
    AH's "AH" and "AH Biologisch" brands are clearly labelled in the
    brand field.
"""

from __future__ import annotations

import logging

import requests

from src.data.scrapers.base import BaseScraper, Product

logger = logging.getLogger(__name__)

AUTH_URL = "https://api.ah.nl/mobile-auth/v1/auth/token/anonymous"
API_BASE = "https://api.ah.nl/mobile-services"

AH_PL_PREFIXES = ("ah ", "ah-")


class AlbertHeijnScraper(BaseScraper):
    """Scraper for Albert Heijn's mobile API."""

    def __init__(self, **kwargs):
        super().__init__(retailer_name="albert_heijn", **kwargs)
        self.session = requests.Session()
        self._token: str | None = None

    def _authenticate(self) -> None:
        """Obtain an anonymous access token."""
        resp = self.session.post(AUTH_URL, json={})
        resp.raise_for_status()
        self._token = resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self._token}"})
        logger.info("Obtained anonymous AH token")

    def scrape_categories(self) -> list[dict]:
        """Fetch category tree from AH API."""
        if not self._token:
            self._authenticate()
        resp = self._request_with_retry(
            self.session, f"{API_BASE}/product/search/v2",
            params={"query": "", "size": 0},
        )
        # Extract taxonomy from response
        data = resp.json()
        categories = []
        for taxonomy in data.get("taxonomies", []):
            for item in taxonomy.get("children", []):
                categories.append({"id": str(item.get("id", "")), "name": item.get("name", "")})
        return categories

    def scrape_products(self, category_id: str) -> list[Product]:
        """Fetch all products in an AH category."""
        if not self._token:
            self._authenticate()
        self._rate_limit()

        products = []
        page = 0
        while True:
            resp = self._request_with_retry(
                self.session, f"{API_BASE}/product/search/v2",
                params={"taxonomyId": category_id, "size": 100, "page": page},
            )
            data = resp.json()
            for item in data.get("products", []):
                products.append(self._parse_product(item, category_id))
            if page >= data.get("page", {}).get("totalPages", 0) - 1:
                break
            page += 1
            self._rate_limit()

        return products

    def _parse_product(self, raw: dict, category_id: str) -> Product:
        """Convert raw AH API response to a Product record."""
        brand = raw.get("brand", "")
        nutrition = raw.get("nutritionInfo", {})
        return Product(
            retailer="albert_heijn",
            product_id=str(raw.get("webshopId", "")),
            name=raw.get("title", ""),
            brand=brand,
            price_eur=raw.get("priceBeforeBonus", raw.get("currentPrice")),
            unit_price_eur=raw.get("unitPriceDescription"),
            category_path=[category_id],
            ean=raw.get("gtin"),
            energy_kcal_100g=self._extract_nutrient(nutrition, "energy"),
            fat_100g=self._extract_nutrient(nutrition, "fat"),
            saturated_fat_100g=self._extract_nutrient(nutrition, "saturatedFat"),
            sugars_100g=self._extract_nutrient(nutrition, "sugars"),
            salt_100g=self._extract_nutrient(nutrition, "salt"),
            fiber_100g=self._extract_nutrient(nutrition, "fiber"),
            proteins_100g=self._extract_nutrient(nutrition, "protein"),
            is_private_label=self._is_private_label(brand),
        )

    @staticmethod
    def _extract_nutrient(nutrition: dict, key: str) -> float | None:
        """Extract a nutrient value from AH nutrition info dict."""
        for item in nutrition.get("nutrients", []):
            if item.get("name", "").lower().startswith(key.lower()):
                try:
                    return float(item.get("value", 0))
                except (ValueError, TypeError):
                    return None
        return None

    @staticmethod
    def _is_private_label(brand: str) -> bool:
        """Check if a brand is Albert Heijn private label."""
        lower = brand.lower().strip()
        return lower.startswith(AH_PL_PREFIXES) or lower == "ah"
