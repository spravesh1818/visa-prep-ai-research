"""Replay a scripted interview across multiple LLMs and compare the reports.

This is the evaluation harness for "I want to test multiple LLMs for this job".
It feeds the SAME scripted applicant answers to each configured provider/model,
runs the full interview graph, and prints a side-by-side comparison of the
resulting scores. Requires the relevant provider API keys in the environment.

Usage:
    uv run python scripts/compare_models.py \
        --country US --visa F1 \
        --model openai:gpt-4o-mini --model anthropic:claude-3-5-sonnet-latest
"""

from __future__ import annotations

import argparse
import importlib
import os
from typing import Optional

# A generic, reasonable transcript that exercises every topic. Tailor as needed.
SCRIPTED_ANSWERS = [
    "I'm pursuing a Master's in Computer Science, focusing on machine learning, "
    "because I want to specialize in applied AI.",
    "I'll be studying at MIT. I chose it for its faculty and research labs; I was "
    "also admitted to Georgia Tech and Purdue.",
    "I completed my Bachelor's in Computer Engineering in 2024 with a strong GPA, "
    "so this Master's is a natural next step.",
    "Total cost is about 80,000 dollars. My father, who runs an export business "
    "earning around 120,000 dollars a year, is sponsoring me, plus an education "
    "loan of 30,000 dollars.",
    "After graduating I plan to return home to join my family's business and our "
    "growing tech sector; my parents and property are all back home.",
    "Yes, of course.",
    "Let me clarify that point in more detail.",
]


def _reset_caches() -> None:
    """Clear cached settings/graph/checkpointer so new env takes effect."""

    for mod_name, attr in [
        ("app.config", "get_settings"),
        ("app.llm.factory", "_cached_llm"),
        ("app.session.checkpointer", "get_checkpointer"),
        ("app.interview.graph", "get_interview_graph"),
    ]:
        mod = importlib.import_module(mod_name)
        getattr(mod, attr).cache_clear()


def run_one(provider: str, model: str, country: str, visa: str) -> dict:
    os.environ["LLM_PROVIDER"] = provider
    os.environ["LLM_MODEL"] = model
    os.environ["CHECKPOINTER_BACKEND"] = "memory"
    _reset_caches()

    # Import lazily so the cache reset above is honored.
    from app.api import service

    turn = service.start_interview(country, visa, {"name": "Comparison Candidate"})
    session_id = turn["session_id"]

    last = turn
    for ans in SCRIPTED_ANSWERS:
        if last["status"] == service.STATUS_COMPLETED:
            break
        last = service.respond(session_id, ans)

    report = service.get_report(session_id).get("report") or {}
    return {
        "provider": provider,
        "model": model,
        "overall_score": report.get("overall_score"),
        "band": report.get("recommendation_band"),
        "red_flags": len(report.get("red_flags", [])),
        "coaching_signal": report.get("coaching_signal"),
        "university": (report.get("university_assessment") or {}).get("tier"),
    }


def parse_models(raw: list[str]) -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    for item in raw:
        if ":" not in item:
            raise SystemExit(f"--model must be 'provider:model', got '{item}'")
        provider, model = item.split(":", 1)
        parsed.append((provider, model))
    return parsed


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--country", default="US")
    parser.add_argument("--visa", default="F1")
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        default=[],
        help="provider:model (repeatable), e.g. openai:gpt-4o-mini",
    )
    args = parser.parse_args(argv)

    models = parse_models(args.models) or [
        ("openai", "gpt-4o-mini"),
    ]

    results = []
    for provider, model in models:
        print(f"Running {provider}:{model} ...")
        try:
            results.append(run_one(provider, model, args.country, args.visa))
        except Exception as exc:  # keep going across providers
            results.append(
                {"provider": provider, "model": model, "error": str(exc)}
            )

    header = f"{'provider':10} {'model':28} {'score':>6} {'band':>11} {'flags':>6} {'uni':>10}"
    print("\n" + header)
    print("-" * len(header))
    for r in results:
        if "error" in r:
            print(f"{r['provider']:10} {r['model']:28} ERROR: {r['error']}")
            continue
        print(
            f"{r['provider']:10} {r['model']:28} "
            f"{r['overall_score']!s:>6} {r['band']!s:>11} "
            f"{r['red_flags']!s:>6} {r['university']!s:>10}"
        )


if __name__ == "__main__":
    main()
