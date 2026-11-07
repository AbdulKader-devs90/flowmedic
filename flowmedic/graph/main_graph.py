"""Persistent parent: triage -> planner -> close -> approved save."""

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from flowmedic.agents.planner.graph import build_graph as build_planner
from flowmedic.agents.planner.nodes import PlannerNodes
from flowmedic.agents.triage.graph import build_graph as build_triage
from flowmedic.agents.triage.nodes import StopTriage, TriageNodes, note
from flowmedic.graph.state import IncidentRecord, IncidentState


def build_graph(
    *,
    triage_nodes: TriageNodes | None = None,
    planner_nodes: PlannerNodes | None = None,
    checkpointer: Any = None,
) -> Any:
    """Caller owns the SQLite saver lifetime (also allows offline memory savers)."""
    triage = build_triage(nodes=triage_nodes, checkpointer=True)
    planner_nodes = planner_nodes or PlannerNodes()
    graph = StateGraph(IncidentState)
    graph.add_node("triage", triage)
    graph.add_node("planner", build_planner(nodes=planner_nodes))

    async def close(state: IncidentState, config: RunnableConfig) -> IncidentState:
        get_stream_writer()(
            {"node": "close", "summary": "Prepare engineer-reviewed incident record"}
        )
        try:
            return await planner_nodes.close(state, config)
        except StopTriage as exc:
            note(state, str(exc))
            # Preserve a reviewable record even when the incident model budget is spent.
            c = state["context"]
            state["incident_record"] = IncidentRecord(
                symptoms=state["problem"],
                signatures=state.get("signatures", []),
                root_causes=[r.id for r in state["result"].root_causes],
                steps_worked=[],
                platform=c.platform or "unknown",
                category=state["result"].category,
                version=c.version,
                os=c.os,
                environment=c.environment or "unknown",
                components=[],
            )
            state["outcome"] = "escalate"
            state["vendor_case"] = (
                f"Problem: {state['problem']}\nContext: {c.model_dump_json()}\n"
                f"Evidence and steps tried: {state.get('history', [])}"
            )
            return state

    graph.add_node("close", close)

    async def approve_save(state: IncidentState) -> IncidentState:
        get_stream_writer()(
            {"node": "approve_save", "summary": "Request save approval"}
        )
        return await planner_nodes.approve_save(state)

    graph.add_node("approve_save", approve_save)
    graph.add_edge(START, "triage")
    graph.add_edge("triage", "planner")
    graph.add_conditional_edges(
        "planner",
        lambda s: (
            []
            if s.get("decision")
            and s["decision"].decision == "retriage"
            and not s.get("outcome")
            else ["close"]
        ),
    )
    graph.add_edge("close", "approve_save")
    graph.add_edge("approve_save", END)
    return graph.compile(checkpointer=checkpointer)
