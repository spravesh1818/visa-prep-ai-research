"""Application service: drive the interview graph and shape API responses.

Each interview session maps to a LangGraph ``thread_id`` (== ``session_id``).
The graph pauses at ``await_answer`` via ``interrupt()``; we resume it with
``Command(resume=...)`` carrying the applicant's answer.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from langchain_core.messages import BaseMessage

from app.llm.content import content_text
from langgraph.types import Command

from app.config import get_settings
from app.interview.graph import get_interview_graph
from app.ontology import load_ontology

logger = logging.getLogger(__name__)

STATUS_AWAITING = "awaiting_answer"
STATUS_COMPLETED = "completed"


def _config(session_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": session_id}}


def _trailing_officer_message(messages: list[BaseMessage]) -> str:
    """Join the trailing run of officer (AI) messages into one utterance.

    On session start this captures the greeting + first question together; on a
    normal turn it is just the single next question or probe.
    """

    return "\n\n".join(_trailing_officer_utterances(messages)).strip()


def _trailing_officer_utterances(messages: list[BaseMessage]) -> list[str]:
    """Return trailing officer messages separately (e.g. greeting, then question)."""

    collected: list[str] = []
    for m in reversed(messages):
        if m.type == "ai":
            collected.append(content_text(m.content))
        else:
            break
    return list(reversed(collected))


def _officer_utterances_from_text(text: str) -> list[str]:
    from app.voice.utterances import split_officer_utterances

    return split_officer_utterances(text)


def _officer_message_from_result(result: dict[str, Any]) -> str:
    # Prefer the interrupt payload when present, else derive from transcript.
    interrupts = result.get("__interrupt__")
    if interrupts:
        first = interrupts[0]
        value = getattr(first, "value", None)
        if value is None and isinstance(first, (list, tuple)) and first:
            value = first[0]
        if isinstance(value, dict) and value.get("officer_message"):
            # The transcript-based message is richer (includes greeting), so
            # only fall back to the payload if the transcript yields nothing.
            transcript_msg = _trailing_officer_message(result.get("messages", []))
            return transcript_msg or str(value["officer_message"])
    return _trailing_officer_message(result.get("messages", []))


def _shape_turn(session_id: str, result: dict[str, Any]) -> dict[str, Any]:
    status = result.get("status")
    if status == STATUS_COMPLETED:
        closing = result.get("closing_message") or (
            "Thank you for your time. That concludes the interview."
        )
        return {
            "session_id": session_id,
            "officer_message": closing,
            "officer_utterances": _officer_utterances_from_text(closing),
            "status": STATUS_COMPLETED,
            "report_available": True,
        }
    officer_message = _officer_message_from_result(result)
    return {
        "session_id": session_id,
        "officer_message": officer_message,
        "officer_utterances": _officer_utterances_from_text(officer_message),
        "status": STATUS_AWAITING,
        "report_available": False,
    }


def start_interview(
    country: str, visa_type: str, candidate_profile: Optional[dict[str, Any]]
) -> dict[str, Any]:
    """Begin a new interview; raises LookupError for unknown country/visa."""

    # Validate the ontology exists up front (clean 4xx instead of a 500).
    load_ontology(country, visa_type)

    session_id = str(uuid.uuid4())
    graph = get_interview_graph()
    initial_state = {
        "session_id": session_id,
        "country": country,
        "visa_type": visa_type,
        "candidate_profile": candidate_profile or {},
        "messages": [],
    }
    result = graph.invoke(initial_state, config=_config(session_id))
    return _shape_turn(session_id, result)


def respond(session_id: str, message: str) -> dict[str, Any]:
    """Resume a paused interview with the applicant's answer."""

    graph = get_interview_graph()
    config = _config(session_id)

    snapshot = graph.get_state(config)
    if not snapshot.created_at:
        raise KeyError(f"Unknown session '{session_id}'.")
    if (snapshot.values or {}).get("status") == STATUS_COMPLETED:
        return _shape_turn(session_id, snapshot.values)

    result = graph.invoke(Command(resume=message), config=config)
    return _shape_turn(session_id, result)


def respond_voice(session_id: str, message: str) -> dict[str, Any]:
    """Voice-optimized turn: one speak-path LLM call; evaluation runs in background."""

    from app.voice.fast_turn import respond_voice_fast

    return respond_voice_fast(session_id, message)


def get_report(session_id: str) -> dict[str, Any]:
    """Return the report (if ready) and current status for a session."""

    settings = get_settings()
    if settings.voice_fast_mode:
        from app.voice.fast_turn import flush_pending_eval

        flush_pending_eval(session_id)

    graph = get_interview_graph()
    snapshot = graph.get_state(_config(session_id))
    if not snapshot.created_at:
        raise KeyError(f"Unknown session '{session_id}'.")

    values = snapshot.values or {}
    return {
        "session_id": session_id,
        "status": values.get("status", "in_progress"),
        "report": values.get("report"),
    }


def maybe_deliver_report(session_id: str) -> None:
    """POST the finished report to the configured BE webhook, if any."""

    settings = get_settings()
    if not settings.report_webhook_url:
        return

    data = get_report(session_id)
    if data.get("status") != STATUS_COMPLETED or not data.get("report"):
        return

    try:
        import httpx

        httpx.post(settings.report_webhook_url, json=data["report"], timeout=10.0)
    except Exception:  # pragma: no cover - webhook is best-effort
        logger.exception("Failed to deliver report to webhook.")
