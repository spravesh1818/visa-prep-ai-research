"""Prompt construction for the interview.

Crucial design rule: we never store literal questions. Every officer utterance
(greeting, question, probe) is generated from an *intent* plus the live
conversation, with explicit instructions to vary the wording so it sounds like a
real person rather than a script.
"""

from __future__ import annotations

import random
from typing import Any, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.ontology.models import ConsistencyRule, OfficerPersona, Topic

_ANTI_SCRIPT_RULES = (
    "Speak like a real human visa officer at the interview window, not a "
    "chatbot. Keep it to one or two sentences. Ask only ONE thing at a time. "
    "Vary your phrasing every time; never reuse a stock sentence or template. "
    "Do not number your questions, use no quotation marks, and add no stage "
    "directions or labels like 'Officer:'. Output only the spoken words."
)

# Varied opening flavours so greetings differ session to session.
_OPENER_STYLES = [
    "a crisp good-morning and a request that they have their documents ready",
    "a brief welcome and a quick check that they are ready to begin",
    "a courteous hello that puts a visibly nervous applicant at ease",
    "a polite but no-nonsense greeting that gets straight to business",
    "a warm greeting that briefly acknowledges the wait in line",
    "a friendly hello and a light confirmation of their name",
]

# Varied ways to wrap up so the closing is not identical every time.
_CLOSING_STYLES = [
    "thank them for their time and let them know the interview is complete",
    "politely signal that you have everything you need and are concluding",
    "wrap up courteously and tell them they may step away",
    "close the interview warmly without stating any decision",
    "bring the conversation to a calm, professional end",
]


def _persona_block(persona: OfficerPersona, display_name: str) -> str:
    notes = "\n".join(f"- {n}" for n in persona.style_notes)
    return (
        f"You are {persona.name} conducting a {display_name} interview.\n"
        f"Tone: {persona.tone}.\n"
        f"Skepticism level (0-1): {persona.strictness}.\n"
        f"{notes}"
    )


def _profile_block(profile: Optional[dict[str, Any]]) -> str:
    if not profile:
        return "No prior applicant profile was provided."
    lines = [f"- {k}: {v}" for k, v in profile.items()]
    return "Known applicant profile (use it, do not re-ask what you know):\n" + "\n".join(
        lines
    )


def _transcript(messages: list[BaseMessage], limit: int = 12) -> str:
    recent = messages[-limit:]
    rendered = []
    for m in recent:
        role = "Officer" if m.type == "ai" else "Applicant"
        rendered.append(f"{role}: {m.content}")
    return "\n".join(rendered) if rendered else "(the interview has not started yet)"


def greeting_messages(
    persona: OfficerPersona,
    display_name: str,
    profile: Optional[dict[str, Any]],
) -> list[BaseMessage]:
    """Generate a natural, varied opening greeting (no substantive question)."""

    style = random.choice(_OPENER_STYLES)
    nonce = random.randint(1000, 9999)
    system = SystemMessage(
        content=(
            f"{_persona_block(persona, display_name)}\n\n"
            f"{_profile_block(profile)}\n\n"
            f"{_ANTI_SCRIPT_RULES}"
        )
    )
    human = HumanMessage(
        content=(
            "The applicant has just stepped up to your window. Open with "
            f"{style}. Vary your exact wording from any standard greeting so it "
            "sounds like a real person on a particular day. Do NOT ask any "
            "substantive interview question yet. "
            f"(variation seed {nonce}; never mention it)"
        )
    )
    return [system, human]


def closing_messages(
    persona: OfficerPersona,
    display_name: str,
    messages: list[BaseMessage],
) -> list[BaseMessage]:
    """Generate a natural, varied closing line (reveals no decision)."""

    style = random.choice(_CLOSING_STYLES)
    nonce = random.randint(1000, 9999)
    system = SystemMessage(
        content=(
            f"{_persona_block(persona, display_name)}\n\n"
            f"{_ANTI_SCRIPT_RULES}\n\n"
            "Never reveal or hint at the outcome/decision in your closing."
        )
    )
    human = HumanMessage(
        content=(
            "The interview is over. Conversation so far:\n"
            f"{_transcript(messages)}\n\n"
            f"Now {style}. Keep it short and human; do not state any decision or "
            f"result. (variation seed {nonce}; never mention it)"
        )
    )
    return [system, human]


