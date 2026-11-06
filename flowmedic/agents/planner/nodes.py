"""Human execution loop; no remote command or server write capability."""

import asyncio
import json
import re
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt
from pydantic import Field, model_validator

from flowmedic.agents.triage.nodes import TriageNodes, note
from flowmedic.graph.state import (
    ActivePlan,
    Evidence,
    IncidentRecord,
    IncidentState,
    Interpretation,
    PlanStep,
    ResolutionPlan,
    StepKind,
    StepReply,
    validate_specific_recovery,
)
from flowmedic.tools.parsers import jstack, oracle, ss, vmstat
from flowmedic.tools.parsers.signatures import extract_signatures
from flowmedic.tools.redact import redact
from flowmedic.tools.save_incident import IncidentIndexError, save_incident

from .prompts import PLANNER_BUILD_V1, PLANNER_INTERPRET_V1


class PlannerNodes(TriageNodes):
    """Reuse structured calls, repairs, budgets and traced tool handling."""

    def __init__(self, *, save: Any = save_incident, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.save = save

    def plan_schema(self, state: IncidentState) -> type[ResolutionPlan]:
        component_id = Literal[
            tuple(sorted(c["id"] for c in state["topology"]["components"]))
        ]

        class GroundedStep(PlanStep):
            where: component_id

        class GroundedPlan(ResolutionPlan):
            steps: list[GroundedStep] = Field(min_length=5, max_length=10)

            @model_validator(mode="after")
            def grounded(self) -> "GroundedPlan":
                validate_grounding(state, self.steps)
                return self

        return GroundedPlan

    async def build_plan(
        self, state: IncidentState, config: RunnableConfig
    ) -> IncidentState:
        if not state.get("topology") or not state["result"].first_steps:
            state["outcome"] = "escalate"
            return state
        schema = self.plan_schema(state)
        response = await asyncio.to_thread(
            self.model_call,
            state,
            config,
            "strong",
            schema,
            PLANNER_BUILD_V1,
            json.dumps(
                {
                    "triage": state["result"].model_dump(
                        mode="json", exclude={"flags"}
                    ),
                    "context": state["context"].model_dump(),
                    "topology": state.get("topology", {}),
                    "history": state.get("history", []),
                }
            ),
        )
        plan = ResolutionPlan.model_validate(response.model_dump())
        if state["result"].category == "OUTAGE" or state["result"].route == "new_issue":
            # Triage's related_checks is dependencies (hard first), then callers.
            order = state["result"].related_components
            reads = sorted(
                (
                    s
                    for s in plan.steps
                    if s.kind == StepKind.READ and "verif" not in s.title.lower()
                ),
                key=lambda s: order.index(s.where) if s.where in order else len(order),
            )
            rest = [s for s in plan.steps if s not in reads]
            old_to_new = {s.n: i for i, s in enumerate([*reads, *rest], 1)}
            steps = []
            for i, step in enumerate([*reads, *rest], 1):
                rule = re.sub(
                    r"(?i)step (\d+)",
                    lambda m: f"step {old_to_new.get(int(m[1]), int(m[1]))}",
                    step.decision_rule,
                )
                steps.append(step.model_copy(update={"n": i, "decision_rule": rule}))
            plan = ResolutionPlan(steps=steps)
        state["plan"] = plan
        state["step_index"] = 0
        return state

    async def present_step(self, state: IncidentState) -> IncidentState:
        step = state["plan"].steps[state.get("step_index", 0)]
        reply = StepReply.model_validate(
            interrupt({"type": "step", **step.model_dump(mode="json")})
        )
        safe = redact(reply.output)
        state["flags"] = [*state.get("flags", []), *safe.suspicious_lines]
        reply.output = safe.text
        if (
            step.kind != StepKind.READ
            and reply.status == "done"
            and not reply.confirmed
        ):
            # Replay-safe: no interpretation of an unconfirmed change as execution.
            reply = StepReply(
                status="skipped", output="Change not confirmed; no execution accepted."
            )
        state["reply"] = reply
        return state

    async def interpret(
        self, state: IncidentState, config: RunnableConfig
    ) -> IncidentState:
        reply = state["reply"]
        text = redact(reply.output).text
        reply.output = text
        parsers = {
            "jstack": jstack.summarize(text).model_dump(),
            "vmstat": vmstat.summarize(text).model_dump(),
            "ss": ss.summarize(text),
            "oracle": oracle.summarize(text),
            "signatures": [
                s.signature for s in extract_signatures(text, state.get("profile"))
            ],
        }
        step = state["plan"].steps[state["step_index"]]

        class GroundedInterpretation(Interpretation):
            @model_validator(mode="after")
            def grounded(self) -> "GroundedInterpretation":
                validate_grounding(state, self.steps)
                return self

        decision = await asyncio.to_thread(
            self.model_call,
            state,
            config,
            "fast",
            GroundedInterpretation,
            PLANNER_INTERPRET_V1,
            json.dumps(
                {
                    "triage": state["result"].model_dump(
                        mode="json", exclude={"flags"}
                    ),
                    "step": step.model_dump(mode="json"),
                    "reply": reply.model_dump(),
                    "parsers": parsers,
                    "history": state.get("history", []),
                    "remaining_plan": [
                        s.model_dump(mode="json")
                        for s in state["plan"].steps[state["step_index"] + 1 :]
                    ],
                    "topology": state.get("topology", {}),
                    "retriage_rounds": state.get("retriage_rounds", 0),
                }
            ),
        )
        decision = Interpretation.model_validate(decision.model_dump())
        known = {c.id.value for c in state["result"].root_causes}
        if (
            reply.status == "done"
            and parsers["oracle"]["blocking_lock"]
            and "db_blocking_lock" not in known
        ):
            decision = Interpretation(
                decision="retriage",
                reason="Blocking lock evidence introduces db_blocking_lock.",
            )
        if decision.decision == "resolved" and any(
            pending.kind == StepKind.READ and "verif" in pending.title.casefold()
            for pending in state["plan"].steps[state["step_index"] + 1 :]
        ):
            decision = Interpretation(
                decision="next",
                reason="Recovery observed; complete the remaining verification.",
            )
        if reply.status != "done" and decision.decision == "resolved":
            decision = Interpretation(
                decision="next", reason="Skipped/failed output cannot confirm recovery."
            )
        if decision.decision == "retriage":
            if state.get("retriage_rounds", 0) >= 2:
                decision = Interpretation(
                    decision="escalate",
                    reason="Two re-triage rounds exhausted; vendor review needed.",
                )
            else:
                state["retriage_rounds"] = state.get("retriage_rounds", 0) + 1
                state["engineer_evidence"] = [
                    *state.get("engineer_evidence", []),
                    *[
                        Evidence(
                            source_file=f"step-{len(state.get('history', [])) + 1}",
                            line_no=n,
                            text=line,
                        )
                        for n, line in enumerate(text.splitlines(), 1)
                    ],
                ]
        if decision.decision == "insert_steps" and decision.steps:

            def action_key(action: str) -> str:
                return " ".join(re.findall(r"\w+", action.casefold()))

            seen = {action_key(s.command_or_action) for s in state["plan"].steps}
            seen.update(
                action_key(h["step"]["command_or_action"])
                for h in state.get("history", [])
            )
            fresh = []
            for candidate in decision.steps:
                key = action_key(candidate.command_or_action)
                if key not in seen:
                    fresh.append(candidate)
                    seen.add(key)
            if not fresh:
                decision = Interpretation(
                    decision="next",
                    reason="Checks already appear in the plan/history; continue.",
                )
            else:
                decision.steps = fresh
        if decision.decision == "insert_steps":
            if not decision.steps:
                decision = Interpretation(
                    decision="escalate", reason="No grounded inserted steps supplied."
                )
            else:
                steps = state["plan"].steps
                index = state["step_index"] + 1
                combined = steps[:index] + decision.steps + steps[index:]
                # A repaired model output cannot grow the plan without bound.
                payload = {
                    "steps": [
                        s.model_copy(update={"n": n}).model_dump()
                        for n, s in enumerate(combined, 1)
                    ]
                }
                try:
                    validate_grounding(state, decision.steps)
                    state["plan"] = ActivePlan.model_validate(payload)
                except ValueError:
                    decision = Interpretation(
                        decision="escalate",
                        reason="Inserted steps failed grounding or safety checks.",
                    )
        state["planner_turns"] = state.get("planner_turns", 0) + 1
        state["history"] = [
            *state.get("history", []),
            {
                "step": step.model_dump(mode="json"),
                "reply": reply.model_dump(),
                "decision": decision.model_dump(mode="json"),
            },
        ]
        state["decision"] = decision
        if state["planner_turns"] >= 30 and decision.decision not in {
            "resolved",
            "escalate",
        }:
            state["decision"] = Interpretation(
                decision="escalate", reason="Planner iteration limit reached."
            )
        state["step_index"] += 1
        if state["decision"].decision in {"resolved", "escalate"}:
            state["outcome"] = state["decision"].decision
        elif (
            state["step_index"] >= len(state["plan"].steps)
            and state["decision"].decision != "retriage"
        ):
            state["outcome"] = "escalate"
        return state

    async def close(
        self, state: IncidentState, config: RunnableConfig
    ) -> IncidentState:
        context = state["context"]
        # These are literal masked observations, never model-invented executions.
        record = IncidentRecord(
            symptoms=(
                f"{state['problem']}\n"
                f"Session outcome: {state.get('outcome', 'escalate')}"
            ),
            platform=context.platform or "unknown",
            version=context.version,
            os=context.os,
            environment=context.environment or "unknown",
            category=state["result"].category,
            root_causes=[c.id for c in state["result"].root_causes],
            signatures=state.get("signatures", []),
            components=list(dict.fromkeys(s.where for s in state["plan"].steps))
            if state.get("plan")
            else [],
            steps_worked=[
                {
                    "action": entry["step"]["command_or_action"],
                    "kind": entry["step"]["kind"],
                    "output": redact(entry["reply"]["output"]).text[:600],
                    "risk": entry["step"].get("risk") or "",
                    "rollback": entry["step"].get("rollback") or "",
                }
                for entry in state.get("history", [])
                if entry["reply"]["status"] == "done"
            ],
        )
        state["incident_record"] = record
        if state.get("outcome") != "resolved":
            tried = "\n".join(
                f"{n}. [{entry['reply']['status']}] "
                f"{entry['step']['command_or_action']}: "
                + " ".join(redact(entry["reply"]["output"]).text.split())[:240]
                for n, entry in enumerate(state.get("history", []), 1)
            )
            state["vendor_case"] = (
                f"Problem: {record.symptoms}\n"
                f"Platform/version: {record.platform} {record.version}; "
                f"OS: {record.os}\n"
                f"Environment: {record.environment}\n"
                f"Evidence: {', '.join(record.signatures)}\n"
                f"Steps tried:\n{tried}"
            )
        return state

    async def approve_save(self, state: IncidentState) -> IncidentState:
        response = interrupt(
            {
                "type": "approve_save",
                "record": state["incident_record"].model_dump(mode="json"),
                "outcome": state.get("outcome", "escalate"),
            }
        )
        if isinstance(response, dict) and response.get("approved") is True:
            try:
                saved = await asyncio.to_thread(
                    self.save, state["incident_record"], approved=True
                )
                if saved:
                    state["saved_path"] = str(saved)
            except IncidentIndexError as exc:
                state["saved_path"] = str(exc.path)
                note(state, str(exc))
            except Exception as exc:
                note(
                    state,
                    f"Approved save failed ({type(exc).__name__}); review destination.",
                )
        return state


def validate_grounding(state: IncidentState, steps: list[Any]) -> None:
    """Apply identical topology, provenance and recovery checks to inserted steps."""
    ids = {c["id"] for c in state.get("topology", {}).get("components", [])}
    provenance = {(s.source, s.source_ref) for s in state["result"].first_steps}
    for step in steps:
        if step.where not in ids:
            raise ValueError("where must be a loaded topology component id")
        if (step.source, step.source_ref) not in provenance:
            raise ValueError("Carry source and source_ref from triage")
        validate_specific_recovery(step)
