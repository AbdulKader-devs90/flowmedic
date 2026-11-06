"""Checkpointed triage graph; all server actions remain with the engineer."""

from collections.abc import Callable
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph

from flowmedic.graph.state import Route, TriageState

from .nodes import StopTriage, TriageNodes, note


def build_graph(*, nodes: TriageNodes | None = None, checkpointer: Any = None) -> Any:
    """Build an isolated graph with an in-memory checkpointer by default."""
    nodes = nodes or TriageNodes()
    graph = StateGraph(TriageState)

    def guarded(method: Callable[..., Any]) -> Callable[..., Any]:
        async def run(state: TriageState, config: RunnableConfig) -> TriageState:
            try:
                if method.__name__ in {"intake", "evidence", "classify", "resolve"}:
                    return await method(state, config)
                return await method(state)
            except StopTriage as exc:
                note(state, str(exc))
                state["stopped"] = True
                return state

        return run

    for name in (
        "intake",
        "clarify",
        "evidence",
        "classify",
        "kb_search",
        "ask_evidence",
        "resolve",
        "synthesize",
    ):
        graph.add_node(name, guarded(getattr(nodes, name)))
    graph.add_edge(START, "intake")
    graph.add_conditional_edges(
        "intake", lambda s: "synthesize" if s.get("stopped") else "clarify"
    )
    graph.add_conditional_edges("clarify", nodes.after_clarify)
    graph.add_edge("evidence", "classify")
    graph.add_conditional_edges(
        "classify", lambda s: "synthesize" if s.get("stopped") else "kb_search"
    )
    graph.add_conditional_edges(
        "kb_search",
        lambda s: (
            "ask_evidence"
            if s["route"] == Route.CLARIFY and not s.get("evidence_rounds")
            else "resolve"
        ),
    )
    graph.add_edge("ask_evidence", "evidence")
    graph.add_edge("resolve", "synthesize")
    graph.add_edge("synthesize", END)
    serde = JsonPlusSerializer(
        allowed_msgpack_modules=[
            ("flowmedic.graph.state", name)
            for name in (
                "TriageContext",
                "Evidence",
                "KBMatch",
                "Classification",
                "TriageResult",
                "Category",
                "Severity",
                "RootCauseID",
                "Source",
                "StepKind",
                "Route",
                "PlanStep",
                "RankedRootCause",
            )
        ]
    )
    return graph.compile(
        checkpointer=checkpointer
        if checkpointer is not None
        else InMemorySaver(serde=serde)
    )
