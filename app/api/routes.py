"""FastAPI routes for the visa interview."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

import json
import uuid

from app.api import service
from app.api.schemas import (
    ConfigResponse,
    InterviewTurnResponse,
    ReportResponse,
    RespondRequest,
    StartInterviewRequest,
    VoiceTokenRequest,
    VoiceTokenResponse,
)
from app.config import get_settings
from app.llm.factory import describe_active_llm
from app.ontology import OntologyNotFoundError, available_ontologies

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/config", response_model=ConfigResponse)
def config() -> ConfigResponse:
    settings = get_settings()
    return ConfigResponse(
        llm=describe_active_llm(),
        checkpointer_backend=settings.checkpointer_backend,
        max_probes_per_topic=settings.max_probes_per_topic,
        supported_interviews=available_ontologies(),
        voice_enabled=settings.voice_enabled,
    )


@router.post("/interview/start", response_model=InterviewTurnResponse)
def start_interview(payload: StartInterviewRequest) -> InterviewTurnResponse:
    try:
        result = service.start_interview(
            payload.country, payload.visa_type, payload.candidate_profile
        )
    except OntologyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return InterviewTurnResponse(**result)


@router.post("/interview/{session_id}/respond", response_model=InterviewTurnResponse)
def respond(session_id: str, payload: RespondRequest) -> InterviewTurnResponse:
    try:
        result = service.respond(session_id, payload.message)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if result.get("status") == service.STATUS_COMPLETED:
        service.maybe_deliver_report(session_id)

    return InterviewTurnResponse(**result)


@router.post("/voice/token", response_model=VoiceTokenResponse)
def voice_token(payload: VoiceTokenRequest) -> VoiceTokenResponse:
    """Mint a LiveKit access token so the React client can join a voice room.

    The requested country/visa type is embedded in the participant metadata so
    the voice agent knows which ontology-driven interview to run.
    """

    settings = get_settings()
    if not settings.voice_enabled:
        raise HTTPException(
            status_code=503,
            detail="Voice is not configured (set LIVEKIT_URL/API_KEY/API_SECRET).",
        )

    from app.ontology import load_ontology

    try:
        load_ontology(payload.country, payload.visa_type)
    except OntologyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    from livekit import api as lk_api

    room = f"visa-{uuid.uuid4().hex[:10]}"
    identity = f"applicant-{uuid.uuid4().hex[:8]}"
    metadata = json.dumps(
        {
            "country": payload.country,
            "visa_type": payload.visa_type,
            "candidate_profile": payload.candidate_profile or {},
        }
    )

    token = (
        lk_api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name("Applicant")
        .with_metadata(metadata)
        .with_grants(lk_api.VideoGrants(room_join=True, room=room))
        .to_jwt()
    )

    return VoiceTokenResponse(
        url=settings.livekit_url, token=token, room=room, identity=identity
    )


@router.get("/interview/{session_id}/report", response_model=ReportResponse)
def report(session_id: str) -> ReportResponse:
    try:
        data = service.get_report(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if data.get("status") != service.STATUS_COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=f"Report not ready; interview status is '{data.get('status')}'.",
        )
    return ReportResponse(**data)
