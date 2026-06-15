"""Graph node implementations for the interview.

Flow (see graph.py for wiring):
    initialize -> greet -> ask_question -> await_answer -> evaluate_answer
    evaluate_answer --(needs probe)--> probe -> await_answer -> evaluate_answer
    evaluate_answer --(more topics)--> next_topic -> ask_question
    evaluate_answer --(done)--> finalize -> END
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.types import interrupt

from app.config import get_settings
from app.interview import prompts
from app.interview.report import (
    DISCLAIMER,
    AnswerEvaluation,
    InterviewReport,
    ReportNarrative,
)
from app.interview.scoring import compute_scores, render_scored_summary
from app.interview.state import InterviewState
from app.knowledge.university_service import UniversityMatch, assess_university
from app.llm import get_llm, llm_text
from app.llm.factory import describe_active_llm, get_structured_llm
from app.ontology import load_ontology
from app.ontology.models import Ontology, Topic

logger = logging.getLogger(__name__)

# Entity keys that should trigger a university credibility check.
_UNIVERSITY_KEYS = {"university", "provider", "institution", "school", "college"}


def _ontology(state: InterviewState) -> Ontology:
    return load_ontology(state["country"], state["visa_type"])


def _current_topic(state: InterviewState) -> Topic:
    ontology = _ontology(state)
    idx = state.get("current_topic_index", 0)
    idx = min(idx, len(ontology.topics) - 1)
    return ontology.topics[idx]


def _messages(state: InterviewState) -> list[BaseMessage]:
    return state.get("messages", [])


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #
def initialize(state: InterviewState) -> dict[str, Any]:
    """Validate config, load the ontology, and seed progress counters."""

    ontology = _ontology(state)
    return {
        "ontology_key": ontology.key,
        "topic_ids": [t.id for t in ontology.topics],
        "current_topic_index": 0,
        "probe_count": 0,
        "needs_probe": False,
        "status": "in_progress",
        "model_info": describe_active_llm(),
    }


def _officer_message(content: str, **kwargs: Any) -> AIMessage:
    """Create an officer AIMessage with turn metadata for the report transcript."""

    return AIMessage(content=content, additional_kwargs=kwargs)


def greet(state: InterviewState) -> dict[str, Any]:
    """Officer delivers a natural, varied opening greeting."""

    ontology = _ontology(state)
    llm = get_llm("interviewer")
    msg = llm.invoke(
        prompts.greeting_messages(
            ontology.officer_persona,
            ontology.display_name,
            state.get("candidate_profile"),
            timezone=ontology.timezone,
        )
    )
    return {"messages": [_officer_message(llm_text(msg), turn_kind="greeting")]}


def ask_question(state: InterviewState) -> dict[str, Any]:
    """Generate and commit the next topic question (no waiting here)."""

    ontology = _ontology(state)
    topic = _current_topic(state)
    llm = get_llm("interviewer")
    msg = llm.invoke(
        prompts.question_messages(
            ontology.officer_persona,
            ontology.display_name,
            topic,
            _messages(state),
            state.get("candidate_profile"),
        )
    )
    return {
        "messages": [
            _officer_message(
                llm_text(msg),
                turn_kind="question",
                topic_id=topic.id,
                topic_label=topic.label,
            )
        ]
    }


def await_answer(state: InterviewState) -> dict[str, Any]:
    """Pause for the applicant's answer; resumes via Command(resume=...)."""

    last_officer = next(
        (m.content for m in reversed(_messages(state)) if m.type == "ai"),
        "",
    )
    reply = interrupt({"officer_message": last_officer, "status": "awaiting_answer"})
    text = reply if isinstance(reply, str) else str(reply)
    return {"messages": [HumanMessage(content=text)]}


def evaluate_answer(state: InterviewState) -> dict[str, Any]:
    """Analyze the latest answer; extract entities; decide on probing."""

    ontology = _ontology(state)
    topic = _current_topic(state)
    settings = get_settings()

    latest_answer = next(
        (m.content for m in reversed(_messages(state)) if m.type == "human"),
        "",
    )

    llm = get_structured_llm("evaluator", AnswerEvaluation)
    try:
        evaluation: AnswerEvaluation = llm.invoke(
            prompts.evaluation_messages(
                topic,
                ontology.consistency_rules,
                latest_answer,
                _messages(state),
                state.get("candidate_profile"),
                ontology.officer_persona.strictness,
            )
        )
    except Exception:  # pragma: no cover - defensive against provider quirks
        logger.exception("Evaluation failed; using neutral fallback.")
        evaluation = AnswerEvaluation(answer_quality=0.5, rationale="Evaluation error.")

    evaluation.topic_id = topic.id

    updates: dict[str, Any] = {"evaluations": [evaluation.model_dump()]}

    # University credibility check when a school is mentioned and not yet scored.
    existing_uni = state.get("university_assessment")
    if not (existing_uni and existing_uni.get("matched_name")):
        uni_name = _extract_university(evaluation.extracted_entities)
        if uni_name:
            match: UniversityMatch = assess_university(uni_name, ontology.country)
            updates["university_assessment"] = match.model_dump()

    probe_count = state.get("probe_count", 0)
    needs_probe = bool(
        evaluation.needs_probe and probe_count < settings.max_probes_per_topic
    )
    updates["needs_probe"] = needs_probe
    return updates


