"""Elicitation agent: turns a loose request into a structured ShoppingQuery
by asking a short round of clarifying questions, the way a sales associate
would, instead of expecting the user to already know what to specify.

Each follow-up question maps its answer straight into the field it asked
about. Only the initial free-form request is scanned across all fields,
since at that point we don't know which attributes the user volunteered.
Scanning a targeted answer (e.g. the reply to "indoor or outdoor?") against
every field's keywords risks a word like "outside" in an *occasion* answer
being mistaken for the *setting* answer -- so targeted answers are never
run back through the multi-field scanner.
"""

from __future__ import annotations

from collections.abc import Callable

from scout.catalog import detect_item_type
from scout.models import ShoppingQuery

_OCCASION_KEYWORDS = ["wedding", "interview", "date", "funeral", "graduation", "party", "work"]
_SETTING_KEYWORDS = {"outdoor": ["outdoor", "outside"], "indoor": ["indoor", "inside"]}
_SEASON_KEYWORDS = ["fall", "autumn", "winter", "spring", "summer", "cold", "warm", "hot"]
_FORMALITY_KEYWORDS = ["formal", "semi-formal", "casual", "black tie"]

Ask = Callable[[str], str]


def run(raw_request: str, ask: Ask) -> ShoppingQuery:
    """Build a ShoppingQuery from the initial request, asking a follow-up
    for each attribute that wasn't already stated.
    """
    query = ShoppingQuery(raw_request=raw_request)
    query.item_type = detect_item_type(raw_request)
    query.occasion = _find_keyword(raw_request, _OCCASION_KEYWORDS)
    query.setting = _find_setting(raw_request)
    query.season_or_weather = _find_keyword(raw_request, _SEASON_KEYWORDS)
    query.formality = _find_keyword(raw_request, _FORMALITY_KEYWORDS)

    if not query.item_type:
        answer = ask("What kind of item are you looking for -- a dress, jeans, a top, a suit?")
        query.item_type = detect_item_type(answer) or answer.strip() or None

    if not query.occasion:
        answer = ask("What's the occasion you're shopping for?")
        query.occasion = answer.strip() or None

    if not query.setting:
        answer = ask("Will it be mostly indoors or outdoors?")
        query.setting = _find_setting(answer) or answer.strip() or None

    if not query.season_or_weather:
        answer = ask("What season or weather should it work for?")
        query.season_or_weather = _find_keyword(answer, _SEASON_KEYWORDS) or answer.strip() or None

    if not query.formality:
        answer = ask("How formal are you thinking -- casual, semi-formal, or formal?")
        query.formality = _find_keyword(answer, _FORMALITY_KEYWORDS) or answer.strip() or None

    return query


def _find_keyword(text: str, keywords: list[str]) -> str | None:
    lowered = text.lower()
    for kw in keywords:
        if kw in lowered:
            return kw
    return None


def _find_setting(text: str) -> str | None:
    lowered = text.lower()
    for canonical, synonyms in _SETTING_KEYWORDS.items():
        if any(s in lowered for s in synonyms):
            return canonical
    return None
