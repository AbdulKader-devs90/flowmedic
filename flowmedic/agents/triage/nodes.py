"""Triage nodes with bounded model/tool use and explicit approval interrupts."""

import asyncio
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt
from pydantic import BaseModel, ValidationError

from flowmedic.config import REPO_ROOT, ConfigurationError, get_settings
from flowmedic.graph.state import (
    Category,
    Classification,
    Evidence,
    PlanStep,
    Route,
    Severity,
    Source,
    StepKind,
    TriageContext,
    TriageResult,
    TriageState,
)
from flowmedic.knowledge.loaders import (
    load_categories,
    load_documents,
    load_profile,
    load_root_causes,
    load_topology,
)
from flowmedic.llm import get_llm
from flowmedic.tools import knowledge_repo, topology
from flowmedic.tools.environment_memory import EnvironmentMemory
from flowmedic.tools.log_client import LogClient
from flowmedic.tools.parsers import jstack, ss, vmstat
from flowmedic.tools.parsers.signatures import extract_signatures
from flowmedic.tools.redact import redact
from flowmedic.tools.vendor_docs import search_vendor_docs
from flowmedic.tracing import tool_context

from .prompts import TRIAGE_CLASSIFY_V2, TRIAGE_INTAKE_V1, TRIAGE_REPAIR_V1


class StopTriage(Exception):
    """Controlled hand-back when budget or structured output is exhausted."""


def note(state: TriageState, message: str) -> None:
    """Record a masked, non-instruction gap without raw exception payloads."""
    state["notes"] = [*state.get("notes", []), redact(message).text]


