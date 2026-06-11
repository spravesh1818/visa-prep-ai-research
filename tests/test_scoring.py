"""Scoring engine tests (pure functions, no LLM)."""

from app.interview.report import AnswerEvaluation
from app.interview.scoring import compute_scores
from app.knowledge.university_service import assess_university
from app.ontology import load_ontology


def _eval(topic_id, **kwargs):
    ev = AnswerEvaluation(**kwargs)
    ev.topic_id = topic_id
    return ev.model_dump()


def test_top_university_raises_overall_vs_diploma_mill():
    ontology = load_ontology("US", "F1")
    evaluations = [
        _eval(t.id, answer_quality=0.7) for t in ontology.topics
    ]

    strong = compute_scores(ontology, evaluations, assess_university("MIT"))
    weak = compute_scores(
        ontology, evaluations, assess_university("University of Farmington")
    )

    assert strong["overall_score"] > weak["overall_score"]
    assert strong["university_adjustment"] > weak["university_adjustment"]


def test_red_flags_and_inconsistencies_lower_topic_score():
    ontology = load_ontology("US", "F1")
    clean = compute_scores(
        ontology, [_eval(t.id, answer_quality=0.8) for t in ontology.topics], None
    )
    flagged = compute_scores(
        ontology,
        [
            _eval(
                t.id,
                answer_quality=0.8,
                detected_red_flags=["vague"],
                inconsistencies=["contradiction"],
            )
            for t in ontology.topics
        ],
        None,
    )
    assert flagged["overall_score"] < clean["overall_score"]
    assert flagged["red_flags"]
    assert flagged["consistency_findings"]


def test_recommendation_band_present():
    ontology = load_ontology("US", "F1")
    scores = compute_scores(
        ontology, [_eval(t.id, answer_quality=0.9) for t in ontology.topics], None
    )
    assert scores["recommendation_band"] in {"Strong", "Likely", "Borderline", "Weak"}
