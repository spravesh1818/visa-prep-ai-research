"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings


def _configure_observability() -> None:
    """Enable LangSmith tracing if requested (purely opt-in via env)."""

    settings = get_settings()
    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    _configure_observability()

    app = FastAPI(
        title="Ontology-Driven Visa Interviewer",
        version="0.1.0",
        description=(
            "A multi-turn, ontology-driven mock visa interview powered by "
            "LangGraph. Questions are generated dynamically from intents, "
            "answers are probed when something is off, universities are "
            "credibility-checked, and a detailed report is produced."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