def probe(state: InterviewState) -> dict[str, Any]:
    """Officer asks a targeted follow-up about the flagged concern."""

    ontology = _ontology(state)
    topic = _current_topic(state)

    probe_reason = ""
    for ev in reversed(state.get("evaluations", [])):
        if ev.get("topic_id") == topic.id:
            probe_reason = ev.get("probe_reason", "")
            break

    llm = get_llm("interviewer")
    msg = llm.invoke(
        prompts.probe_messages(
            ontology.officer_persona,
            ontology.display_name,
            topic,
            probe_reason,
            _messages(state),
            state.get("candidate_profile"),
        )
    )
    return {
        "messages": [
            _officer_message(
                llm_text(msg),
                turn_kind="probe",
                topic_id=topic.id,
                topic_label=topic.label,
                is_probe=True,
            )
        ],
        "probe_count": state.get("probe_count", 0) + 1,
    }


def next_topic(state: InterviewState) -> dict[str, Any]:
    """Advance to the next topic and reset per-topic counters."""

    return {
        "current_topic_index": state.get("current_topic_index", 0) + 1,
        "probe_count": 0,
        "needs_probe": False,
    }


def finalize(state: InterviewState) -> dict[str, Any]:
    """Compute scores, synthesize the narrative, and assemble the report."""

    ontology = _ontology(state)
    evaluations = state.get("evaluations", [])

    uni_dict = state.get("university_assessment")
    university = UniversityMatch.model_validate(uni_dict) if uni_dict else None

    scores = compute_scores(ontology, evaluations, university)
    scored_summary = render_scored_summary(scores)

    narrative = _generate_narrative(ontology.display_name, scored_summary, _messages(state))
    probing_summary = _summarize_probing(scores["topic_results"])
    closing = _generate_closing(ontology, _messages(state))
    closing_message = _officer_message(closing, turn_kind="closing")

    report = InterviewReport(
        session_id=state.get("session_id", ""),
        country=ontology.country,
        visa_type=ontology.visa_type,
        display_name=ontology.display_name,
        overall_score=scores["overall_score"],
        recommendation_band=scores["recommendation_band"],
        recommendation=scores["recommendation"],
        summary=narrative.summary,
        strengths=narrative.strengths,
        weaknesses=narrative.weaknesses,
        topic_results=scores["topic_results"],
        red_flags=scores["red_flags"],
        consistency_findings=scores["consistency_findings"],
        coaching_signal=scores["coaching_signal"],
        university_assessment=university,
        probing_summary=probing_summary,
        transcript=_render_transcript(_messages(state) + [closing_message]),
        model_info=state.get("model_info", {}),
        disclaimer=DISCLAIMER,
    )

    return {
        "status": "completed",
        "report": report.model_dump(),
        "closing_message": closing,
        "messages": [closing_message],
    }


# --------------------------------------------------------------------------- #
# Routing
# --------------------------------------------------------------------------- #
def route_after_eval(state: InterviewState) -> str:
    """Decide whether to probe, advance, or finalize."""

    if state.get("needs_probe"):
        return "probe"

    ontology = _ontology(state)
    if state.get("current_topic_index", 0) + 1 < len(ontology.topics):
        return "next_topic"
    return "finalize"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _extract_university(entities: list[Any]) -> str | None:
    for ent in entities:
        key = getattr(ent, "key", "")
        value = getattr(ent, "value", "")
        if value and any(token in key.lower() for token in _UNIVERSITY_KEYS):
            return value
    return None


def _generate_narrative(
    display_name: str, scored_summary: str, messages: list[BaseMessage]
) -> ReportNarrative:
    llm = get_structured_llm("interviewer", ReportNarrative)
    try:
        return llm.invoke(
            prompts.report_narrative_messages(display_name, scored_summary, messages)
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("Narrative generation failed; using minimal fallback.")
        return ReportNarrative(
            summary="Automated summary unavailable; see the scoring breakdown.",
            strengths=[],
            weaknesses=[],
        )


def _generate_closing(ontology: Ontology, messages: list[BaseMessage]) -> str:
    llm = get_llm("interviewer")
    try:
        msg = llm.invoke(
            prompts.closing_messages(
                ontology.officer_persona, ontology.display_name, messages
            )
        )
        text = llm_text(msg)
        if text:
            return text
    except Exception:  # pragma: no cover - defensive
        logger.exception("Closing generation failed; using fallback.")
    return "Thank you for your time. That concludes the interview."


def _summarize_probing(topic_results: list[Any]) -> str:
    probed = [t for t in topic_results if t.probes_used > 0]
    if not probed:
        return "No follow-up probes were required; answers were sufficiently clear."
    parts = [f"{t.label} ({t.probes_used} probe(s))" for t in probed]
    return "Follow-up probing was triggered on: " + ", ".join(parts) + "."


def _render_transcript(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    from app.interview.report import TranscriptEntry

    transcript: list[dict[str, Any]] = []
    for m in messages:
        role = "officer" if m.type == "ai" else "applicant"
        content = llm_text(m.content)
        if role == "applicant":
            transcript.append(
                TranscriptEntry(role="applicant", content=content).model_dump()
            )
            continue

        meta = getattr(m, "additional_kwargs", None) or {}
        transcript.append(
            TranscriptEntry(
                role="officer",
                content=content,
                turn_kind=meta.get("turn_kind"),
                topic_id=meta.get("topic_id"),
                topic_label=meta.get("topic_label"),
                is_probe=bool(meta.get("is_probe", False)),
            ).model_dump()
        )
    return transcript
