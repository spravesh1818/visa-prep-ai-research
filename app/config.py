"""Application configuration loaded from environment variables.

A single ``Settings`` object is the source of truth for which LLM provider/model
to use, how sessions are persisted, and where (optionally) to push finished
reports. Nothing about the interview behaviour is hardcoded here beyond knobs.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal[
    "openai", "anthropic", "google", "ollama", "deepseek", "moonshot"
]
CheckpointerBackend = Literal["memory", "sqlite"]


class Settings(BaseSettings):
    """Central settings, populated from the environment / a ``.env`` file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core LLM selection (the "central LLM" used everywhere) -------------
    llm_provider: LLMProvider = Field(
        default="openai",
        description="Which provider the LLM factory builds by default.",
    )
    llm_model: str = Field(
        default="gpt-4o-mini",
        description="Default model id for the selected provider.",
    )
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_max_tokens: Optional[int] = Field(default=None)

    # --- Optional per-role overrides --------------------------------------
    # The interviewer benefits from a more creative model; the evaluator from a
    # cheaper/deterministic one. Leave unset to reuse the defaults above.
    interviewer_model: Optional[str] = None
    interviewer_temperature: Optional[float] = Field(default=0.85, ge=0.0, le=2.0)
    evaluator_model: Optional[str] = None
    evaluator_temperature: Optional[float] = Field(default=0.0)

    # --- Provider credentials / endpoints ---------------------------------
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"
    deepseek_api_key: Optional[str] = None
    moonshot_api_key: Optional[str] = None
    moonshot_base_url: str = "https://api.moonshot.ai/v1"

    # --- Interview behaviour knobs ----------------------------------------
    max_probes_per_topic: int = Field(default=2, ge=0, le=5)

    # --- Session persistence ----------------------------------------------
    checkpointer_backend: CheckpointerBackend = "sqlite"
    sqlite_path: str = "./interview_sessions.db"

    # --- Report delivery to the backend -----------------------------------
    report_webhook_url: Optional[str] = Field(
        default=None,
        description="If set, completed reports are POSTed here for the BE.",
    )

    # --- Voice interview (LiveKit + Deepgram + ElevenLabs) -----------------
    livekit_url: Optional[str] = None
    livekit_api_key: Optional[str] = None
    livekit_api_secret: Optional[str] = None
    deepgram_api_key: Optional[str] = None
    deepgram_model: str = "nova-3"
    deepgram_endpointing_ms: int = Field(default=400, ge=0)
    voice_min_endpointing_delay: float = Field(default=1.2, ge=0.0)
    voice_max_endpointing_delay: float = Field(default=6.0, ge=0.0)
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_voice_id: Optional[str] = None
    elevenlabs_model: str = "eleven_turbo_v2_5"
    # TTS provider for the voice agent: "cartesia", "openai", or "elevenlabs".
    tts_provider: Literal["cartesia", "openai", "elevenlabs"] = "cartesia"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "alloy"
    cartesia_api_key: Optional[str] = None
    cartesia_model: str = "sonic-2"
    cartesia_voice: Optional[str] = None  # global override; skips region shuffle if set
    cartesia_voice_uk_male: str = "4bc3cb8c-adb9-4bb8-b5d5-cbbef950b991"
    cartesia_voice_uk_female: str = "dc30854e-e398-4579-9dc8-16f6cb2c19b9"
    cartesia_voice_us_male: str = "a167e0f3-df7e-4d52-a9c3-f949145efdab"
    cartesia_voice_us_female: str = "10bd4af4-825b-49b8-b8bd-0ca11865536e"
    # Fallback interview type for voice when the client sends none.
    voice_default_country: str = "US"
    voice_default_visa_type: str = "F1"

    @property
    def voice_enabled(self) -> bool:
        return bool(
            self.livekit_url and self.livekit_api_key and self.livekit_api_secret
        )

    # --- Observability -----------------------------------------------------
    langsmith_tracing: bool = False
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "visa-interviewer"
    # Estimated USD rates for voice infra (calibrate against provider invoices).
    cost_deepgram_stt_usd_per_min: float = 0.0048
    cost_cartesia_tts_usd_per_min: float = 0.05
    cost_livekit_agent_usd_per_min: float = 0.01

    # --- HTTP server -------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""

    return Settings()
