"""Loads the mocked product catalog and runs candidate filtering.

This stands in for a real product-search backend. The elicitation agent's
structured query narrows the catalog down to a short candidate list before
the comparison agent reasons over each candidate in depth.

Garment category is a hard filter, not a scored preference: if the user
asked for jeans and the catalog has none, we say so honestly rather than
recommending a dress because it scored highest among "everything."
"""

from __future__ import annotations

import json
from pathlib import Path

from scout.models import Product, ShoppingQuery

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"

# Maps a canonical catalog category to the words a shopper might use for it.
CATEGORY_SYNONYMS: dict[str, list[str]] = {
    "dress": ["dress", "gown", "sundress"],
    "suit": ["suit", "blazer set", "pantsuit"],
    "jeans": ["jeans", "denim", "denim pants"],
    "top": ["top", "blouse", "shirt", "button-down", "button down", "knit top"],
}


def load_catalog(path: Path = CATALOG_PATH) -> list[Product]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return [Product.from_dict(item) for item in raw]


def available_categories(catalog: list[Product]) -> list[str]:
    seen: list[str] = []
    for product in catalog:
        if product.category not in seen:
            seen.append(product.category)
    return seen


def detect_item_type(text: str) -> str | None:
    """Match free text against known catalog categories and their synonyms."""
    lowered = text.lower()
    for category, synonyms in CATEGORY_SYNONYMS.items():
        for synonym in synonyms:
            if synonym in lowered:
                return category
    return None


def find_candidates(query: ShoppingQuery, catalog: list[Product], limit: int = 4) -> list[Product]:
    """Score products against the structured query and return the top matches.

    Returns an empty list if the requested item_type isn't in the catalog at
    all -- callers should treat that as "we don't carry that," not as "no
    great matches," and not silently substitute unrelated categories.
    """
    pool = catalog
    if query.item_type:
        pool = [p for p in catalog if p.category == query.item_type]
        if not pool:
            return []

    scored = [(_score(query, p), p) for p in pool]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [product for _, product in scored[:limit]]


def _score(query: ShoppingQuery, product: Product) -> float:
    score = 1.0  # baseline so an unfiltered query still returns everything
    tags = " ".join(product.occasion_tags).lower()

    if query.occasion and query.occasion.lower() in tags:
        score += 3
    if query.setting and query.setting.lower() in tags:
        score += 2
    if query.season_or_weather and query.season_or_weather.lower() in (tags + " " + product.weather_notes.lower()):
        score += 2
    if query.formality and query.formality.lower() in product.formality.lower():
        score += 1
    return score
