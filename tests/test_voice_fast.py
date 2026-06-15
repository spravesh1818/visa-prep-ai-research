"""Tests for voice-fast turn handling and utterance splitting."""

from __future__ import annotations

import pytest

from app.api import service
from app.config import get_settings
from app.session import checkpointer as cp_mod
from app.voice.utterances import split_officer_utterances


def test_split_officer_utterances():
    text = "Good morning.\n\nWhat brings you here today?"
    assert split_officer_utterances(text) == [
        "Good morning.",
        "What brings you here today?",
    ]


def test_start_interview_exposes_utterances(fake_llm):
    turn = service.start_interview("UK", "Student", None)
    assert turn["officer_utterances"]
    assert len(turn["officer_utterances"]) >= 1
    assert turn["officer_message"] == "\n\n".join(turn["officer_utterances"])


def test_respond_voice_fast_advances(fake_llm, monkeypatch):
    monkeypatch.setenv("VOICE_FAST_MODE", "true")
    get_settings.cache_clear()

    import app.interview.graph as graph_mod

    graph_mod.get_interview_graph.cache_clear()
    cp_mod.get_checkpointer.cache_clear()

    turn = service.start_interview("US", "F1", {"name": "Test"})
    session_id = turn["session_id"]

    from app.voice.fast_turn import flush_pending_eval

    next_turn = service.respond_voice(session_id, "My detailed answer about the program.")
    flush_pending_eval(session_id)
    assert next_turn["status"] == service.STATUS_AWAITING
    assert next_turn["officer_message"]
    assert next_turn.get("officer_utterances")

    get_settings.cache_clear()
    graph_mod.get_interview_graph.cache_clear()
    cp_mod.get_checkpointer.cache_clear()


def test_respond_voice_unknown_session():
    with pytest.raises(KeyError):
        service.respond_voice("missing-session", "hello")
