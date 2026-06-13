"""Shared prompt building blocks (persona, profile, transcript)."""

from __future__ import annotations

from typing import Any, Optional

from langchain_core.messages import BaseMessage

from app.llm.content import content_text
from app.ontology.models import ConsistencyRule, OfficerPersona, Topic


def persona_block(persona: OfficerPersona, display_name: str) -> str:
    notes = "\n".join(f"- {n}" for n in persona.style_notes)
    return (
        f"You are {persona.name} conducting a {display_name} interview.\n"
        f"Tone: {persona.tone}.\n"
        f"Skepticism level (0-1): {persona.strictness}.\n"
        f"{notes}"
    )


def profile_block(profile: Optional[dict[str, Any]]) -> str:
    if not profile:
        return "No prior applicant profile was provided."
    lines = [f"- {k}: {v}" for k, v in profile.items()]
    return "Known applicant profile (use it, do not re-ask what you know):\n" + "\n".join(
        lines
    )


def transcript(messages: list[BaseMessage], limit: int = 12) -> str:
    recent = messages[-limit:]
    rendered = []
    for m in recent:
        role = "Officer" if m.type == "ai" else "Applicant"
        rendered.append(f"{role}: {content_text(m.content)}")
    return "\n".join(rendered) if rendered else "(the interview has not started yet)"


def topic_rubric_blocks(
    topic: Topic, consistency_rules: list[ConsistencyRule]
) -> dict[str, str]:
    signals = "\n".join(f"- {s}" for s in topic.expected_signals) or "- (none listed)"
    red_flags = "\n".join(f"- {r}" for r in topic.red_flags) or "- (none listed)"
    triggers = "\n".join(f"- {t}" for t in topic.probe_triggers) or "- (none listed)"
    entities = ", ".join(topic.entities) if topic.entities else "(none)"
    rules = (
        "\n".join(f"- {r.description.strip()}" for r in consistency_rules)
        or "- (none)"
    )
    return {
        "topic_label": topic.label,
        "topic_intent": topic.intent.strip(),
        "expected_signals": signals,
        "red_flags": red_flags,
        "probe_triggers": triggers,
        "entities": entities,
        "consistency_rules": rules,
    }
