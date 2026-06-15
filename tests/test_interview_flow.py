"""End-to-end interview flow tests using a fake LLM (offline)."""

from app.api import service
from app.ontology import load_ontology


def _run_to_completion(country, visa_type, answers):
    turn = service.start_interview(country, visa_type, {"name": "Test Applicant"})
    session_id = turn["session_id"]
    assert turn["status"] == service.STATUS_AWAITING
    assert turn["officer_message"]

    last = turn
    for ans in answers:
        if last["status"] == service.STATUS_COMPLETED:
            break
        last = service.respond(session_id, ans)
    return session_id, last


def test_full_interview_produces_report(fake_llm):
    ontology = load_ontology("US", "F1")
    answers = [f"My detailed answer about topic {i}" for i in range(len(ontology.topics))]

    session_id, last = _run_to_completion("US", "F1", answers)

    assert last["status"] == service.STATUS_COMPLETED
    assert last["report_available"] is True

    # The closing is LLM-generated (not the old hardcoded constant).
    assert last["officer_message"]
    assert last["officer_message"] != "Thank you. That concludes the interview."

    data = service.get_report(session_id)
    assert data["status"] == service.STATUS_COMPLETED
    report = data["report"]

    assert report["session_id"] == session_id
    assert 0 <= report["overall_score"] <= 100
    assert report["recommendation_band"] in {"Strong", "Likely", "Borderline", "Weak"}
    assert len(report["topic_results"]) == len(ontology.topics)
    # University was extracted (MIT) and assessed as top tier.
    assert report["university_assessment"]["tier"] == "top"
    assert report["transcript"]
    assert report["disclaimer"]

    officer_turns = [t for t in report["transcript"] if t["role"] == "officer"]
    turn_kinds = {t.get("turn_kind") for t in officer_turns}
    assert "greeting" in turn_kinds
    assert "question" in turn_kinds
    assert "closing" in turn_kinds


def test_greeting_then_first_question_on_start(fake_llm):
    turn = service.start_interview("UK", "Student", None)
    # The first turn bundles greeting + first question (two officer utterances).
    assert "\n\n" in turn["officer_message"]


def test_probing_triggers_followup(fake_llm):
    from app.interview.report import AnswerEvaluation

    # Make the first evaluation request a probe, the rest clean.
    state = {"first": True}

    def factory():
        if state["first"]:
            state["first"] = False
            return AnswerEvaluation(
                answer_quality=0.4,
                needs_probe=True,
                probe_reason="Answer was vague about funding source.",
            )
        return AnswerEvaluation(answer_quality=0.8, needs_probe=False)

    fake_llm["factory"] = factory

    ontology = load_ontology("US", "F1")
    # One extra answer to account for the probe turn.
    answers = ["ans"] * (len(ontology.topics) + 2)
    session_id, last = _run_to_completion("US", "F1", answers)

    assert last["status"] == service.STATUS_COMPLETED
    report = service.get_report(session_id)["report"]
    probes = sum(t["probes_used"] for t in report["topic_results"])
    assert probes >= 1

    probe_turns = [
        t
        for t in report["transcript"]
        if t.get("role") == "officer" and t.get("turn_kind") == "probe"
    ]
    assert len(probe_turns) >= 1
    assert probe_turns[0].get("is_probe") is True


def test_unknown_session_raises():
    import pytest

    with pytest.raises(KeyError):
        service.respond("does-not-exist", "hello")
