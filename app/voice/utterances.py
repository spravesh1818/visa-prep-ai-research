"""Split officer text into sequential spoken utterances."""

from __future__ import annotations


def split_officer_utterances(text: str) -> list[str]:
    """Split on blank lines so TTS can speak greeting then question separately."""

    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    if parts:
        return parts
    stripped = text.strip()
    return [stripped] if stripped else []
