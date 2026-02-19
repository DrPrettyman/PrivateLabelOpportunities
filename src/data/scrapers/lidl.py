"""Lidl (Germany/Spain/EU) product catalogue scraper.

Tier 2 (supplementary). Web scraping of country-specific Lidl sites.
~80%+ own-brand assortment makes Lidl valuable as the "endpoint" of a
full private label strategy.

Limitation: Online catalogue may underrepresent in-store food range.
"""

from __future__ import annotations

from src.data.scrapers.base import BaseScraper, Product


class LidlScraper(BaseScraper):
    """Scraper for Lidl product pages."""

    def __init__(self, country: str = "de", **kwargs):
        super().__init__(retailer_name=f"lidl_{country}", request_delay=2.0, **kwargs)
        self.country = country

    def scrape_categories(self) -> list[dict]:
        raise NotImplementedError("Lidl scraper pending implementation")

    def scrape_products(self, category_id: str) -> list[Product]:
        raise NotImplementedError("Lidl scraper pending implementation")
