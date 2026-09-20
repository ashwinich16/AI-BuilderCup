"""Persistent taste profile: remembers *why* the user accepted or rejected
products, so that reasoning generalizes to products it has never seen.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from scout.models import PreferenceEvent

MEMORY_PATH = Path(__file__).resolve().parent.parent / "data" / "user_memory.json"


class PreferenceMemory:
    def __init__(self, path: Path = MEMORY_PATH):
        self.path = path
        self.events: list[PreferenceEvent] = self._load()

    def _load(self) -> list[PreferenceEvent]:
        if not self.path.exists():
            return []
        with open(self.path, encoding="utf-8") as f:
            raw = json.load(f)
        return [PreferenceEvent(**item) for item in raw]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump([vars(e) for e in self.events], f, indent=2)

    def record(self, product_id: str, product_name: str, decision: str, reason: str) -> None:
        self.events.append(PreferenceEvent.now(product_id, product_name, decision, reason))
        self._save()

    def liked_reasons(self) -> list[str]:
        return [e.reason for e in self.events if e.decision == "accepted" and e.reason]

    def disliked_reasons(self) -> list[str]:
        return [e.reason for e in self.events if e.decision == "rejected" and e.reason]

    def summary(self) -> str:
        """A short natural-language taste profile built from remembered reasons."""
        if not self.events:
            return "No remembered preferences yet."
        liked = _dedupe_recent(self.liked_reasons())
        disliked = _dedupe_recent(self.disliked_reasons())
        parts = []
        if liked:
            parts.append("Tends to like: " + "; ".join(liked[-3:]))
        if disliked:
            parts.append("Tends to avoid: " + "; ".join(disliked[-3:]))
        return " | ".join(parts)

    def rejection_keyword_counts(self) -> Counter:
        """Crude keyword frequency over rejection reasons, used to down-rank
        candidates that share language with past rejections (e.g. "itchy",
        "too tight") when Gemini isn't available to reason over it directly.
        """
        counts: Counter = Counter()
        for reason in self.disliked_reasons():
            for word in reason.lower().split():
                cleaned = word.strip(".,!?")
                if len(cleaned) > 3:
                    counts[cleaned] += 1
        return counts


def _dedupe_recent(reasons: list[str]) -> list[str]:
    """Drop consecutive duplicate reasons (e.g. one rejection reason applied
    to every candidate in a batch) while preserving order.
    """
    deduped: list[str] = []
    for reason in reasons:
        if not deduped or deduped[-1] != reason:
            deduped.append(reason)
    return deduped
