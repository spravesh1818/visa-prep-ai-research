"""Shared test fixtures.

Tests run fully offline: a fake chat model replaces every LLM call so no API
keys or network are required.
"""

from __future__ import annotations

import os

os.environ.setdefault("CHECKPOINTER_BACKEND", "memory")
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from langchain_core.messages import AIMessage

from app.interview.report import AnswerEvaluation, ExtractedEntity, ReportNarrative


class _FakeStructured:
    """Stands in for ``llm.with_structured_output(Schema)``."""

    def __init__(self, schema, eval_factory):
        self._schema = schema
        self._eval_factory = eval_factory

    def invoke(self, _messages):
        if self._schema is AnswerEvaluation:
            return self._eval_factory()
        if self._schema is ReportNarrative:
            return ReportNarrative(
                summary="Overall a credible interview.",
                strengths=["Clear program rationale", "Solid funding"],
                weaknesses=["Could elaborate on ties home"],
            )
        return self._schema()


class FakeChatModel:
    """Deterministic fake that returns canned officer lines and evaluations."""

    def __init__(self, eval_factory):
        self._eval_factory = eval_factory
        self.calls = 0

    def invoke(self, _messages):
        self.calls += 1
        return AIMessage(content=f"Officer utterance #{self.calls}")

    def with_structured_output(self, schema):
        return _FakeStructured(schema, self._eval_factory)


@pytest.fixture
def fake_llm(monkeypatch):
    """Patch the LLM factory used by nodes and reset cached singletons."""

    # Default evaluation: strong answer mentioning a top-tier university.
    def default_eval():
        return AnswerEvaluation(
            answer_quality=0.82,
            extracted_entities=[ExtractedEntity(key="university", value="MIT")],
            matched_signals=["specific and credible"],
            needs_probe=False,
        )

    holder = {"factory": default_eval}

    def _get_llm(role="default", provider=None):
        return FakeChatModel(holder["factory"])

    def _get_structured_llm(role, schema):
        return FakeChatModel(holder["factory"]).with_structured_output(schema)

    import app.interview.graph as graph_mod
    import app.interview.nodes as nodes_mod
    import app.session.checkpointer as cp_mod

    monkeypatch.setattr(nodes_mod, "get_llm", _get_llm)
    monkeypatch.setattr(nodes_mod, "get_structured_llm", _get_structured_llm)
    monkeypatch.setattr(
        nodes_mod, "describe_active_llm", lambda: {"provider": "fake", "model": "fake"}
    )

    # Ensure a fresh in-memory graph/checkpointer per test.
    graph_mod.get_interview_graph.cache_clear()
    cp_mod.get_checkpointer.cache_clear()

    yield holder

    graph_mod.get_interview_graph.cache_clear()
    cp_mod.get_checkpointer.cache_clear()
