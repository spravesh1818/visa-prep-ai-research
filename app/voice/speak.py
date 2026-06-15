"""Speak officer lines via LiveKit TTS, splitting multi-paragraph text."""

from __future__ import annotations

import logging
from typing import Any

from app.voice.utterances import split_officer_utterances

logger = logging.getLogger(__name__)


async def say_officer_message(session: Any, text: str, *, allow_interruptions: bool = True) -> None:
    """Speak one or more sequential utterances (split on blank lines)."""

    parts = split_officer_utterances(text)
    for i, part in enumerate(parts):
        logger.debug("session.say part %d/%d len=%d", i + 1, len(parts), len(part))
        await session.say(part, allow_interruptions=allow_interruptions)
