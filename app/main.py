"""FastAPI application entrypoint."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.observability import configure_langsmith


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    configure_langsmith()

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
