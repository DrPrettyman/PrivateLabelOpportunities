"""Carrefour (France/Spain) product catalogue scraper.

Web scraping of carrefour.fr or carrefour.es product pages.
No clean internal API — the site uses dynamic JS rendering.

Private label identification:
    "Carrefour", "Carrefour Bio", "Carrefour Classic", "Simpl" (budget tier).

Complexity note:
    Hardest to scrape of the three primary targets — anti-bot measures,
    dynamic rendering. Demonstrates handling of real-world scraping challenges.
"""

from __future__ import annotations

import logging

from src.data.scrapers.base import BaseScraper, Product

logger = logging.getLogger(__name__)

CARREFOUR_PL_BRANDS = {
    "carrefour", "carrefour bio", "carrefour classic", "carrefour extra",
    "simpl", "carrefour veggie", "carrefour no gluten",
}


class CarrefourScraper(BaseScraper):
    """Scraper for Carrefour product pages."""

    def __init__(self, country: str = "fr", **kwargs):
        super().__init__(retailer_name=f"carrefour_{country}", request_delay=2.0, **kwargs)
        self.country = country
        self.base_url = f"https://www.carrefour.{country}"

    def scrape_categories(self) -> list[dict]:
        """Crawl category tree from Carrefour website."""
        raise NotImplementedError("Carrefour scraper pending implementation")

    def scrape_products(self, category_id: str) -> list[Product]:
        """Scrape products from a Carrefour category page."""
        raise NotImplementedError("Carrefour scraper pending implementation")

    @staticmethod
    def _is_private_label(brand: str) -> bool:
        """Check if a brand is a Carrefour private label."""
        return brand.lower().strip() in CARREFOUR_PL_BRANDS
