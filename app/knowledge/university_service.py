"""University credibility lookup.

Given a (possibly noisy) spoken university name, fuzzy-match it against the
curated dataset, determine its tier, and translate that tier into a credibility
adjustment that nudges the applicant's visa likelihood up or down.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel
from rapidfuzz import fuzz, process

DATA_PATH = Path(__file__).parent / "universities.json"

# Tokens/suffixes that add noise without changing the institution's identity.
_GENERIC_SUFFIXES = ("main campus",)
_WS = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Canonicalize a school name for matching (shared with the build script).

    Lowercases, drops a leading "the", strips punctuation, and removes generic
    campus suffixes (e.g. "-Main Campus") so registry quirks do not block exact
    matches. Meaningful campus names (e.g. "-Berkeley") are preserved.
    """

    s = name.strip().lower()
    s = s.removeprefix("the ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = _WS.sub(" ", s).strip()
    for suffix in _GENERIC_SUFFIXES:
        if s.endswith(" " + suffix):
            s = s[: -(len(suffix) + 1)].strip()
    return s

UniversityTier = Literal[
    "top", "high", "mid", "low", "recognized", "diploma_mill", "unknown"
]

# How each tier shifts the credibility component, on a -1..+1 scale.
TIER_ADJUSTMENT: dict[str, float] = {
    "top": 0.30,
    "high": 0.18,
    "mid": 0.05,
    "recognized": 0.0,
    "low": -0.18,
    "diploma_mill": -0.60,
    "unknown": -0.05,
}

TIER_SUMMARY: dict[str, str] = {
    "top": "Top-tier, highly reputable institution; strongly supports credibility.",
    "high": "Well-regarded institution; supports credibility.",
    "mid": "Recognized institution of average standing; neutral to slightly positive.",
    "recognized": "Accredited, recognized institution (not separately ranked); neutral baseline.",
    "low": "Lower-tier institution with weaker reputation; mild negative signal.",
    "diploma_mill": "Known diploma mill / fraudulent institution; major red flag.",
    "unknown": "Institution not found in the registry; treat with caution and verify.",
}

# Minimum fuzzy score (0-100) to accept a match when there is no exact hit.
MATCH_THRESHOLD = 88

# On a normalized-key collision, the more specific (curated) tier wins so that,
# e.g., a shared abbreviation maps to the ranked school rather than a generic
# "recognized" namesake.
_TIER_PRIORITY = {
    "diploma_mill": 6,
    "top": 5,
    "high": 4,
    "mid": 3,
    "low": 2,
    "recognized": 1,
    "unknown": 0,
}


class UniversityMatch(BaseModel):
    """Result of a credibility lookup."""

    raw_name: str
    matched_name: Optional[str] = None
    country: Optional[str] = None
    tier: UniversityTier = "unknown"
    match_confidence: float = 0.0
    score_adjustment: float = 0.0
    summary: str = ""


class _Entry(BaseModel):
    name: str
    country: str
    tier: str
    aliases: list[str] = []


@lru_cache(maxsize=1)
def _load_entries() -> list[_Entry]:
    with DATA_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return [_Entry.model_validate(item) for item in data["universities"]]


@lru_cache(maxsize=1)
def _lookup_index() -> dict[str, _Entry]:
    """Map every normalized surface form (name + aliases) to its entry.

    On collisions the entry whose tier has higher priority wins.
    """

    index: dict[str, _Entry] = {}

    def _consider(key: str, entry: _Entry) -> None:
        if not key:
            return
        existing = index.get(key)
        if existing is None or _TIER_PRIORITY.get(entry.tier, 0) > _TIER_PRIORITY.get(
            existing.tier, 0
        ):
            index[key] = entry

    for entry in _load_entries():
        _consider(normalize_name(entry.name), entry)
        for alias in entry.aliases:
            _consider(normalize_name(alias), entry)
    return index


def _build_match(raw: str, entry: _Entry, confidence: float) -> UniversityMatch:
    return UniversityMatch(
        raw_name=raw,
        matched_name=entry.name,
        country=entry.country,
        tier=entry.tier,  # type: ignore[arg-type]
        match_confidence=round(float(confidence), 1),
        score_adjustment=TIER_ADJUSTMENT.get(entry.tier, TIER_ADJUSTMENT["unknown"]),
        summary=TIER_SUMMARY.get(entry.tier, TIER_SUMMARY["unknown"]),
    )


def assess_university(
    raw_name: Optional[str], country_hint: Optional[str] = None
) -> UniversityMatch:
    """Match ``raw_name`` and return a credibility assessment.

    Strategy: normalize the input, try an exact normalized match first (robust
    and unambiguous), then fall back to fuzzy matching for typos. ``country_hint``
    is accepted for API symmetry; matching is global so a mis-stated country does
    not hide a valid match.
    """

    if not raw_name or not raw_name.strip():
        return UniversityMatch(
            raw_name=raw_name or "",
            tier="unknown",
            score_adjustment=TIER_ADJUSTMENT["unknown"],
            summary="No university name was provided.",
        )

    cleaned = raw_name.strip()
    normalized = normalize_name(cleaned)
    index = _lookup_index()

    # 1) Exact normalized hit - the common, unambiguous case.
    entry = index.get(normalized)
    if entry is not None:
        return _build_match(cleaned, entry, 100.0)

    # 2) Fuzzy fallback for typos / partial names.
    best = process.extractOne(
        normalized,
        list(index.keys()),
        scorer=fuzz.WRatio,
        score_cutoff=MATCH_THRESHOLD,
    )
    if best is not None:
        matched_key, confidence, _ = best
        return _build_match(cleaned, index[matched_key], confidence)

    return UniversityMatch(
        raw_name=cleaned,
        tier="unknown",
        match_confidence=0.0,
        score_adjustment=TIER_ADJUSTMENT["unknown"],
        summary=TIER_SUMMARY["unknown"],
    )
