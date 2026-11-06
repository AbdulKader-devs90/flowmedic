"""Planner subgraph hands new observations back to its parent triage node."""

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from flowmedic.agents.triage.nodes import StopTriage, note
from flowmedic.graph.state import IncidentState

from .nodes import PlannerNodes


def build_graph(*, nodes: PlannerNodes | None = None) -> Any:
    nodes = nodes or PlannerNodes()
    graph = StateGraph(IncidentState)

    def guarded(name: str) -> Any:
        async def run(state: IncidentState, config: RunnableConfig) -> IncidentState:
            get_stream_writer()({"node": name, "summary": name.replace("_", " ")})
            try:
                method = getattr(nodes, name)
                return (
                    await method(state, config)
                    if name in {"build_plan", "interpret"}
                    else await method(state)
                )
            except StopTriage as exc:
                note(state, str(exc))
                state["outcome"] = "escalate"
                return state

        return run

    for name in ("build_plan", "present_step", "interpret"):
        graph.add_node(name, guarded(name))

    def after_interpret(state: IncidentState) -> str:
        if state.get("outcome"):
            return END
        return "handoff" if state["decision"].decision == "retriage" else "present_step"

    def handoff(state: IncidentState) -> Command:
        return Command(goto="triage", graph=Command.PARENT, update=dict(state))

    graph.add_node("handoff", handoff)
    graph.add_edge(START, "build_plan")
    graph.add_conditional_edges(
        "build_plan", lambda s: END if s.get("outcome") else "present_step"
    )
    graph.add_edge("present_step", "interpret")
    graph.add_conditional_edges("interpret", after_interpret)
    return graph.compile()