class TriageNodes:
    """Dependencies are injectable so offline tests exercise the real graph."""

    def __init__(
        self,
        *,
        model_factory: Callable[..., Any] = get_llm,
        search: Callable[..., Any] = knowledge_repo.search,
        vendor: Callable[..., Any] = search_vendor_docs,
        log_factory: Callable[..., Any] = LogClient,
        memory: EnvironmentMemory | None = None,
    ) -> None:
        self.model_factory = model_factory
        self.search = search
        self.vendor = vendor
        self.log_factory = log_factory
        self.memory = memory or EnvironmentMemory()

    def model_call(
        self,
        state: TriageState,
        config: RunnableConfig,
        role: str,
        schema: type[BaseModel],
        prompt: str,
        payload: str,
    ) -> Any:
        """Every attempt is counted; one repair, no unstructured response parsing."""
        error = ""
        for _ in range(2):
            if state.get("model_calls", 0) >= get_settings().max_llm_calls:
                raise StopTriage(
                    "MAX_LLM_CALLS reached; ask the engineer to continue in a new turn."
                )
            state["model_calls"] = state.get("model_calls", 0) + 1
            try:
                call_config = dict(config)
                call_config["metadata"] = {
                    **config.get("metadata", {}),
                    "model": get_settings().model_name(role),
                }
                response = (
                    self.model_factory(role)
                    .with_structured_output(schema)
                    .invoke(
                        [("system", prompt + error), ("human", payload)],
                        config=call_config,
                    )
                )
                return schema.model_validate(response)
            except ConfigurationError as exc:
                raise StopTriage(str(exc)) from exc
            except Exception as exc:
                # Exception messages may contain provider output or secrets. Give the
                # repair schema constraints, never an untrusted model response.
                detail = type(exc).__name__
                if isinstance(exc, ValidationError):
                    detail += json.dumps(
                        exc.errors(
                            include_input=False,
                            include_context=False,
                            include_url=False,
                        )
                    )
                error = "\n" + TRIAGE_REPAIR_V1 + detail
                note(
                    state,
                    f"Structured repair for {schema.__name__}: {type(exc).__name__}.",
                )
        raise StopTriage(
            "Structured output failed validation twice; engineer review required."
        )

    async def tool(
        self,
        state: TriageState,
        function: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Retry errors once, retaining a gap if both attempts fail."""
        for attempt in range(2):
            try:
                with tool_context(state["case_id"]):
                    value = await asyncio.to_thread(function, *args, **kwargs)
                    return await value if hasattr(value, "__await__") else value
            except StopTriage:
                raise
            except Exception as exc:
                if attempt:
                    name = getattr(function, "__name__", type(function).__name__)
                    note(
                        state,
                        f"Missing evidence: {name} failed ({type(exc).__name__}).",
                    )
                else:
                    await asyncio.sleep(get_settings().retry_backoff)
        return None

    async def intake(self, state: TriageState, config: RunnableConfig) -> TriageState:
        safe = redact(state["problem"])
        state["problem"] = safe.text
        state["flags"] = list(state.get("flags", [])) + safe.suspicious_lines
        state["context"] = await asyncio.to_thread(
            self.model_call,
            state,
            config,
            "fast",
            TriageContext,
            TRIAGE_INTAKE_V1,
            f"<untrusted_report>\n{safe.text}\n</untrusted_report>",
        )
        state["context"] = TriageContext.model_validate(
            {
                **state["context"].model_dump(),
                **state.get("context_answers", {}),
            }
        )
        state["confirmed_context"] = state["context"].model_dump(exclude_none=True)
        await self.load_context(state)
        return state

    async def load_context(self, state: TriageState) -> None:
        context = state["context"]
        state["profile"] = {}
        state["topology"] = {}
        if context.platform:
            state["profile"] = (
                await self.tool(state, load_profile, context.platform) or {}
            )
        if not context.environment and context.platform:
            remembered_environment = await self.tool(
                state, self.memory.latest_environment, context.platform
            )
            context = context.model_copy(
                update={
                    "environment": remembered_environment
                    or (
                        state["profile"].get("default_environment", "kong-sample")
                        if context.platform == "kong"
                        else get_settings().default_environment
                    )
                }
            )
            state["context"] = context
        if context.environment:
            remembered = (
                await self.tool(state, self.memory.read, context.environment) or {}
            )
            context = context.model_copy(
                update={
                    slot: remembered[slot]
                    for slot in ("platform", "version", "os")
                    if not getattr(context, slot) and remembered.get(slot)
                }
            )
            state["context"] = context
            topo = await self.tool(state, load_topology, context.environment)
            if topo:
                state["topology"] = topo
        if not state["profile"] and state["context"].platform:
            state["profile"] = (
                await self.tool(state, load_profile, state["context"].platform) or {}
            )

    async def clarify(self, state: TriageState) -> TriageState:
        context = state["context"]
        profile = state.get("profile", {})
        missing = ["platform"] if not profile else context.missing_slots(profile)
        if not missing:
            return state
        rounds = state.get("clarification_rounds", 0)
        if rounds >= 2:
            note(state, "Context gaps after two rounds: " + ", ".join(missing))
            return state
        allowed = {
            "platform": [p.stem for p in (REPO_ROOT / "platforms").glob("*.yaml")],
            "version": profile.get("versions", []),
            "os": profile.get("os", []),
            "component": [c["type"] for c in profile.get("components", [])],
            "deployment_mode": profile.get(
                "deployment_modes", ["db", "db-less", "hybrid"]
            ),
        }
        answer = interrupt(
            {
                "kind": "context",
                "slots": missing,
                "allowed_values": {s: allowed.get(s, []) for s in missing},
                "why": "These details select compatible diagnostics and documentation.",
            }
        )
        values = answer if isinstance(answer, dict) else {}
        updates = {}
        for slot in missing:
            value = values.get(slot)
            if not isinstance(value, str) or not value.strip():
                continue
            value = redact(value.strip()).text
            choices = allowed.get(slot, [])
            if choices and value not in choices:
                note(state, f"Unsupported value for {slot}; choose a profile value.")
                continue
            updates[slot] = value
        state["context"] = context.model_copy(update=updates)
        state["context_answers"] = {**state.get("context_answers", {}), **updates}
        state["confirmed_context"] = {**state.get("confirmed_context", {}), **updates}
        state["clarification_rounds"] = rounds + 1
        await self.load_context(state)
        if rounds + 1 >= 2:
            gaps = state["context"].missing_slots(state.get("profile", {}))
            if not state.get("profile"):
                gaps = ["platform"]
            if gaps:
                note(state, "Context gaps after two rounds: " + ", ".join(gaps))
        return state

    def after_clarify(self, state: TriageState) -> str:
        missing = not state.get("profile") or state["context"].missing_slots(
            state["profile"]
        )
        return (
            "clarify"
            if missing and state.get("clarification_rounds", 0) < 2
            else "classify"
        )

    async def request_log_access(self, state: TriageState) -> TriageState:
        root = state.get("log_root")
        if not root:
            return state
        if not state.get("approved"):
            answer = interrupt(
                {
                    "kind": "log_access",
                    "folder": root,
                    "start_time": state.get("start_time"),
                    "end_time": state.get("end_time"),
                    "why": (
                        "Approve this folder and time window "
                        "(null means the full export)."
                    ),
                }
            )
            if not isinstance(answer, dict) or answer.get("approved") is not True:
                note(
                    state, "Log access declined; diagnosis is based on the report only."
                )
                return state
            # Approval cannot broaden the folder selected by the caller.
            state["approved"] = True
            state["confirmed_context"] = {
                **state.get("confirmed_context", {}),
                "log_roots": [root],
            }
            state["start_time"] = answer.get("start_time", state.get("start_time"))
            state["end_time"] = answer.get("end_time", state.get("end_time"))
        return state

    async def evidence(self, state: TriageState, config: RunnableConfig) -> TriageState:
        root = state.get("log_root")
        if not root:
            note(
                state, "No log folder supplied; request an approved diagnostic export."
            )
            return state
        if not state.get("approved"):
            return state
        try:
            with tool_context(state["case_id"]):
                async with self.log_factory([Path(root)]) as client:
                    if client.fallback_reason:
                        note(state, client.fallback_reason)
                    listing = await self.tool(
                        state, client.list_files, root, config=config
                    )
                    evidence: list[Evidence] = []
                    flags: list[str] = list(state.get("flags", []))
                    summaries: dict[str, Any] = {}
                    for file in (listing or {}).get("files", []):
                        result = await self.tool(
                            state,
                            client.grep,
                            file["path"],
                            ".*",
                            start_time=state.get("start_time"),
                            end_time=state.get("end_time"),
                            max_lines=10000,
                            config=config,
                        )
                        if result is None:
                            continue
                        name = file["name"]
                        for flag in result["flagged"]:
                            flags.append(
                                f"{name}:{flag.get('line_no', '?')}: {flag['text']}"
                            )
                        items = [
                            Evidence(source_file=name, **line)
                            for line in result["lines"]
                        ]
                        evidence.extend(items)
                        text = "\n".join(e.text for e in items)
                        if "jstack" in name or "thread" in name:
                            summaries[name] = jstack.summarize(text).model_dump()
                        elif any(t in name for t in ("vmstat", "free", "host")):
                            summaries[name] = vmstat.summarize(text).model_dump()
                        elif "ss" in Path(name).stem:
                            summaries[name] = ss.summarize(text)
                        if result.get("truncated"):
                            note(
                                state,
                                f"{name}: truncated; narrow the approved window.",
                            )
                    state["evidence"] = evidence
                    state["flags"] = list(dict.fromkeys(flags))
                    state["diagnostic_summaries"] = summaries
                    text = "\n".join(e.text for e in evidence)
                    if text and not state["context"].platform:
                        baseline = {s.signature for s in extract_signatures(text)}
                        candidates = []
                        for path in (REPO_ROOT / "platforms").glob("*.yaml"):
                            profile = await self.tool(state, load_profile, path.stem)
                            if (
                                profile
                                and {
                                    s.signature
                                    for s in extract_signatures(
                                        text,
                                        profile,
                                    )
                                }
                                - baseline
                            ):
                                candidates.append(profile)
                        if len(candidates) == 1:
                            profile = candidates[0]
                            components = [
                                c["type"]
                                for c in profile.get("components", [])
                                if {
                                    s.signature
                                    for s in extract_signatures(
                                        text,
                                        {"components": [c]},
                                    )
                                }
                                - baseline
                            ]
                            updates = {"platform": profile["id"]}
                            if not state["context"].component and len(components) == 1:
                                updates["component"] = components[0]
                            state["context"] = state["context"].model_copy(
                                update=updates
                            )
                            state["profile"] = profile
                            note(
                                state,
                                "Platform identified from approved log signatures: "
                                + profile["id"],
                            )
                    state["signatures"] = [
                        s.signature
                        for s in extract_signatures(
                            text,
                            state.get("profile"),
                        )
                    ]
        except StopTriage:
            raise
        except Exception as exc:
            note(
                state,
                f"Log reader unavailable ({type(exc).__name__}); request a new export.",
            )
        await self.load_context(state)
        if not state["context"].component and state.get("profile"):
            text = "\n".join(e.text for e in state.get("evidence", []))
            baseline = {s.signature for s in extract_signatures(text)}
            components = [
                c["type"]
                for c in state["profile"].get("components", [])
                if {s.signature for s in extract_signatures(text, {"components": [c]})}
                - baseline
            ]
            if len(components) == 1:
                state["context"] = state["context"].model_copy(
                    update={"component": components[0]}
                )
        return state

    async def classify(self, state: TriageState, config: RunnableConfig) -> TriageState:
        items = state.get("evidence", []) + state.get("engineer_evidence", [])
        references = {f"{e.source_file}:{e.line_no}" for e in items}

        component_ids = {
            c["id"] for c in state.get("topology", {}).get("components", [])
        }
        default_component = next(
            (
                c["id"]
                for c in state.get("topology", {}).get("components", [])
                if state["context"].component
                in (c["id"], c["type"], *c.get("nodes", []))
            ),
            None,
        )

        class GroundedClassification(Classification):
            """Evidence references are checked after structured decoding."""

            affected_component: str | None = default_component

            @classmethod
            def model_validate(cls, obj: Any, **kwargs: Any) -> Any:
                result = super().model_validate(obj, **kwargs)
                if any(
                    ref not in references
                    for cause in result.root_causes
                    for ref in cause.evidence_refs
                ):
                    raise ValueError("Unknown evidence reference")
                if component_ids and result.affected_component not in component_ids:
                    raise ValueError("Choose affected_component from the topology ids")
                return result

        diagnosis = await asyncio.to_thread(
            self.model_call,
            state,
            config,
            "strong",
            GroundedClassification,
            TRIAGE_CLASSIFY_V2
            + "\nChoose affected_component from topology ids: "
            + json.dumps(sorted(component_ids))
            + "\nCategory definitions:\n"
            + json.dumps(load_categories())
            + "\nRoot-cause definitions:\n"
            + json.dumps(load_root_causes()),
            json.dumps(
                {
                    "untrusted_report": state["problem"],
                    "untrusted_context": state["context"].model_dump(),
                    "untrusted_evidence": [
                        {"ref": f"{e.source_file}:{e.line_no}", "text": e.text}
                        for e in items
                    ],
                    "untrusted_diagnostics": state.get("diagnostic_summaries", {}),
                }
            ),
        )
        state["classification"] = Classification.model_validate(diagnosis.model_dump())
        context = state["context"]
        component = diagnosis.affected_component
        if component and context.environment:
            state["related_components"] = (
                await self.tool(
                    state,
                    topology.related_checks,
                    context.environment,
                    component,
                )
                or []
            )
        if context.environment:
            await self.tool(
                state,
                self.memory.confirm,
                context.environment,
                state.get("confirmed_context", {}),
            )
        return state

    async def kb_search(self, state: TriageState) -> TriageState:
        context = state["context"]
        matches = (
            await self.tool(
                state,
                self.search,
                state["problem"],
                state.get("signatures", []),
                context.platform or "",
                context.version,
                log_text="\n".join(
                    e.text
                    for e in state.get("evidence", [])
                    + state.get("engineer_evidence", [])
                ),
            )
            or []
        )
        docs = {d.doc_id: d for d in load_documents()}
        category = state["classification"].category
        matches = [
            m.model_copy(update={"category_match": docs[m.doc_id].category == category})
            for m in matches
            if m.doc_id in docs
        ]
        state["matches"] = matches
        state["route"] = knowledge_repo.route_for(matches)
        if (
            category == Category.UNKNOWN
            and len(state.get("evidence", []) + state.get("engineer_evidence", [])) < 2
        ):
            state["route"] = Route.CLARIFY
        return state

    async def ask_evidence(self, state: TriageState) -> TriageState:
        if state.get("evidence_rounds", 0) >= 1:
            note(
                state,
                "Evidence is insufficient; provide timestamped errors and exports.",
            )
            return state
        answer = interrupt(
            {
                "kind": "evidence",
                "slots": ["evidence"],
                "why": "Paste timestamped errors or diagnostics for this component.",
            }
        )
        text = answer.get("evidence", "") if isinstance(answer, dict) else str(answer)
        safe = redact(text)
        state["engineer_evidence"] = [
            Evidence(source_file="engineer", line_no=n, text=line)
            for n, line in enumerate(safe.text.splitlines(), 1)
        ]
        state["flags"] = (
            [
                *state.get("flags", []),
                *safe.suspicious_lines,
                *answer.get("flagged", []),
            ]
            if isinstance(answer, dict)
            else [*state.get("flags", []), *safe.suspicious_lines]
        )
        state["evidence_rounds"] = 1
        return state

    async def resolve(self, state: TriageState, config: RunnableConfig) -> TriageState:
        steps: list[PlanStep] = []
        matches = state.get("matches", [])
        if state["route"] in (Route.KNOWN_FIX, Route.SIMILAR) and matches:
            docs = {d.doc_id: d for d in load_documents()}
            incident = next(
                (
                    docs[m.doc_id]
                    for m in sorted(matches, key=lambda match: -match.score)
                    if m.doc_type == "incident"
                ),
                None,
            )
            if incident and incident.verified:
                for doc in [
                    incident,
                    *(docs[r] for r in incident.runbooks if r in docs),
                ]:
                    if not doc.verified:
                        continue
                    body = doc.body
                    if doc.doc_type == "incident":
                        section = re.search(
                            r"## Resolution steps\n(.*?)(?=\n## |\Z)", body, re.S
                        )
                        body = section[1] if section else ""
                    for kind, action in re.findall(
                        r"(?m)^\d+\. \[(read|change|destructive)\] (.+)$",
                        body,
                    ):
                        if action.casefold() in {
                            s.command_or_action.casefold() for s in steps
                        }:
                            continue
                        steps.append(
                            PlanStep(
                                n=len(steps) + 1,
                                title=action,
                                kind=StepKind(kind),
                                command_or_action=action,
                                where=", ".join(doc.components),
                                expected_output=(
                                    "Confirm the documented symptom clears "
                                    "and service health recovers."
                                ),
                                risk=(
                                    "May interrupt active work; the owner must assess "
                                    "impact before execution."
                                    if kind != "read"
                                    else None
                                ),
                                rollback=(
                                    "Stop if impact is unclear; the owner must record "
                                    "current settings and approve a recovery procedure "
                                    "before execution."
                                    if kind != "read"
                                    else None
                                ),
                                source=Source.VERIFIED,
                                source_ref=doc.doc_id,
                            )
                        )
            elif state["route"] == Route.KNOWN_FIX:
                state["route"] = Route.SIMILAR
                note(
                    state,
                    "No verified incident resolution; confirm with vendor research.",
                )
        state["first_steps"] = steps
        if state["route"] in (Route.NEW_ISSUE, Route.SIMILAR):
            context = state["context"]
            try:
                with tool_context(state["case_id"]):
                    findings = await asyncio.to_thread(
                        self.vendor,
                        context.platform or "",
                        context.version,
                        state.get("signatures", []),
                        state["problem"]
                        + "\nCandidate KB steps to confirm/adjust:\n"
                        + "\n".join(s.command_or_action for s in steps),
                        model_call=lambda *args: self.model_call(state, config, *args),
                    )
            except StopTriage:
                raise
            except Exception as exc:
                findings = None
                note(state, f"Vendor research gap ({type(exc).__name__}).")
            if findings:
                if state["route"] == Route.NEW_ISSUE:
                    steps.extend(findings.steps)
                else:
                    steps = steps[:5] + findings.steps[:1]
                if findings.likely_causes:
                    note(
                        state,
                        "Vendor hypotheses (unconfirmed): "
                        + "; ".join(findings.likely_causes),
                    )
                if findings.notes:
                    note(state, findings.notes)
        if state["route"] == Route.CLARIFY:
            note(
                state,
                "Evidence insufficient; provide timestamped diagnostic exports.",
            )
        state["first_steps"] = [
            s.model_copy(update={"n": i}) for i, s in enumerate(steps[:6], 1)
        ]
        return state

    async def synthesize(self, state: TriageState) -> TriageState:
        classification = state.get("classification") or Classification(
            category=Category.UNKNOWN,
            severity=Severity.P3,
            confidence=0,
        )
        rc = max(
            (c.confidence for c in classification.root_causes),
            default=classification.confidence,
        )
        kb = max((m.score for m in state.get("matches", [])), default=0)
        vendor_evidence = float(
            any(s.source == Source.CITED for s in state.get("first_steps", []))
        )
        confidence = overall_confidence(
            state.get("route", Route.CLARIFY),
            rc,
            kb,
            vendor_evidence,
            evidence_gap=any("Missing evidence:" in n for n in state.get("notes", [])),
        )
        state["result"] = TriageResult(
            **classification.model_dump(exclude={"confidence"}),
            confidence=confidence,
            route=state.get("route", Route.CLARIFY),
            kb_matches=state.get("matches", []),
            related_components=state.get("related_components", []),
            first_steps=state.get("first_steps", []),
            notes="\n".join(state.get("notes", [])),
            flags=state.get("flags", []),
        )
        return state


def overall_confidence(
    route: Route,
    rc: float,
    kb: float,
    vendor_evidence: float,
    *,
    evidence_gap: bool = False,
) -> float:
    """Single confidence formula: cause support + retrieval + cited vendor evidence.

    known_fix=.5*rc+.5*kb; similar=.4*rc+.3*kb+.3*vendor;
    new_issue=.7*rc; clarify=min(rc,.4). Multiply by .7 for missing-tool evidence.
    Inputs and output are in [0,1]; informational notes do not lower confidence.
    """
    base = {
        Route.KNOWN_FIX: 0.5 * rc + 0.5 * kb,
        Route.SIMILAR: 0.4 * rc + 0.3 * kb + 0.3 * vendor_evidence,
        Route.NEW_ISSUE: 0.7 * rc,
        Route.CLARIFY: min(rc, 0.4),
    }[route]
    return base * (0.7 if evidence_gap else 1)
