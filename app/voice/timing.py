"""Structured latency logging for the voice interview pipeline."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger("visa-voice-timing")


class VoiceTimer:
    """Log monotonic phase durations for a single voice session."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._t0 = time.monotonic()

    def mark(self, phase: str, **extra: object) -> float:
        elapsed = time.monotonic() - self._t0
        if extra:
            logger.info(
                "voice_timing session=%s phase=%s elapsed_s=%.3f %s",
                self.session_id,
                phase,
                elapsed,
                " ".join(f"{k}={v!r}" for k, v in extra.items()),
            )
        else:
            logger.info(
                "voice_timing session=%s phase=%s elapsed_s=%.3f",
                self.session_id,
                phase,
                elapsed,
            )
        return elapsed

    @contextmanager
    def phase(self, name: str, **extra: object) -> Iterator[None]:
        start = time.monotonic()
        try:
            yield
        finally:
            duration = time.monotonic() - start
            logger.info(
                "voice_timing session=%s phase=%s duration_s=%.3f %s",
                self.session_id,
                name,
                duration,
                " ".join(f"{k}={v!r}" for k, v in extra.items()),
            )
