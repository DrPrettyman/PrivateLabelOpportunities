"""Jumbo (Netherlands) product catalogue scraper.

Tier 2 (supplementary). Internal mobile API, no auth required.
Supported by the SupermarktConnector Python package.

Value: Paired with Albert Heijn, gives two competing retailers in the
same country — enables same-product price comparison.
"""

from __future__ import annotations

from src.data.scrapers.base import BaseScraper, Product


class JumboScraper(BaseScraper):
    """Scraper for Jumbo NL mobile API."""

    def __init__(self, **kwargs):
        super().__init__(retailer_name="jumbo", **kwargs)

    def scrape_categories(self) -> list[dict]:
        raise NotImplementedError("Jumbo scraper pending implementation")

    def scrape_products(self, category_id: str) -> list[Product]:
        raise NotImplementedError("Jumbo scraper pending implementation")
