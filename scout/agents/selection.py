"""Selection agent: interprets what the shopper meant to do with the
narrated options, from a free-form spoken sentence.

A voice-first user doesn't say "1" or "two" -- they say "I'll go with the
second one", "yeah let's do the Rowan jeans", "nah none of those work,
too plain". Matching that with regex/keyword rules is inherently brittle
(see: "I would like to go for number 2" failing to match a bare-digit or
whole-word-number check). When Gemini is live, this hands the utterance
and the candidate list to it directly and asks for a structured decision;
the rule-based fallback below still handles the common cases (digits,
spelled-out numbers and ordinals anywhere in the sentence, product-name
substrings, and a rejection-phrase heuristic) when Gemini isn't available.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from scout import gemini_client
from scout.agents.comparison import ComparisonResult

Decision = Literal["select", "reject_all", "unclear"]


@dataclass
class Selection:
    decision: Decision
    picked: ComparisonResult | None = None
    reason: str | None = None


_WORD_NUMBERS = {
    "one": 1, "first": 1,
    "two": 2, "second": 2,
    "three": 3, "third": 3,
    "four": 4, "fourth": 4,
    "five": 5, "fifth": 5,
}
_REJECTION_MARKERS = ["no ", "not ", "none", "don't", "doesn't", "isn't", "aren't", "n't have", "not what"]


def interpret(utterance: str, results: list[ComparisonResult]) -> Selection:
    if gemini_client.is_live():
        gemini_result = _interpret_with_gemini(utterance, results)
        if gemini_result is not None:
            return gemini_result
    return _interpret_with_rules(utterance, results)


def _interpret_with_gemini(utterance: str, results: list[ComparisonResult]) -> Selection | None:
    listing = "\n".join(f"{i}: {r.product.name}" for i, r in enumerate(results, start=1))
    prompt = f"""A shopper was just read this numbered list of product options:
{listing}

They replied: "{utterance}"

Decide what they meant. Respond with exactly one line, no other text:
- "SELECT <n>" where <n> is the option number they picked, if they clearly picked one
- "REJECT_ALL: <short reason>" only if they are actively rejecting the options
  themselves (e.g. "none of these", "too plain", "doesn't have what I need"),
  with their reason in a few words
- "UNCLEAR" if they sound undecided, hesitant, or you genuinely can't tell what
  they want (e.g. "not sure", "let me think", "can you repeat those?") -- this
  is different from rejecting the options, so don't use REJECT_ALL for it
"""
    text = gemini_client.generate_text(prompt, fallback="")
    if not text:
        return None

    line = text.strip().splitlines()[0].strip()
    match = re.match(r"SELECT\s+(\d+)", line, re.IGNORECASE)
    if match:
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(results):
            return Selection(decision="select", picked=results[idx])
        return None

    if line.upper().startswith("REJECT_ALL"):
        reason = line.split(":", 1)[1].strip() if ":" in line else utterance.strip()
        return Selection(decision="reject_all", reason=reason or utterance.strip())

    if line.upper().startswith("UNCLEAR"):
        return Selection(decision="unclear")

    return None


def _interpret_with_rules(utterance: str, results: list[ComparisonResult]) -> Selection:
    stripped = utterance.strip().lower()

    if stripped in ("none", "none of these", "no", "skip"):
        return Selection(decision="reject_all", reason=utterance.strip())

    bare_digits = re.findall(r"\d+", stripped)
    for digit_str in bare_digits:
        idx = int(digit_str) - 1
        if 0 <= idx < len(results):
            return Selection(decision="select", picked=results[idx])

    for word in re.findall(r"[a-z]+", stripped):
        if word in _WORD_NUMBERS:
            idx = _WORD_NUMBERS[word] - 1
            if 0 <= idx < len(results):
                return Selection(decision="select", picked=results[idx])

    for result in results:
        name = result.product.name.lower()
        if name in stripped or stripped in name:
            return Selection(decision="select", picked=result)
        # match on any distinctive word from the product name (e.g. "Rowan jeans" -> "rowan")
        first_word = name.split()[0]
        if len(first_word) > 3 and first_word in stripped:
            return Selection(decision="select", picked=result)

    padded = f" {stripped} "
    if any(marker in padded for marker in _REJECTION_MARKERS):
        return Selection(decision="reject_all", reason=utterance.strip())

    return Selection(decision="unclear")
