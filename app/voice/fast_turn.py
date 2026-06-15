"""Voice-fast interview turns: one interviewer LLM on the speak path, async eval."""

from __future__ import annotations

import logging
import threading
from typing import Any

from langchain_core.messages import HumanMessage

from app.api import service
from app.interview import nodes
from app.interview.graph import get_interview_graph
from app.llm.content import content_text

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_pending_threads: dict[str, threading.Thread] = {}


def _config(session_id: str) -> dict[str, Any]:
    return service._config(session_id)


def _state_values(session_id: str) -> dict[str, Any]:
    graph = get_interview_graph()
    snapshot = graph.get_state(_config(session_id))
    return dict(snapshot.values or {})


def _merge_state(state: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(state)
    for key, value in updates.items():
        if key == "messages" and key in merged:
            merged["messages"] = list(merged["messages"]) + list(value)
        elif key == "evaluations" and key in merged:
            merged["evaluations"] = list(merged.get("evaluations", [])) + list(value)
        else:
            merged[key] = value
    return merged


def _apply_updates(session_id: str, updates: dict[str, Any], as_node: str) -> None:
    graph = get_interview_graph()
    graph.update_state(_config(session_id), updates, as_node=as_node)


def _officer_text_from_updates(updates: dict[str, Any]) -> str:
    for msg in reversed(updates.get("messages", [])):
        if getattr(msg, "type", None) == "ai":
            return content_text(msg.content)
    return ""


def _run_eval_and_route(session_id: str) -> None:
    """Background: evaluate latest answer and advance topic or finalize."""

    try:
        state = _state_values(session_id)
        eval_updates = nodes.evaluate_answer(state)
        state = _merge_state(state, eval_updates)
        route = nodes.route_after_eval(state)

        _apply_updates(session_id, eval_updates, as_node="evaluate_answer")

        if route == "probe":
            logger.info("voice_fast eval session=%s route=probe (next turn)", session_id)
        elif route == "next_topic":
            _apply_updates(session_id, nodes.next_topic(state), as_node="next_topic")
            logger.info("voice_fast eval session=%s route=next_topic", session_id)
        elif route == "finalize":
            state = _state_values(session_id)
            finalize_updates = nodes.finalize(state)
            _apply_updates(session_id, finalize_updates, as_node="finalize")
            logger.info("voice_fast eval session=%s route=finalize (report ready)", session_id)
    except Exception:
        logger.exception("voice_fast background eval failed session=%s", session_id)


def _start_background_eval(session_id: str) -> None:
    with _lock:
        prior = _pending_threads.get(session_id)
        if prior and prior.is_alive():
            prior.join(timeout=120)

        thread = threading.Thread(
            target=_run_eval_and_route,
            args=(session_id,),
            name=f"voice-eval-{session_id[:8]}",
            daemon=True,
        )
        _pending_threads[session_id] = thread
        thread.start()


def flush_pending_eval(session_id: str, timeout: float = 120.0) -> None:
    """Wait for in-flight background evaluation (before finalize/report)."""

    with _lock:
        thread = _pending_threads.get(session_id)
    if thread and thread.is_alive():
        thread.join(timeout=timeout)
        if thread.is_alive():
            logger.warning(
                "voice_fast eval still running after %.0fs session=%s",
                timeout,
                session_id,
            )


def respond_voice_fast(session_id: str, message: str) -> dict[str, Any]:
    """Advance a voice turn with one interviewer LLM call; eval runs in background."""

    graph = get_interview_graph()
    config = _config(session_id)

    snapshot = graph.get_state(config)
    if not snapshot.created_at:
        raise KeyError(f"Unknown session '{session_id}'.")
    if (snapshot.values or {}).get("status") == service.STATUS_COMPLETED:
        return service._shape_turn(session_id, snapshot.values)

    flush_pending_eval(session_id)

    snapshot = graph.get_state(config)
    if (snapshot.values or {}).get("status") == service.STATUS_COMPLETED:
        return service._shape_turn(session_id, snapshot.values)

    state = dict(snapshot.values or {})
    human = HumanMessage(content=message)
    _apply_updates(session_id, {"messages": [human]}, as_node="await_answer")
    state = _merge_state(state, {"messages": [human]})

    if state.get("status") == service.STATUS_COMPLETED:
        return service._shape_turn(session_id, state)

    if state.get("needs_probe"):
        speak_updates = nodes.probe(state)
        _apply_updates(session_id, speak_updates, as_node="probe")
        officer_message = _officer_text_from_updates(speak_updates)
        _start_background_eval(session_id)
        shaped = service._shape_turn(
            session_id,
            {**state, **speak_updates, "status": service.STATUS_AWAITING},
        )
        shaped["officer_utterances"] = service._officer_utterances_from_text(
            officer_message
        )
        return shaped

    speak_updates = nodes.ask_question(state)
    _apply_updates(session_id, speak_updates, as_node="ask_question")
    officer_message = _officer_text_from_updates(speak_updates)
    _start_background_eval(session_id)

    shaped = service._shape_turn(
        session_id,
        {**state, **speak_updates, "status": service.STATUS_AWAITING},
    )
    shaped["officer_utterances"] = service._officer_utterances_from_text(officer_message)
    return shaped
