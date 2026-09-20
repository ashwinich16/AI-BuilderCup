"""Thin wrapper around the Gemini API.

Every agent in this project calls through here rather than importing
`google.generativeai` directly, so the whole pipeline can run without any
credentials: if GEMINI_API_KEY isn't set (or the package isn't installed),
`is_live()` is False and callers fall back to their rule-based logic.

Swapping in real Gemini/Vertex AI reasoning later means setting the env var
and, for image reasoning, passing real image file paths instead of the
catalog's placeholder `image_descriptions` text.
"""

from __future__ import annotations

import os

_MODEL_NAME = "gemini-2.5-flash"

_client = None
_configured = False


def is_live() -> bool:
    """Whether real Gemini calls are available (API key set + package installed)."""
    _ensure_configured()
    return _client is not None


def _ensure_configured() -> None:
    global _client, _configured
    if _configured:
        return
    _configured = True

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return

    try:
        from google import genai
    except ImportError:
        return

    _client = genai.Client(api_key=api_key)


def generate_text(prompt: str, *, fallback: str) -> str:
    """Ask Gemini for a text completion; return `fallback` if not live or on error."""
    if not is_live():
        return fallback
    try:
        response = _client.models.generate_content(model=_MODEL_NAME, contents=prompt)
        return (response.text or "").strip() or fallback
    except Exception:
        return fallback
