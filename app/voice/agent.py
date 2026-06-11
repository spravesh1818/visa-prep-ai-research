"""LiveKit voice agent worker for the visa interview.

Run it (after setting LiveKit/Deepgram/ElevenLabs keys in your environment):

    uv run python -m app.voice.agent dev

It connects to a LiveKit room, reads the requested country/visa type from the
joining participant's metadata, starts an ontology-driven interview, speaks the
officer's turns (Cartesia TTS by default, OpenAI/ElevenLabs optional) and
transcribes the applicant (Deepgram). The interview "brain" is the existing
LangGraph graph, via InterviewLLM.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time

from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.agents import tts as tts_base
from livekit.agents.voice.turn import TurnHandlingOptions
from livekit.plugins import cartesia, deepgram, elevenlabs, openai, silero

from app.api import service
from app.config import get_settings
from app.observability import configure_langsmith
from app.voice.cost import compute_voice_costs, push_voice_costs_to_langsmith
from app.voice.interview_llm import InterviewLLM

logger = logging.getLogger("visa-voice-agent")


def _build_stt() -> deepgram.STT:
    settings = get_settings()
    kwargs = {
        "model": settings.deepgram_model,
        "endpointing_ms": settings.deepgram_endpointing_ms,
        "smart_format": True,
        "punctuate": True,
        "filler_words": True,
    }
    if settings.deepgram_api_key:
        kwargs["api_key"] = settings.deepgram_api_key
    return deepgram.STT(**kwargs)


def _select_cartesia_voice(country: str) -> str:
    settings = get_settings()
    if settings.cartesia_voice:
        return settings.cartesia_voice
    region = "uk" if country.strip().upper() in {"UK", "GB", "GBR"} else "us"
    gender = random.choice(["male", "female"])
    voice = {
        ("uk", "male"): settings.cartesia_voice_uk_male,
        ("uk", "female"): settings.cartesia_voice_uk_female,
        ("us", "male"): settings.cartesia_voice_us_male,
        ("us", "female"): settings.cartesia_voice_us_female,
    }[(region, gender)]
    logger.info("Selected Cartesia voice: region=%s gender=%s voice=%s", region, gender, voice)
    return voice


def _build_cartesia_tts(voice: str | None = None) -> cartesia.TTS:
    settings = get_settings()
    kwargs = {"model": settings.cartesia_model}
    voice = voice or settings.cartesia_voice
    if voice:
        kwargs["voice"] = voice
    if settings.cartesia_api_key:
        kwargs["api_key"] = settings.cartesia_api_key
    return cartesia.TTS(**kwargs)


def _build_openai_tts() -> openai.TTS:
    settings = get_settings()
    kwargs = {
        "model": settings.openai_tts_model,
        "voice": settings.openai_tts_voice,
    }
    if settings.openai_api_key:
        kwargs["api_key"] = settings.openai_api_key
    return openai.TTS(**kwargs)


def _build_elevenlabs_tts() -> elevenlabs.TTS:
    settings = get_settings()
    kwargs = {"model": settings.elevenlabs_model}
    if settings.elevenlabs_voice_id:
        kwargs["voice_id"] = settings.elevenlabs_voice_id
    if settings.elevenlabs_api_key:
        kwargs["api_key"] = settings.elevenlabs_api_key
    return elevenlabs.TTS(**kwargs)


def _build_tts(country: str) -> tts_base.TTS:
    settings = get_settings()
    if settings.tts_provider == "elevenlabs":
        return _build_elevenlabs_tts()
    if settings.tts_provider == "openai":
        return _build_openai_tts()
    return _build_cartesia_tts(_select_cartesia_voice(country))


async def entrypoint(ctx: JobContext) -> None:
    configure_langsmith()
    settings = get_settings()
    started_at = time.monotonic()
    await ctx.connect()

    participant = await ctx.wait_for_participant()
    try:
        meta = json.loads(participant.metadata or "{}")
    except json.JSONDecodeError:
        meta = {}

    country = meta.get("country") or settings.voice_default_country
    visa_type = meta.get("visa_type") or settings.voice_default_visa_type
    profile = meta.get("candidate_profile")

    # Start the ontology-driven interview; this yields the greeting + first Q.
    turn = await asyncio.to_thread(service.start_interview, country, visa_type, profile)
    session_id = turn["session_id"]
    greeting = turn["officer_message"]
    logger.info("Voice interview %s started (%s %s)", session_id, country, visa_type)

    # Tell the frontend which session to poll for the final report.
    await ctx.room.local_participant.publish_data(
        json.dumps({"type": "session", "session_id": session_id}).encode(),
        topic="interview",
    )

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=_build_stt(),
        llm=InterviewLLM(session_id),
        tts=_build_tts(country),
        turn_handling=TurnHandlingOptions(
            endpointing={
                "mode": "fixed",
                "min_delay": settings.voice_min_endpointing_delay,
                "max_delay": settings.voice_max_endpointing_delay,
            },
            preemptive_generation={"enabled": False},
        ),
    )

    async def _emit_costs(_reason: str = "") -> None:
        duration = time.monotonic() - started_at
        breakdown = compute_voice_costs(session_id, session.usage, duration)
        await asyncio.to_thread(push_voice_costs_to_langsmith, breakdown)
        logger.info(
            "Interview cost (voice infra): stt=$%.4f tts=$%.4f livekit=$%.4f "
            "total_voice=$%.4f session=%s",
            breakdown.stt_usd,
            breakdown.tts_usd,
            breakdown.livekit_usd,
            breakdown.voice_infra_usd,
            session_id,
        )

    ctx.add_shutdown_callback(_emit_costs)

    # Instructions are unused for text generation (InterviewLLM drives content),
    # but the Agent object is required by the session.
    agent = Agent(instructions="You are a consular visa interview officer.")
    await session.start(agent=agent, room=ctx.room)

    # Speak the dynamically generated greeting + first question.
    await session.say(greeting, allow_interruptions=True)


def main() -> None:
    settings = get_settings()
    options = WorkerOptions(entrypoint_fnc=entrypoint)
    if settings.livekit_url:
        options.ws_url = settings.livekit_url
    if settings.livekit_api_key:
        options.api_key = settings.livekit_api_key
    if settings.livekit_api_secret:
        options.api_secret = settings.livekit_api_secret
    cli.run_app(options)


if __name__ == "__main__":
    main()
