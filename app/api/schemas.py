"""Request/response models for the interview API."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.interview.report import InterviewReport


class StartInterviewRequest(BaseModel):
    country: str = Field(examples=["US", "UK"])
    visa_type: str = Field(examples=["F1", "J1", "B1B2", "H1B", "Student"])
    candidate_profile: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional known facts (name, prior education, sponsor, etc.).",
    )


class InterviewTurnResponse(BaseModel):
    session_id: str
    officer_message: str
    status: str  # "awaiting_answer" | "completed"
    report_available: bool = False


class RespondRequest(BaseModel):
    message: str = Field(min_length=1, description="The applicant's answer.")


class OntologyInfo(BaseModel):
    key: str
    country: str
    visa_type: str
    display_name: str


class ConfigResponse(BaseModel):
    llm: dict[str, Any]
    checkpointer_backend: str
    max_probes_per_topic: int
    supported_interviews: list[OntologyInfo]
    voice_enabled: bool = False


class ReportResponse(BaseModel):
    session_id: str
    status: str
    report: Optional[InterviewReport] = None


class VoiceTokenRequest(BaseModel):
    country: str = Field(examples=["US", "UK"])
    visa_type: str = Field(examples=["F1", "Student"])
    candidate_profile: Optional[dict[str, Any]] = None


class VoiceTokenResponse(BaseModel):
    url: str
    token: str
    room: str
    identity: str
