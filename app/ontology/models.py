"""Pydantic schema for the visa-interview ontology.

The ontology is intentionally *intent-driven*: it never stores literal question
text. Each topic describes what the officer wants to learn, what good answers
look like, and what should trigger suspicion. The LLM turns intents into fresh,
human-sounding questions at runtime.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class OfficerPersona(BaseModel):
    """How the simulated officer behaves and sounds."""

    name: str = Field(default="Consular Officer")
    tone: str = Field(
        default="professional, calm, courteous but probing",
        description="Free-text tone guidance fed to the question generator.",
    )
    strictness: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="0 = lenient, 1 = highly skeptical. Influences probing.",
    )
    style_notes: list[str] = Field(default_factory=list)


class Topic(BaseModel):
    """A single dimension of the interview the officer must cover."""

    id: str
    label: str = Field(description="Human-readable topic name for the report.")
    intent: str = Field(
        description="What the officer is trying to learn. NOT a literal question."
    )
    weight: float = Field(
        default=1.0,
        gt=0.0,
        description="Relative importance when aggregating the final score.",
    )
    expected_signals: list[str] = Field(
        default_factory=list,
        description="Things a strong, credible answer would contain.",
    )
    red_flags: list[str] = Field(
        default_factory=list,
        description="Patterns that should lower the score / trigger probing.",
    )
    probe_triggers: list[str] = Field(
        default_factory=list,
        description="Conditions under which a follow-up question is warranted.",
    )
    entities: list[str] = Field(
        default_factory=list,
        description="Structured facts to extract (e.g. university, funding_source).",
    )
    required: bool = Field(default=True)


class ConsistencyRule(BaseModel):
    """A cross-topic contradiction the evaluator should watch for."""

    id: str
    description: str
    related_topics: list[str] = Field(default_factory=list)


class Ontology(BaseModel):
    """The full interview ontology for one country + visa type."""

    country: str
    visa_type: str
    display_name: str
    description: str = ""
    officer_persona: OfficerPersona = Field(default_factory=OfficerPersona)
    topics: list[Topic]
    consistency_rules: list[ConsistencyRule] = Field(default_factory=list)

    @field_validator("topics")
    @classmethod
    def _non_empty_topics(cls, value: list[Topic]) -> list[Topic]:
        if not value:
            raise ValueError("An ontology must define at least one topic.")
        ids = [t.id for t in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Topic ids must be unique within an ontology.")
        return value

    @property
    def key(self) -> str:
        """Canonical lookup key, e.g. ``us_f1``."""

        return f"{self.country.lower()}_{self.visa_type.lower()}"

    def topic_by_id(self, topic_id: str) -> Optional[Topic]:
        return next((t for t in self.topics if t.id == topic_id), None)

    def total_weight(self) -> float:
        return sum(t.weight for t in self.topics)
