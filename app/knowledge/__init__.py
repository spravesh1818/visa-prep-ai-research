"""Curated knowledge: university credibility tiers and lookup service."""

from app.knowledge.university_service import (
    UniversityMatch,
    UniversityTier,
    assess_university,
)

__all__ = ["UniversityMatch", "UniversityTier", "assess_university"]
