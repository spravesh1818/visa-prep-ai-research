"""Assemble the interview StateGraph and compile it with a checkpointer."""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.interview import nodes
from app.interview.state import InterviewState
from app.session import get_checkpointer


def build_interview_graph() -> StateGraph:
    """Construct (but do not compile) the interview graph."""

    graph = StateGraph(InterviewState)

    graph.add_node("initialize", nodes.initialize)
    graph.add_node("greet", nodes.greet)
    graph.add_node("ask_question", nodes.ask_question)
    graph.add_node("await_answer", nodes.await_answer)
    graph.add_node("evaluate_answer", nodes.evaluate_answer)
    graph.add_node("probe", nodes.probe)
    graph.add_node("next_topic", nodes.next_topic)
    graph.add_node("finalize", nodes.finalize)

    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "greet")
    graph.add_edge("greet", "ask_question")
    graph.add_edge("ask_question", "await_answer")
    graph.add_edge("await_answer", "evaluate_answer")

    graph.add_conditional_edges(
        "evaluate_answer",
        nodes.route_after_eval,
        {
            "probe": "probe",
            "next_topic": "next_topic",
            "finalize": "finalize",
        },
    )

    graph.add_edge("probe", "await_answer")
    graph.add_edge("next_topic", "ask_question")
    graph.add_edge("finalize", END)

    return graph


@lru_cache(maxsize=1)
def get_interview_graph() -> CompiledStateGraph:
    """Return the compiled, checkpointed interview graph (singleton)."""

    return build_interview_graph().compile(checkpointer=get_checkpointer())
