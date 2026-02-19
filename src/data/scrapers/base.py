"""Abstract base class for supermarket scrapers.

Provides shared infrastructure: rate limiting, retry logic, output schema
validation, progress tracking, and respectful crawling behaviour.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@dataclass
class Product:
    """Unified product record from any supermarket scraper."""

    retailer: str
    product_id: str
    name: str
    brand: str | None = None
    price_eur: float | None = None
    unit_price_eur: float | None = None
    unit_price_unit: str | None = None  # e.g. "kg", "l"
    category_path: list[str] = field(default_factory=list)
    ean: str | None = None
    # Nutritional data (per 100g) — not all retailers provide this
    energy_kcal_100g: float | None = None
    fat_100g: float | None = None
    saturated_fat_100g: float | None = None
    sugars_100g: float | None = None
    salt_100g: float | None = None
    fiber_100g: float | None = None
    proteins_100g: float | None = None
    is_private_label: bool | None = None


class BaseScraper(ABC):
    """Abstract base for all supermarket scrapers."""

    def __init__(
        self,
        retailer_name: str,
        request_delay: float = 1.5,
        output_dir: Path | None = None,
    ):
        self.retailer_name = retailer_name
        self.request_delay = request_delay
        self.output_dir = output_dir or Path("data/scraped")
        self._products: list[Product] = []

    @abstractmethod
    def scrape_categories(self) -> list[dict]:
        """Fetch the full category tree from the retailer."""
        ...

    @abstractmethod
    def scrape_products(self, category_id: str) -> list[Product]:
        """Fetch all products in a given category."""
        ...

    def run(self) -> pd.DataFrame:
        """Execute full scrape: categories -> products -> DataFrame."""
        logger.info("Starting scrape for %s", self.retailer_name)
        categories = self.scrape_categories()
        logger.info("Found %d categories", len(categories))

        for cat in categories:
            products = self.scrape_products(cat["id"])
            self._products.extend(products)
            self._rate_limit()

        df = self.to_dataframe()
        logger.info("Scraped %d products from %s", len(df), self.retailer_name)
        return df

    def to_dataframe(self) -> pd.DataFrame:
        """Convert collected products to a DataFrame."""
        return pd.DataFrame([p.__dict__ for p in self._products])

    def _rate_limit(self) -> None:
        """Sleep between requests to respect the retailer's servers."""
        time.sleep(self.request_delay)

    @staticmethod
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _request_with_retry(session, url: str, **kwargs):
        """Make an HTTP request with exponential backoff retry."""
        response = session.get(url, **kwargs)
        response.raise_for_status()
        return response
