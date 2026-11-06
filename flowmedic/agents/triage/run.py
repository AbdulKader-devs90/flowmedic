"""Interactive triage CLI. Only the requested JSON artifact is written locally."""

import argparse
import asyncio
import json
import sys
from typing import Any
from uuid import uuid4

from langgraph.types import Command

from flowmedic.config import REPO_ROOT
from flowmedic.graph.state import TriageContext, TriageResult, TriageState
from flowmedic.knowledge.loaders import load_scenario
from flowmedic.tools.redact import redact
from flowmedic.tracing import case_trace, run_config, tool_context

from .graph import build_graph
from .prompts import PROMPT_VERSION


def initial_state(case_id: str) -> TriageState:
    """Read only the problem; log content is loaded later after an interrupt."""
    scenario = load_scenario(case_id, include_logs=False, include_expected=True)
    folder = REPO_ROOT / "data/scenarios" / scenario.case_id
    logs = folder / "logs"
    if logs.exists() and not logs.resolve().is_relative_to(folder.resolve()):
        raise ValueError("Scenario logs escape the scenario folder")
    safe = redact(scenario.problem)
    environment = scenario.expected.get("environment")
    return TriageState(
        case_id=case_id,
        problem=safe.text,
        log_root=str(folder / "logs"),
        context_answers={"environment": environment} if environment else {},
        model_calls=0,
        notes=[],
        flags=safe.suspicious_lines,
    )


def render(result: TriageResult) -> str:
    """Readable diagnosis with provenance, risks and rollback visible."""
    lines = [
        f"Category: {result.category} | Severity: {result.severity}",
        f"Route: {result.route} | Confidence: {result.confidence:.0%}",
        "Root causes:",
    ]
    lines.extend(
        f"  {r.id} ({r.confidence:.0%}) evidence: "
        f"{', '.join(r.evidence_refs) or 'report only'}"
        for r in result.root_causes
    )
    if result.kb_matches:
        top = result.kb_matches[0]
        lines.append(f"Top KB match: {top.doc_id} — {top.title} ({top.score:.3f})")
    lines.append(
        "Related components: "
        + (", ".join(result.related_components) or "not established")
    )
    lines.append("Suggested first steps (engineer executes):")
    for step in result.first_steps:
        lines.append(
            f"  {step.n}. [{step.kind}] "
            f"[{step.source}: {step.source_ref or 'own knowledge'}] "
            f"{step.command_or_action}"
        )
        if step.risk:
            lines.append(f"     Risk: {step.risk}\n     Rollback: {step.rollback}")
    if result.notes:
        lines.append("Notes: " + result.notes)
    if result.flags:
        lines.append("Flags (quarantined):\n" + "\n".join(result.flags))
    return "\n".join(lines)


async def run(
    case_id: str, answers: dict[str, str], approve_logs: bool, *, graph: Any = None
) -> TriageResult:
    """Resume each interrupt on the same case thread with inherited tracing."""
    graph = graph if graph is not None else build_graph()
    config = run_config(
        case_id=case_id, prompt_version=PROMPT_VERSION, run_name="triage"
    )
    config["configurable"] = {"thread_id": f"{case_id}-{uuid4()}"}
    config["metadata"] = {**config.get("metadata", {}), "model": "per-role"}
    config["recursion_limit"] = 50
    with case_trace(config), tool_context(case_id):
        state = initial_state(case_id)
        state.setdefault("context_answers", {})
        for slot, value in answers.items():
            if slot in TriageContext.model_fields:
                safe = redact(value)
                state["context_answers"][slot] = safe.text
                state["flags"].extend(safe.suspicious_lines)
        output = await graph.ainvoke(state, config=config)
        while output.get("__interrupt__"):
            question = output["__interrupt__"][0].value
            print(json.dumps(question, indent=2))
            response: dict[str, Any] = {}
            if question["kind"] == "log_access":
                response = {
                    "approved": approve_logs,
                    "start_time": question.get("start_time"),
                    "end_time": question.get("end_time"),
                }
                if not approve_logs and sys.stdin.isatty():
                    response["approved"] = (
                        input("Approve log access? [y/N] ").strip().lower() == "y"
                    )
            else:
                for slot in question.get("slots", []):
                    if slot in answers:
                        response[slot] = answers[slot]
                    elif sys.stdin.isatty():
                        response[slot] = input(f"{slot}: ").strip()
            flags = []
            for slot, value in response.items():
                if isinstance(value, str):
                    safe = redact(value)
                    response[slot] = safe.text
                    flags.extend(safe.suspicious_lines)
            if flags:
                response["flagged"] = flags
            output = await graph.ainvoke(
                Command(resume=response or {"skip": True}), config=config
            )
    return output["result"]


def main() -> None:
    """Parse portable scenario-based arguments and save an in-repo result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id")
    parser.add_argument("--answer", action="append", default=[], metavar="SLOT=VALUE")
    parser.add_argument("--approve-logs", action="store_true")
    parser.add_argument("--environment")
    args = parser.parse_args()
    answers = {}
    for pair in args.answer:
        if "=" not in pair:
            parser.error("--answer must use SLOT=VALUE")
        key, value = pair.split("=", 1)
        answers[key] = value
    if args.environment:
        answers["environment"] = args.environment
    result = asyncio.run(run(args.case_id, answers, args.approve_logs))
    print(render(result))
    folder = REPO_ROOT / "runs"
    folder.mkdir(exist_ok=True)
    target = folder / f"{args.case_id}.json"
    if not folder.resolve().is_relative_to(REPO_ROOT) or target.is_symlink():
        raise ValueError("Result destination escapes repository or is a symlink")
    target.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(f"Saved runs/{args.case_id}.json")


if __name__ == "__main__":
    main()
