"""Checkpointer factory.

The checkpointer is what makes the interview multi-turn: it persists graph state
between HTTP requests, keyed by ``thread_id`` (our session id). ``interrupt()``
relies on it to pause and later resume.

- ``memory``: fast, in-process. NOT shared across uvicorn workers - dev only.
- ``sqlite``: file-backed, survives restarts, safe for a single worker.

For production multi-worker deployments, swap in ``PostgresSaver`` (the graph
code is agnostic to which checkpointer is used).
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache

from langgraph.checkpoint.base import BaseCheckpointSaver

from app.config import get_settings


@lru_cache(maxsize=1)
def get_checkpointer() -> BaseCheckpointSaver:
    """Build (once) and return the configured checkpointer."""

    settings = get_settings()

    if settings.checkpointer_backend == "memory":
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()

    if settings.checkpointer_backend == "sqlite":
        from langgraph.checkpoint.sqlite import SqliteSaver

        conn = sqlite3.connect(settings.sqlite_path, check_same_thread=False)
        saver = SqliteSaver(conn)
        saver.setup()
        return saver

    raise ValueError(
        f"Unknown checkpointer backend '{settings.checkpointer_backend}'."
    )
