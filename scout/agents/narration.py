"""Narration agent: turns the comparison results into what should actually
be *said*, in ranked order -- not a full read-out of every spec and review,
but the deltas that matter for this decision, the way a sighted shopper's
eye would move from the strongest option down.
"""

from __future__ import annotations

from scout.agents.comparison import ComparisonResult


def narrate(results: list[ComparisonResult], max_items: int = 3) -> str:
    if not results:
        return "I couldn't find anything matching that. Want to try different terms?"

    lines = [f"I found {len(results)} options. Here's how they compare, best fit first:"]
    for rank, result in enumerate(results[:max_items], start=1):
        p = result.product
        lines.append(f"\n{rank}. {p.name} - ${p.price:.0f}, {p.color}, {p.silhouette}.")
        if result.strengths:
            lines.append("   Why it works: " + "; ".join(result.strengths[:2]) + ".")
        if result.concerns:
            lines.append("   Worth knowing: " + "; ".join(result.concerns[:2]) + ".")

    if len(results) > max_items:
        lines.append(f"\n({len(results) - max_items} more options available if none of these fit.)")

    return "\n".join(lines)


def narrate_single_delta(a: ComparisonResult, b: ComparisonResult) -> str:
    """The one-sentence 'what's actually different' comparison between two
    specific candidates, for when the user asks to compare just two.
    """
    a_only = [s for s in a.strengths if s not in b.strengths]
    b_only = [s for s in b.strengths if s not in a.strengths]
    parts = [f"Between {a.product.name} and {b.product.name}:"]
    if a_only:
        parts.append(f"{a.product.name} has an edge on: {'; '.join(a_only[:2])}.")
    if b_only:
        parts.append(f"{b.product.name} has an edge on: {'; '.join(b_only[:2])}.")
    if not a_only and not b_only:
        parts.append("They're close on the things that matter most for this decision.")
    return " ".join(parts)
