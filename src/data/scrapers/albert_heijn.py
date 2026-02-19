"""Albert Heijn (Netherlands) product catalogue scraper.

Uses the mobile API at api.ah.nl/mobile-services/.
Anonymous token obtainable via POST to /mobile-auth/v1/auth/token/anonymous
with body {"clientId": "appie"}.

API structure (verified Feb 2026):
    /mobile-services/product/search/v2
        - params: query, size (max 100), page, taxonomyId
        - returns: products list, page info, filters (with taxonomy categories)

Product fields from search:
    webshopId, title, brand, priceBeforeBonus, unitPriceDescription,
    mainCategory, subCategory, salesUnitSize, nutriscore (A-E),
    propertyIcons, images

Private label identification:
    AH's brands (AH, AH Biologisch, AH Excellent, AH Terra) are clearly
    labelled in the brand field. AH brand alone has 6,135+ products.

Limitation:
    No EAN barcode or detailed nutrition in search results.
    Nutriscore grade IS available. Join to OFF via fuzzy name matching.
"""

from __future__ import annotations

import logging
import re

import requests

from src.data.scrapers.base import BaseScraper, Product

logger = logging.getLogger(__name__)

AUTH_URL = "https://api.ah.nl/mobile-auth/v1/auth/token/anonymous"
API_BASE = "https://api.ah.nl/mobile-services"

AH_PL_BRANDS = {"ah", "ah biologisch", "ah excellent", "ah terra", "ah basic"}

# Non-food taxonomy categories to skip
AH_SKIP_CATEGORIES = {
    "lichaamsverzorging", "haarverzorging", "zelfzorg", "mondhygiene",
    "deodorant", "bad en douche", "intieme hygiëne", "gezichtsverzorging",
    "shampoo", "wasmiddelen, wasverzachters", "wasmiddel",
    "schoonmaakmiddelen", "toiletreinigers & verfrissers", "kaarsen",
    "katten", "honden", "nat kattenvoer", "supplementen",
    "vitamines & mineralen", "sportvoeding",
}


class AlbertHeijnScraper(BaseScraper):
    """Scraper for Albert Heijn's mobile API."""

    def __init__(self, include_non_food: bool = False, **kwargs):
        kwargs.setdefault("request_delay", 1.0)
        super().__init__(retailer_name="albert_heijn", **kwargs)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Appie/8.22.3",
            "x-application": "AHWEBSHOP",
        })
        self._token: str | None = None
        self.include_non_food = include_non_food

    def _authenticate(self) -> None:
        """Obtain an anonymous access token."""
        resp = self.session.post(AUTH_URL, json={"clientId": "appie"})
        resp.raise_for_status()
        self._token = resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self._token}"})
        logger.info("Obtained anonymous AH token")

    def scrape_categories(self) -> list[dict]:
        """Fetch taxonomy categories from the search API filters."""
        if not self._token:
            self._authenticate()

        resp = self._request_with_retry(
            self.session,
            f"{API_BASE}/product/search/v2",
            params={"size": 1, "page": 0},
        )
        data = resp.json()

        taxonomy_filter = next(
            (f for f in data.get("filters", []) if f.get("type") == "TAXONOMY"),
            None,
        )
        if not taxonomy_filter:
            logger.warning("No TAXONOMY filter found in AH search response")
            return []

        categories = []
        for opt in taxonomy_filter.get("options", []):
            name = opt.get("label", "").lower()
            if not self.include_non_food and name in AH_SKIP_CATEGORIES:
                logger.info("Skipping non-food category: %s", opt.get("label"))
                continue
            categories.append({
                "id": str(opt["id"]),
                "name": opt.get("label", ""),
                "count": opt.get("count", 0),
            })

        logger.info("Found %d food taxonomy categories", len(categories))
        return categories

    def scrape_products(self, category_id: str) -> list[Product]:
        """Fetch all products in an AH taxonomy category via pagination."""
        if not self._token:
            self._authenticate()

        products = []
        page = 0

        while True:
            self._rate_limit()
            resp = self._request_with_retry(
                self.session,
                f"{API_BASE}/product/search/v2",
                params={"taxonomyId": category_id, "size": 100, "page": page},
            )
            data = resp.json()

            for raw in data.get("products", []):
                products.append(self._parse_product(raw))

            page_info = data.get("page", {})
            total_pages = page_info.get("totalPages", 0)

            if page >= total_pages - 1:
                break
            page += 1

        return products

    def run(self) -> "pd.DataFrame":
        """Execute full AH scrape."""
        import pandas as pd

        logger.info("Starting scrape for %s", self.retailer_name)
        categories = self.scrape_categories()
        logger.info("Found %d categories to scrape", len(categories))

        for cat in categories:
            products = self.scrape_products(cat["id"])
            self._products.extend(products)
            logger.info(
                "  %s (id=%s): %d products (expected ~%d)",
                cat["name"], cat["id"], len(products), cat["count"],
            )

        # Deduplicate — products may appear in multiple taxonomy categories
        df = self.to_dataframe()
        before_dedup = len(df)
        df = df.drop_duplicates(subset=["product_id"])
        logger.info(
            "Scraped %d total products (%d after dedup) from %s",
            before_dedup, len(df), self.retailer_name,
        )
        return df

    def _parse_product(self, raw: dict) -> Product:
        """Convert raw AH search result to a Product record."""
        brand = raw.get("brand", "") or ""
        price = raw.get("priceBeforeBonus")
        nutriscore = raw.get("nutriscore")

        # Parse unit price from description like "prijs per liter €0.95"
        unit_price, unit = self._parse_unit_price(raw.get("unitPriceDescription", ""))

        return Product(
            retailer="albert_heijn",
            product_id=str(raw.get("webshopId", "")),
            name=raw.get("title", ""),
            brand=brand,
            price_eur=price,
            unit_price_eur=unit_price,
            unit_price_unit=unit,
            category_path=[
                raw.get("mainCategory", ""),
                raw.get("subCategory", ""),
            ],
            is_private_label=self._is_private_label(brand),
        )

    @staticmethod
    def _parse_unit_price(description: str) -> tuple[float | None, str | None]:
        """Parse 'prijs per liter €0.95' into (0.95, 'liter')."""
        if not description:
            return None, None
        match = re.search(r"per\s+(\w+)\s+€\s*([\d.,]+)", description)
        if match:
            unit = match.group(1)
            try:
                value = float(match.group(2).replace(",", "."))
                return value, unit
            except ValueError:
                return None, unit
        return None, None

    @staticmethod
    def _is_private_label(brand: str) -> bool:
        """Check if a brand is Albert Heijn private label."""
        return brand.lower().strip() in AH_PL_BRANDS
