"""LangGraph state definition for an interview session."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class InterviewState(TypedDict, total=False):
    """Mutable state carried through the interview graph.

    ``messages`` is the running transcript (officer + applicant turns).
    ``evaluations`` accumulates one structured analysis per answered turn.
    """

    # Configuration captured at session start.
    session_id: str
    country: str
    visa_type: str
    ontology_key: str
    candidate_profile: dict[str, Any]
    model_info: dict[str, Any]

    # Conversation transcript (reduced via add_messages).
    messages: Annotated[list, add_messages]

    # Interview progress.
    topic_ids: list[str]
    current_topic_index: int
    probe_count: int
    needs_probe: bool

    # Accumulated analysis (appended via operator.add).
    evaluations: Annotated[list[dict[str, Any]], operator.add]
    university_assessment: Optional[dict[str, Any]]

    # Completion.
    status: str  # "in_progress" | "completed"
    report: Optional[dict[str, Any]]
    closing_message: str
