"""Scout: a voice-first shopping companion for blind and low-vision
fashion shoppers.

Runs the core loop end-to-end against a mocked product catalog:
  1. Elicitation agent turns a loose request into a structured query.
  2. Catalog search narrows to a short candidate list.
  3. Comparison agent reasons over each candidate's images/specs/reviews
     against the query and the user's remembered taste profile.
  4. Narration agent reports only the deltas that matter, ranked.
  5. Whatever the user picks or rejects (and why) is written to memory.

Voice I/O degrades to typed input/output automatically if no mic/speakers
are available. Gemini reasoning is used if GEMINI_API_KEY is set in the
environment; otherwise the comparison agent falls back to rule-based
reasoning over the same structured fields, so the whole pipeline is
runnable without any credentials.
"""

from __future__ import annotations

from scout import gemini_client, voice
from scout.agents import comparison, elicitation, narration, selection
from scout.catalog import available_categories, find_candidates, load_catalog
from scout.memory import PreferenceMemory

_MAX_SELECTION_ATTEMPTS = 3


def main() -> None:
    catalog = load_catalog()
    memory = PreferenceMemory()

    mode = "Gemini-backed" if gemini_client.is_live() else "rule-based fallback (no GEMINI_API_KEY set)"
    voice.speak(f"Hi, I'm Scout, your shopping companion. (Reasoning mode: {mode}.)")
    if not voice.output_ready():
        voice.speak(
            "Heads up: text-to-speech isn't available on this machine, so I'll only be able to "
            "print my side of the conversation, not speak it."
        )
    if not voice.input_ready():
        voice.speak(
            "Heads up: I can't access a microphone, so please type your answers instead of speaking them."
        )
    if memory.events:
        voice.speak(f"Welcome back. From what I remember: {memory.summary()}")

    while True:
        raw_request = voice.listen("What are you shopping for today?")
        if raw_request.lower() in ("quit", "exit", "stop", "nevermind"):
            voice.speak("Sounds good, happy shopping. Goodbye!")
            break

        query = elicitation.run(raw_request, ask=voice.listen)
        candidates = find_candidates(query, catalog)

        if not candidates and query.item_type:
            options = ", ".join(available_categories(catalog))
            voice.speak(
                f"I don't have any {query.item_type} in the catalog right now. "
                f"What I do have is: {options}. Want to try one of those instead?"
            )
            continue

        results = comparison.compare(candidates, query, memory)
        voice.speak(narration.narrate(results))
        if _run_selection(results, memory) == "quit":
            break

        again = voice.listen("Would you like to look for anything else? (yes/no)")
        if again.strip().lower() not in ("yes", "y", "yeah", "sure"):
            voice.speak("Happy to help. Goodbye!")
            break


def _run_selection(results: list[comparison.ComparisonResult], memory: PreferenceMemory) -> str | None:
    """Find out what the shopper wants to do with these results, retrying by
    voice on an unclear reply instead of silently giving up after one miss.
    Returns "quit" if the shopper asked to stop the whole session.
    """
    prompt = "Which one would you like to go with, say 'none' if none of these work, or 'quit' to stop."
    for attempt in range(1, _MAX_SELECTION_ATTEMPTS + 1):
        utterance = voice.listen(prompt)
        if utterance.strip().lower() in ("quit", "exit", "stop"):
            voice.speak("Got it, stopping here.")
            return "quit"

        outcome = selection.interpret(utterance, results)

        if outcome.decision == "select" and outcome.picked is not None:
            _record_selection(outcome.picked, results, memory)
            return None

        if outcome.decision == "reject_all":
            reason = outcome.reason or voice.listen("No problem - what didn't work about these options?")
            for result in results:
                memory.record(result.product.id, result.product.name, "rejected", reason)
            voice.speak("Got it, noted that none of those worked.")
            return None

        if attempt < _MAX_SELECTION_ATTEMPTS:
            prompt = (
                "Sorry, I didn't catch which one you meant. You can say a number like "
                "'the second one', name the product, or say 'none of these work'."
            )
        else:
            voice.speak("I'm still not catching that, let's leave this round unrecorded and move on.")
    return None


def _record_selection(
    picked: comparison.ComparisonResult,
    results: list[comparison.ComparisonResult],
    memory: PreferenceMemory,
) -> None:
    voice.speak(f"Great choice - {picked.product.name} it is.")
    memory.record(picked.product.id, picked.product.name, "accepted", "; ".join(picked.strengths[:2]))
    for result in results:
        if result is picked:
            continue
        memory.record(result.product.id, result.product.name, "rejected", f"chose {picked.product.name} instead")


if __name__ == "__main__":
    main()
