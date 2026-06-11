"""Shared observability setup (LangSmith tracing)."""

from __future__ import annotations

import os

from app.config import get_settings


def configure_langsmith() -> None:
    """Enable LangSmith tracing when requested via environment settings."""

    settings = get_settings()
    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
