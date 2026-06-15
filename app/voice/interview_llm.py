"""A LiveKit ``llm.LLM`` adapter that drives the existing LangGraph interview.

LiveKit handles audio + STT + TTS + turn-taking; this adapter is the "brain":
for each completed applicant turn it advances our ontology-driven interview via
``app.api.service.respond`` (or ``respond_voice`` when voice-fast mode is on)
and returns the officer's next utterance.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from livekit.agents import llm

from app.api import service
from app.config import get_settings
from app.llm.content import content_text
from app.voice.timing import VoiceTimer
from app.voice.utterances import split_officer_utterances

logger = logging.getLogger(__name__)


def _message_text(item: Any) -> str:
    """Best-effort extraction of plain text from a ChatContext item."""

    text = getattr(item, "text_content", None)
    if text:
        return str(text)
    content = getattr(item, "content", None)
    return content_text(content)


def _accumulated_user_turn_text(chat_ctx: llm.ChatContext) -> str:
    """Join all user messages since the last assistant turn (safety net for STT chunks)."""
    parts: list[str] = []
    for item in reversed(list(chat_ctx.items)):
        if getattr(item, "role", None) == "user":
            txt = _message_text(item).strip()
            if txt:
                parts.append(txt)
        elif getattr(item, "role", None) == "assistant":
            break
    return " ".join(reversed(parts)).strip()


def _emit_officer_chunks(stream: llm.LLMStream, text: str) -> None:
    """Send one or more assistant chunks (split on paragraph breaks)."""

    parts = split_officer_utterances(text)
    for i, part in enumerate(parts):
        stream._event_ch.send_nowait(
            llm.ChatChunk(
                id=str(uuid.uuid4()),
                delta=llm.ChoiceDelta(role="assistant", content=part),
            )
        )
        if i < len(parts) - 1:
            logger.debug("voice utterance split part %d/%d", i + 1, len(parts))


class _InterviewLLMStream(llm.LLMStream):
    def __init__(self, interview_llm: "InterviewLLM", *, chat_ctx, tools, conn_options):
        super().__init__(
            interview_llm, chat_ctx=chat_ctx, tools=tools, conn_options=conn_options
        )
        self._interview_llm = interview_llm

    async def _run(self) -> None:
        user_text = _accumulated_user_turn_text(self._chat_ctx)
        if not user_text:
            return

        settings = get_settings()
        timer = VoiceTimer(self._interview_llm.session_id)
        timer.mark("stt_turn_ready", text_len=len(user_text))
        logger.info("Applicant turn (stitched): %s", user_text)

        graph_start = time.monotonic()
        try:
            if settings.voice_fast_mode:
                turn = await asyncio.to_thread(
                    service.respond_voice,
                    self._interview_llm.session_id,
                    user_text,
                )
            else:
                turn = await asyncio.to_thread(
                    service.respond,
                    self._interview_llm.session_id,
                    user_text,
                )
        except Exception:
            logger.exception("Voice interview turn failed.")
            turn = {
                "officer_message": "I'm sorry, could you repeat that?",
                "officer_utterances": ["I'm sorry, could you repeat that?"],
                "status": service.STATUS_AWAITING,
            }

        timer.mark("graph_done", graph_s=round(time.monotonic() - graph_start, 3))

        officer_message = turn.get("officer_message", "")
        if turn.get("status") == service.STATUS_COMPLETED:
            self._interview_llm.completed = True

        timer.mark("tts_start", parts=len(turn.get("officer_utterances", [])))
        _emit_officer_chunks(self, officer_message)


class InterviewLLM(llm.LLM):
    """Bridges LiveKit's voice pipeline to one LangGraph interview session."""

    def __init__(self, session_id: str) -> None:
        super().__init__()
        self.session_id = session_id
        self.completed = False

    def chat(self, *, chat_ctx, tools=None, conn_options=None, **_kwargs):
        from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS

        return _InterviewLLMStream(
            self,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options or DEFAULT_API_CONNECT_OPTIONS,
        )
