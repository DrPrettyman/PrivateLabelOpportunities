"""Supermarket product catalogue scrapers.

Each scraper inherits from BaseScraper and implements a consistent
interface for collecting product data (name, brand, price, category,
and optionally EAN barcode + nutritional data) from European retailers.
"""

from src.data.scrapers.base import BaseScraper

__all__ = ["BaseScraper"]
