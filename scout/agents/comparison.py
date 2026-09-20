"""Comparison agent: reasons jointly over each candidate's images, specs,
and reviews against the query and the user's remembered preferences, and
produces the deltas that actually matter for this decision.

When GEMINI_API_KEY is set, the joint reasoning (image descriptions + specs
+ reviews + taste profile -> strengths/concerns) is delegated to Gemini.
Otherwise a rule-based pass over the same fields produces a comparable,
if less nuanced, result -- so the pipeline runs end-to-end either way.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from scout import gemini_client
from scout.memory import PreferenceMemory
from scout.models import Product, ShoppingQuery


@dataclass
class ComparisonResult:
    product: Product
    fit_score: float
    strengths: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)


def compare(candidates: list[Product], query: ShoppingQuery, memory: PreferenceMemory) -> list[ComparisonResult]:
    results = [_evaluate_one(p, query, memory) for p in candidates]
    results.sort(key=lambda r: r.fit_score, reverse=True)
    return results


def _evaluate_one(product: Product, query: ShoppingQuery, memory: PreferenceMemory) -> ComparisonResult:
    if gemini_client.is_live():
        return _evaluate_with_gemini(product, query, memory)
    return _evaluate_with_rules(product, query, memory)


def _evaluate_with_rules(product: Product, query: ShoppingQuery, memory: PreferenceMemory) -> ComparisonResult:
    score = 5.0
    strengths: list[str] = []
    concerns: list[str] = []

    weather = (query.season_or_weather or "").lower()
    notes = product.weather_notes.lower()
    if weather in ("fall", "autumn", "winter", "cold") and "warm" in notes:
        score += 2
        strengths.append(f"warm enough for {query.season_or_weather} weather per its weather notes")
    if weather in ("fall", "autumn", "winter", "cold") and ("lightweight" in notes or "breathable" in notes):
        score -= 2
        concerns.append("fabric reads lightweight, may run cold for the weather you described")

    if query.setting and query.setting.lower() == "outdoor":
        if "wind" in notes and "not wind-resistant" not in notes:
            score += 1
            strengths.append("holds up in wind per its weather notes")
        if "flows a lot in wind" in notes or "not wind-resistant" in notes:
            score -= 1
            concerns.append("may not hold up well in outdoor wind")

    review_texts = " ".join(r.text.lower() for r in product.reviews)
    positive_reviews = [r for r in product.reviews if r.rating >= 4]
    if len(positive_reviews) >= 2:
        score += 1
        strengths.append(f"{len(positive_reviews)} of {len(product.reviews)} reviewers rated it 4 stars or higher")

    rejection_counts = memory.rejection_keyword_counts()
    for word, count in rejection_counts.items():
        if word in review_texts or word in notes or word in product.fabric.lower():
            score -= 1
            concerns.append(f"reviews mention '{word}', which you've flagged as a dealbreaker before")

    for image_desc in product.image_descriptions:
        lowered = image_desc.lower()
        if "structured" in lowered or "tailored" in lowered:
            strengths.append("visually structured silhouette rather than clingy or shapeless")

    return ComparisonResult(product=product, fit_score=score, strengths=strengths, concerns=concerns)


def _evaluate_with_gemini(product: Product, query: ShoppingQuery, memory: PreferenceMemory) -> ComparisonResult:
    prompt = f"""You are a personal shopping assistant for a blind or low-vision user.
Evaluate this product against the shopper's request and their remembered taste profile.
Respond with two short bullet lists: STRENGTHS and CONCERNS, each 1-3 bullets,
focused only on what's decision-relevant (not a generic description).
This will be read aloud by text-to-speech, so use plain sentences with no
markdown formatting (no asterisks, bold, or headers).

Shopper's request: {query.raw_request}
Occasion: {query.occasion}, Setting: {query.setting}, Weather: {query.season_or_weather}, Formality: {query.formality}
Remembered taste profile: {memory.summary()}

Product: {product.name}
Specs: color={product.color}, fabric={product.fabric}, silhouette={product.silhouette}, formality={product.formality}
Weather notes: {product.weather_notes}
Image descriptions: {" | ".join(product.image_descriptions)}
Reviews: {" | ".join(r.text for r in product.reviews)}
"""
    fallback_result = _evaluate_with_rules(product, query, memory)
    text = gemini_client.generate_text(prompt, fallback="")
    if not text:
        return fallback_result

    strengths, concerns = _parse_bullets(text)
    return ComparisonResult(
        product=product,
        fit_score=fallback_result.fit_score,
        strengths=strengths or fallback_result.strengths,
        concerns=concerns or fallback_result.concerns,
    )


def _parse_bullets(text: str) -> tuple[list[str], list[str]]:
    strengths: list[str] = []
    concerns: list[str] = []
    bucket = None
    for line in text.splitlines():
        stripped = line.strip("-* \t").replace("**", "")
        if not stripped:
            continue
        if "strength" in stripped.lower():
            bucket = strengths
            continue
        if "concern" in stripped.lower():
            bucket = concerns
            continue
        if bucket is not None:
            bucket.append(stripped)
    return strengths, concerns
