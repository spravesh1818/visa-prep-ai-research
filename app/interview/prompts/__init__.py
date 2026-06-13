"""Prompt construction for the interview.

Crucial design rule: we never store literal questions. Every officer utterance
(greeting, question, probe) is generated from an *intent* plus the live
conversation, with explicit instructions to vary the wording so it sounds like a
real person rather than a script.

Templates live under ``app/interview/prompts/{version}/{provider}/`` and are
selected via ``PROMPT_VERSION`` and ``LLM_PROVIDER``.
"""

from __future__ import annotations

from typing import Any, Optional

from langchain_core.messages import BaseMessage

from app.interview.prompts.registry import (
    build_closing_messages,
    build_evaluation_messages,
    build_greeting_messages,
    build_probe_messages,
    build_question_messages,
    build_report_narrative_messages,
)
from app.ontology.models import ConsistencyRule, OfficerPersona, Topic


def greeting_messages(
    persona: OfficerPersona,
    display_name: str,
    profile: Optional[dict[str, Any]],
    *,
    timezone: str = "UTC",
) -> list[BaseMessage]:
    """Generate a natural, varied opening greeting (no substantive question)."""

    return build_greeting_messages(
        persona, display_name, profile, timezone=timezone
    )


def closing_messages(
    persona: OfficerPersona,
    display_name: str,
    messages: list[BaseMessage],
) -> list[BaseMessage]:
    """Generate a natural, varied closing line (reveals no decision)."""

    return build_closing_messages(persona, display_name, messages)


def question_messages(
    persona: OfficerPersona,
    display_name: str,
    topic: Topic,
    messages: list[BaseMessage],
    profile: Optional[dict[str, Any]],
) -> list[BaseMessage]:
    """Generate the next question fulfilling a topic's intent, in fresh words."""

    return build_question_messages(
        persona, display_name, topic, messages, profile
    )


def probe_messages(
    persona: OfficerPersona,
    display_name: str,
    topic: Topic,
    probe_reason: str,
    messages: list[BaseMessage],
    profile: Optional[dict[str, Any]],
) -> list[BaseMessage]:
    """Generate a targeted follow-up when something seems off."""

    return build_probe_messages(
        persona, display_name, topic, probe_reason, messages, profile
    )


def evaluation_messages(
    topic: Topic,
    consistency_rules: list[ConsistencyRule],
    latest_answer: str,
    messages: list[BaseMessage],
    profile: Optional[dict[str, Any]],
    strictness: float,
) -> list[BaseMessage]:
    """Build the structured-evaluation prompt for the latest answer."""

    return build_evaluation_messages(
        topic,
        consistency_rules,
        latest_answer,
        messages,
        profile,
        strictness,
    )


def report_narrative_messages(
    display_name: str,
    scored_summary: str,
    messages: list[BaseMessage],
) -> list[BaseMessage]:
    """Ask the LLM to synthesize the narrative portion of the report."""

    return build_report_narrative_messages(display_name, scored_summary, messages)