def question_messages(
    persona: OfficerPersona,
    display_name: str,
    topic: Topic,
    messages: list[BaseMessage],
    profile: Optional[dict[str, Any]],
) -> list[BaseMessage]:
    """Generate the next question fulfilling a topic's intent, in fresh words."""

    system = SystemMessage(
        content=(
            f"{_persona_block(persona, display_name)}\n\n"
            f"{_profile_block(profile)}\n\n"
            f"{_ANTI_SCRIPT_RULES}"
        )
    )
    human = HumanMessage(
        content=(
            "Conversation so far:\n"
            f"{_transcript(messages)}\n\n"
            "Now move the interview forward. Your goal for this next question:\n"
            f"INTENT: {topic.intent}\n\n"
            "Phrase a single, natural question that gets at this intent. React to "
            "what the applicant just said where it feels human (a brief "
            "acknowledgement is fine). Remember: only the spoken words."
        )
    )
    return [system, human]


def probe_messages(
    persona: OfficerPersona,
    display_name: str,
    topic: Topic,
    probe_reason: str,
    messages: list[BaseMessage],
    profile: Optional[dict[str, Any]],
) -> list[BaseMessage]:
    """Generate a targeted follow-up when something seems off."""

    system = SystemMessage(
        content=(
            f"{_persona_block(persona, display_name)}\n\n"
            f"{_ANTI_SCRIPT_RULES}\n\n"
            "You found something that needs clarification. Probe gently but "
            "directly, like a real officer who noticed an inconsistency or a "
            "vague answer."
        )
    )
    human = HumanMessage(
        content=(
            "Conversation so far:\n"
            f"{_transcript(messages)}\n\n"
            f"Topic under discussion: {topic.label} ({topic.intent})\n"
            f"What concerns you and should be probed: {probe_reason}\n\n"
            "Ask a single follow-up question that digs into this specific "
            "concern. Do not repeat your earlier wording."
        )
    )
    return [system, human]


def evaluation_messages(
    topic: Topic,
    consistency_rules: list[ConsistencyRule],
    latest_answer: str,
    messages: list[BaseMessage],
    profile: Optional[dict[str, Any]],
    strictness: float,
) -> list[BaseMessage]:
    """Build the structured-evaluation prompt for the latest answer."""

    signals = "\n".join(f"- {s}" for s in topic.expected_signals) or "- (none listed)"
    red_flags = "\n".join(f"- {r}" for r in topic.red_flags) or "- (none listed)"
    triggers = "\n".join(f"- {t}" for t in topic.probe_triggers) or "- (none listed)"
    entities = ", ".join(topic.entities) if topic.entities else "(none)"
    rules = (
        "\n".join(f"- {r.description.strip()}" for r in consistency_rules)
        or "- (none)"
    )

    system = SystemMessage(
        content=(
            "You are a meticulous visa-interview answer evaluator. Analyze the "
            "applicant's latest answer strictly and objectively against the "
            "rubric. Return the structured analysis only. Be evidence-based: "
            "only flag what is actually present. "
            f"Calibrate suspicion to the officer's skepticism level ({strictness} "
            "on a 0-1 scale): higher means probe more readily."
        )
    )
    human = HumanMessage(
        content=(
            f"TOPIC: {topic.label}\nINTENT: {topic.intent}\n\n"
            f"EXPECTED POSITIVE SIGNALS:\n{signals}\n\n"
            f"RED FLAGS TO WATCH:\n{red_flags}\n\n"
            f"PROBE TRIGGERS:\n{triggers}\n\n"
            f"ENTITIES TO EXTRACT (key = field): {entities}\n\n"
            f"CROSS-ANSWER CONSISTENCY RULES:\n{rules}\n\n"
            f"{_profile_block(profile)}\n\n"
            "FULL CONVERSATION:\n"
            f"{_transcript(messages, limit=40)}\n\n"
            f"APPLICANT'S LATEST ANSWER TO EVALUATE:\n{latest_answer}\n\n"
            "Assess: which expected signals were met, which red flags appeared, "
            "any contradictions with earlier answers or the profile, how vague "
            "the answer is, how likely it was memorized/coached, an overall "
            "answer_quality (0-1), and whether a follow-up probe is warranted "
            "(set needs_probe and a concise probe_reason). Extract the entities "
            "you can find into extracted_entities."
        )
    )
    return [system, human]


def report_narrative_messages(
    display_name: str,
    scored_summary: str,
    messages: list[BaseMessage],
) -> list[BaseMessage]:
    """Ask the LLM to synthesize the narrative portion of the report."""

    system = SystemMessage(
        content=(
            "You are writing the narrative section of a visa mock-interview "
            "report for the applicant to learn from. Be specific, constructive, "
            "and honest. Base everything strictly on the interview and the "
            "computed scores provided."
        )
    )
    human = HumanMessage(
        content=(
            f"Interview type: {display_name}\n\n"
            f"Computed scoring breakdown:\n{scored_summary}\n\n"
            "Full transcript:\n"
            f"{_transcript(messages, limit=60)}\n\n"
            "Write a concise overall summary, then list concrete strengths and "
            "concrete weaknesses / areas to improve. Ground each point in what "
            "actually happened in the interview."
        )
    )
    return [system, human]
