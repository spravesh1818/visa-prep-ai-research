"""A LiveKit ``llm.LLM`` adapter that drives the existing LangGraph interview.

LiveKit handles audio + STT + TTS + turn-taking; this adapter is the "brain":
for each completed applicant turn it advances our ontology-driven interview via
``app.api.service.respond`` and returns the officer's next utterance. This keeps
all probing, university checks, scoring, and reporting intact for voice.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from livekit.agents import llm

from app.api import service

logger = logging.getLogger(__name__)


def _message_text(item: Any) -> str:
    """Best-effort extraction of plain text from a ChatContext item."""

    text = getattr(item, "text_content", None)
    if text:
        return str(text)
    content = getattr(item, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [c for c in content if isinstance(c, str)]
        return " ".join(parts)
    return ""


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

        logger.info("Applicant turn (stitched): %s", user_text)

        try:
            turn = await asyncio.to_thread(
                service.respond, self._interview_llm.session_id, user_text
            )
        except Exception:
            logger.exception("Voice interview turn failed.")
            turn = {
                "officer_message": "I'm sorry, could you repeat that?",
                "status": service.STATUS_AWAITING,
            }

        officer_message = turn.get("officer_message", "")
        if turn.get("status") == service.STATUS_COMPLETED:
            self._interview_llm.completed = True

        self._event_ch.send_nowait(
            llm.ChatChunk(
                id=str(uuid.uuid4()),
                delta=llm.ChoiceDelta(role="assistant", content=officer_message),
            )
        )


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
