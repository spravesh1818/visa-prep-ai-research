"""Voice interview cost estimation and LangSmith cost runs."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from livekit.agents.metrics import AgentSessionUsage
from livekit.agents.metrics.usage import STTModelUsage, TTSModelUsage

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class InterviewCostBreakdown:
    session_id: str
    stt_usd: float
    tts_usd: float
    livekit_usd: float
    stt_audio_seconds: float
    tts_audio_seconds: float
    tts_characters: int
    session_duration_seconds: float

    @property
    def voice_infra_usd(self) -> float:
        return self.stt_usd + self.tts_usd + self.livekit_usd


def compute_voice_costs(
    session_id: str,
    usage: AgentSessionUsage,
    session_duration_seconds: float,
) -> InterviewCostBreakdown:
    """Estimate STT/TTS/LiveKit USD from AgentSession usage metrics."""

    settings = get_settings()
    stt_audio_seconds = 0.0
    tts_audio_seconds = 0.0
    tts_characters = 0

    for entry in usage.model_usage:
        if isinstance(entry, STTModelUsage):
            stt_audio_seconds += entry.audio_duration
        elif isinstance(entry, TTSModelUsage):
            tts_audio_seconds += entry.audio_duration
            tts_characters += entry.characters_count

    stt_usd = (stt_audio_seconds / 60.0) * settings.cost_deepgram_stt_usd_per_min
    if tts_audio_seconds > 0:
        tts_usd = (tts_audio_seconds / 60.0) * settings.cost_cartesia_tts_usd_per_min
    elif tts_characters > 0:
        tts_usd = (tts_characters / 1000.0) * settings.cost_cartesia_tts_usd_per_min
    else:
        tts_usd = 0.0
    livekit_usd = (
        session_duration_seconds / 60.0
    ) * settings.cost_livekit_agent_usd_per_min

    return InterviewCostBreakdown(
        session_id=session_id,
        stt_usd=stt_usd,
        tts_usd=tts_usd,
        livekit_usd=livekit_usd,
        stt_audio_seconds=stt_audio_seconds,
        tts_audio_seconds=tts_audio_seconds,
        tts_characters=tts_characters,
        session_duration_seconds=session_duration_seconds,
    )


def _set_thread_metadata(session_id: str) -> None:
    try:
        from langsmith import get_current_run_tree

        run_tree = get_current_run_tree()
        if run_tree is not None:
            run_tree.metadata["thread_id"] = session_id
    except ImportError:
        pass


def push_voice_costs_to_langsmith(breakdown: InterviewCostBreakdown) -> None:
    """Emit estimated voice infra costs as LangSmith runs on the interview thread."""

    settings = get_settings()
    if not settings.langsmith_tracing or not settings.langsmith_api_key:
        return

    try:
        from langsmith import traceable
    except ImportError:
        logger.warning("langsmith not installed; skipping voice cost export.")
        return

    @traceable(name="deepgram_stt", run_type="tool")
    def _stt_run() -> dict:
        _set_thread_metadata(breakdown.session_id)
        return {
            "audio_duration_sec": breakdown.stt_audio_seconds,
            "estimated_usd": breakdown.stt_usd,
            "usage_metadata": {"total_cost": breakdown.stt_usd},
        }

    @traceable(name="cartesia_tts", run_type="tool")
    def _tts_run() -> dict:
        _set_thread_metadata(breakdown.session_id)
        return {
            "audio_duration_sec": breakdown.tts_audio_seconds,
            "characters": breakdown.tts_characters,
            "estimated_usd": breakdown.tts_usd,
            "usage_metadata": {"total_cost": breakdown.tts_usd},
        }

    @traceable(name="livekit_session", run_type="tool")
    def _livekit_run() -> dict:
        _set_thread_metadata(breakdown.session_id)
        return {
            "session_duration_sec": breakdown.session_duration_seconds,
            "estimated_usd": breakdown.livekit_usd,
            "usage_metadata": {"total_cost": breakdown.livekit_usd},
        }

    @traceable(name="interview_voice_cost", run_type="chain")
    def _summary_run() -> dict:
        _set_thread_metadata(breakdown.session_id)
        _stt_run()
        _tts_run()
        _livekit_run()
        return {
            "session_id": breakdown.session_id,
            "stt_usd": breakdown.stt_usd,
            "tts_usd": breakdown.tts_usd,
            "livekit_usd": breakdown.livekit_usd,
            "voice_infra_usd": breakdown.voice_infra_usd,
        }

    _summary_run()
