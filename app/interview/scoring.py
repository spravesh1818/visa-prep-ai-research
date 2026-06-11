"""Deterministic scoring that turns evaluations + university tier into a score.

The LLM produces per-answer judgments; this module aggregates them into a
transparent, weighted score so results are explainable and reproducible.
"""

from __future__ import annotations

from typing import Any, Optional

from app.interview.report import RecommendationBand, TopicResult
from app.knowledge.university_service import UniversityMatch
from app.ontology.models import Ontology

# Penalties applied to a topic's base quality score.
_RED_FLAG_PENALTY = 0.12
_INCONSISTENCY_PENALTY = 0.18
_VAGUENESS_PENALTY = 0.10

# Global penalty for coached/memorized answers (applied to overall).
_COACHING_PENALTY_WEIGHT = 0.15


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _latest_eval_per_topic(
    evaluations: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Keep the most recent evaluation for each topic (post-probe)."""

    latest: dict[str, dict[str, Any]] = {}
    for ev in evaluations:
        topic_id = ev.get("topic_id")
        if topic_id:
            latest[topic_id] = ev
    return latest


def _probe_counts(evaluations: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ev in evaluations:
        topic_id = ev.get("topic_id")
        if topic_id:
            counts[topic_id] = counts.get(topic_id, 0) + 1
    # First answer per topic is not a probe; subtract one.
    return {k: max(0, v - 1) for k, v in counts.items()}


def _band(score_100: float) -> tuple[RecommendationBand, str]:
    if score_100 >= 78:
        return "Strong", "Strong likelihood of approval in a real interview."
    if score_100 >= 60:
        return "Likely", "Likely to approve, with minor concerns to address."
    if score_100 >= 42:
        return "Borderline", "Borderline; notable concerns could lead to refusal."
    return "Weak", "Weak; significant concerns likely to result in refusal."


def score_topic(
    topic_id: str,
    label: str,
    weight: float,
    evaluation: Optional[dict[str, Any]],
) -> TopicResult:
    """Compute a 0-1 score for a single topic from its latest evaluation."""

    if evaluation is None:
        return TopicResult(
            topic_id=topic_id,
            label=label,
            score=0.0,
            weight=weight,
            summary="Topic was not covered in the interview.",
        )

    base = float(evaluation.get("answer_quality", 0.5))
    red_flags = list(evaluation.get("detected_red_flags", []))
    inconsistencies = list(evaluation.get("inconsistencies", []))
    vagueness = float(evaluation.get("vagueness", 0.0))

    score = base
    score -= _RED_FLAG_PENALTY * len(red_flags)
    score -= _INCONSISTENCY_PENALTY * len(inconsistencies)
    score -= _VAGUENESS_PENALTY * vagueness
    score = _clamp(score)

    return TopicResult(
        topic_id=topic_id,
        label=label,
        score=round(score, 3),
        weight=weight,
        red_flags=red_flags,
        inconsistencies=inconsistencies,
        summary=str(evaluation.get("rationale", "")),
    )


def compute_scores(
    ontology: Ontology,
    evaluations: list[dict[str, Any]],
    university: Optional[UniversityMatch],
) -> dict[str, Any]:
    """Aggregate everything into the final scored breakdown.

    Returns a dict with topic_results, overall_score (0-100), band,
    recommendation, collected red flags / inconsistencies, coaching signal,
    and the university adjustment that was applied.
    """

    latest = _latest_eval_per_topic(evaluations)
    probes = _probe_counts(evaluations)

    topic_results: list[TopicResult] = []
    for topic in ontology.topics:
        ev = latest.get(topic.id)
        result = score_topic(topic.id, topic.label, topic.weight, ev)
        result.probes_used = probes.get(topic.id, 0)
        topic_results.append(result)

    total_weight = sum(t.weight for t in topic_results) or 1.0
    weighted = sum(t.score * t.weight for t in topic_results) / total_weight

    # University credibility nudges the overall score (scaled down so it is
    # influential but not solely decisive).
    uni_adjustment = 0.0
    if university is not None:
        uni_adjustment = 0.5 * university.score_adjustment

    # Coaching/memorization penalty from the worst offending answer.
    coaching_signal = max(
        (float(ev.get("coached_likelihood", 0.0)) for ev in latest.values()),
        default=0.0,
    )

    overall = weighted + uni_adjustment - _COACHING_PENALTY_WEIGHT * coaching_signal
    overall = _clamp(overall)
    overall_100 = round(overall * 100, 1)

    band, recommendation = _band(overall_100)

    red_flags: list[str] = []
    inconsistencies: list[str] = []
    for t in topic_results:
        red_flags.extend(f"[{t.label}] {rf}" for rf in t.red_flags)
        inconsistencies.extend(f"[{t.label}] {ic}" for ic in t.inconsistencies)

    return {
        "topic_results": topic_results,
        "overall_score": overall_100,
        "recommendation_band": band,
        "recommendation": recommendation,
        "red_flags": red_flags,
        "consistency_findings": inconsistencies,
        "coaching_signal": round(coaching_signal, 3),
        "university_adjustment": round(uni_adjustment, 3),
    }


def render_scored_summary(scores: dict[str, Any]) -> str:
    """Human-readable scoring summary fed to the report-narrative LLM."""

    lines = [
        f"Overall: {scores['overall_score']}/100 "
        f"({scores['recommendation_band']})",
        "Per-topic scores:",
    ]
    for t in scores["topic_results"]:
        lines.append(
            f"  - {t.label}: {round(t.score * 100)}/100 "
            f"(weight {t.weight}, probes {t.probes_used})"
        )
    if scores["red_flags"]:
        lines.append("Red flags: " + "; ".join(scores["red_flags"]))
    if scores["consistency_findings"]:
        lines.append("Inconsistencies: " + "; ".join(scores["consistency_findings"]))
    if scores["coaching_signal"]:
        lines.append(f"Coaching/memorization signal: {scores['coaching_signal']}")
    return "\n".join(lines)
