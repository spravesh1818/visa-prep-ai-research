"""Build LangChain messages from versioned, provider-specific YAML templates."""

from __future__ import annotations

import random
from typing import Any, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.config import get_settings
from app.interview.prompts import blocks
from app.interview.prompts.loader import load_prompt, load_shared
from app.interview.prompts.render import render
from app.interview.time_context import interview_time_context
from app.ontology.models import ConsistencyRule, OfficerPersona, Topic


def _base_vars(
    persona: OfficerPersona,
    display_name: str,
    profile: Optional[dict[str, Any]],
) -> dict[str, str]:
    settings = get_settings()
    shared = load_shared(settings.prompt_version, settings.llm_provider)
    return {
        "persona_block": blocks.persona_block(persona, display_name),
        "profile_block": blocks.profile_block(profile),
        "anti_script_rules": shared.anti_script_rules,
    }


def _style_var(template_vars: dict[str, Any], key: str) -> str:
    styles = template_vars.get(key) or []
    if not styles:
        return "a brief, natural greeting"
    return random.choice(styles)


def build_greeting_messages(
    persona: OfficerPersona,
    display_name: str,
    profile: Optional[dict[str, Any]],
    *,
    timezone: str = "UTC",
) -> list[BaseMessage]:
    settings = get_settings()
    tmpl = load_prompt(settings.prompt_version, settings.llm_provider, "greeting")
    vars_ = _base_vars(persona, display_name, profile)
    vars_.update(interview_time_context(timezone))
    style_raw = _style_var(tmpl.variables, "opener_styles")
    vars_["style"] = render(style_raw, **vars_)
    vars_["nonce"] = str(random.randint(1000, 9999))

    return [
        SystemMessage(content=render(tmpl.system, **vars_)),
        HumanMessage(content=render(tmpl.human, **vars_)),
    ]


def build_closing_messages(
    persona: OfficerPersona,
    display_name: str,
    messages: list[BaseMessage],
) -> list[BaseMessage]:
    settings = get_settings()
    tmpl = load_prompt(settings.prompt_version, settings.llm_provider, "closing")
    vars_ = _base_vars(persona, display_name, None)
    vars_["transcript"] = blocks.transcript(messages)
    vars_["style"] = _style_var(tmpl.variables, "closing_styles")
    vars_["nonce"] = str(random.randint(1000, 9999))

    return [
        SystemMessage(content=render(tmpl.system, **vars_)),
        HumanMessage(content=render(tmpl.human, **vars_)),
    ]


def build_question_messages(
    persona: OfficerPersona,
    display_name: str,
    topic: Topic,
    messages: list[BaseMessage],
    profile: Optional[dict[str, Any]],
) -> list[BaseMessage]:
    settings = get_settings()
    tmpl = load_prompt(settings.prompt_version, settings.llm_provider, "question")
    vars_ = _base_vars(persona, display_name, profile)
    vars_["transcript"] = blocks.transcript(messages)
    vars_["topic_intent"] = topic.intent.strip()

    return [
        SystemMessage(content=render(tmpl.system, **vars_)),
        HumanMessage(content=render(tmpl.human, **vars_)),
    ]


def build_probe_messages(
    persona: OfficerPersona,
    display_name: str,
    topic: Topic,
    probe_reason: str,
    messages: list[BaseMessage],
    profile: Optional[dict[str, Any]],
) -> list[BaseMessage]:
    settings = get_settings()
    tmpl = load_prompt(settings.prompt_version, settings.llm_provider, "probe")
    vars_ = _base_vars(persona, display_name, profile)
    vars_["transcript"] = blocks.transcript(messages)
    vars_["topic_label"] = topic.label
    vars_["topic_intent"] = topic.intent.strip()
    vars_["probe_reason"] = probe_reason

    return [
        SystemMessage(content=render(tmpl.system, **vars_)),
        HumanMessage(content=render(tmpl.human, **vars_)),
    ]


def build_evaluation_messages(
    topic: Topic,
    consistency_rules: list[ConsistencyRule],
    latest_answer: str,
    messages: list[BaseMessage],
    profile: Optional[dict[str, Any]],
    strictness: float,
) -> list[BaseMessage]:
    settings = get_settings()
    tmpl = load_prompt(settings.prompt_version, settings.llm_provider, "evaluation")
    rubric = blocks.topic_rubric_blocks(topic, consistency_rules)
    vars_ = {
        "strictness": str(strictness),
        "profile_block": blocks.profile_block(profile),
        "transcript": blocks.transcript(messages, limit=40),
        "latest_answer": latest_answer,
        **rubric,
    }

    return [
        SystemMessage(content=render(tmpl.system, **vars_)),
        HumanMessage(content=render(tmpl.human, **vars_)),
    ]


def build_report_narrative_messages(
    display_name: str,
    scored_summary: str,
    messages: list[BaseMessage],
) -> list[BaseMessage]:
    settings = get_settings()
    tmpl = load_prompt(
        settings.prompt_version, settings.llm_provider, "report_narrative"
    )
    vars_ = {
        "display_name": display_name,
        "scored_summary": scored_summary,
        "transcript": blocks.transcript(messages, limit=60),
    }

    return [
        SystemMessage(content=render(tmpl.system, **vars_)),
        HumanMessage(content=render(tmpl.human, **vars_)),
    ]
