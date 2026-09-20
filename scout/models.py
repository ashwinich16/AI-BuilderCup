"""Data structures shared across Scout's agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Review:
    rating: int
    text: str


@dataclass
class Product:
    id: str
    name: str
    category: str
    price: float
    color: str
    fabric: str
    silhouette: str
    sleeve_length: str
    formality: str
    occasion_tags: list[str]
    weather_notes: str
    image_descriptions: list[str]
    reviews: list[Review]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Product":
        return cls(
            id=data["id"],
            name=data["name"],
            category=data["category"],
            price=data["price"],
            color=data["color"],
            fabric=data["fabric"],
            silhouette=data["silhouette"],
            sleeve_length=data["sleeve_length"],
            formality=data["formality"],
            occasion_tags=data["occasion_tags"],
            weather_notes=data["weather_notes"],
            image_descriptions=data["image_descriptions"],
            reviews=[Review(**r) for r in data["reviews"]],
        )


@dataclass
class ShoppingQuery:
    """The structured need built up by the elicitation agent."""

    raw_request: str
    item_type: str | None = None  # canonical catalog category, e.g. "dress", "jeans"
    occasion: str | None = None
    setting: str | None = None  # e.g. "outdoor", "indoor"
    season_or_weather: str | None = None
    formality: str | None = None
    other_notes: list[str] = field(default_factory=list)


@dataclass
class PreferenceEvent:
    """One remembered decision, with the reasoning behind it."""

    timestamp: str
    product_id: str
    product_name: str
    decision: str  # "accepted" | "rejected"
    reason: str

    @classmethod
    def now(cls, product_id: str, product_name: str, decision: str, reason: str) -> "PreferenceEvent":
        return cls(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            product_id=product_id,
            product_name=product_name,
            decision=decision,
            reason=reason,
        )
