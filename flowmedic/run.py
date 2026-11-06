"""Run a complete, human-executed incident session with durable checkpoints."""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from typing import Any

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from flowmedic.agents.triage.run import initial_state, render
from flowmedic.config import REPO_ROOT, get_settings
from flowmedic.graph import state as contracts
from flowmedic.graph.main_graph import build_graph
from flowmedic.graph.state import TriageContext
from flowmedic.sim.engineer import EngineerSimulator
from flowmedic.tools.environment_memory import local_path
from flowmedic.tools.redact import redact
from flowmedic.tracing import case_trace, run_config, tool_context


def read_engineer_output() -> str:
    """Preserve multiline diagnostic dumps; a single dot ends the paste."""
    print("Paste output; finish with '.' on its own line:")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == ".":
            break
        lines.append(line)
    return "\n".join(lines)


async def run(
    case_id: str,
    answers: dict[str, str],
    *,
    approve_logs: bool = False,
    auto: bool = False,
    approve_save: bool = False,
    graph: Any = None,
    config: Any = None,
) -> dict[str, Any]:
    """Run/resume a single incident; this driver never executes a plan command."""
    config = config or run_config(case_id, "TRIAGE_V2+PLANNER_V1", "incident")
    config["metadata"] = {**config.get("metadata", {}), "model": "per-role"}
    config.setdefault(
        "configurable",
        {"thread_id": f"{case_id}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%f')}"},
    )
    config["recursion_limit"] = 200
    state = initial_state(case_id)
    for slot, value in answers.items():
        if slot not in TriageContext.model_fields:
            raise ValueError(f"Unknown context slot: {slot}")
        state["context_answers"][slot] = redact(value).text
    simulator = (
        EngineerSimulator(REPO_ROOT / "data/scenarios" / case_id / "step_outputs.yaml")
        if auto
        else None
    )

    async def drive(active_graph: Any) -> dict[str, Any]:
        with case_trace(config), tool_context(case_id):
            output = await active_graph.ainvoke(state, config=config)
            shown_history = 0
            shown_triage = None
            while True:
                snapshot = await active_graph.aget_state(config, subgraphs=True)

                def merged_values(snapshot: Any) -> dict[str, Any]:
                    values = dict(snapshot.values)
                    for task in snapshot.tasks:
                        if hasattr(task.state, "values"):
                            values.update(merged_values(task.state))
                    return values

                current = merged_values(snapshot)
                result = current.get("result")
                if result and result.model_dump_json() != shown_triage:
                    if shown_triage:
                        print(f"Re-triage {current.get('retriage_rounds', 0)}")
                    print(render(result))
                    shown_triage = result.model_dump_json()
                history = current.get("history", [])
                for entry in history[shown_history:]:
                    print(f"Engineer output: {entry['reply']['output'].strip()}")
                    print(
                        f"Decision: {entry['decision']['decision']} — "
                        f"{entry['decision']['reason']}"
                    )
                shown_history = len(history)
                if not output.get("__interrupt__"):
                    print(f"Outcome: {output.get('outcome', 'escalate')}")
                    for message in output.get("notes", []):
                        if not result or message not in result.notes:
                            print(f"Note: {message}")
                    print(output["incident_record"].model_dump_json(indent=2))
                    if output.get("vendor_case"):
                        print(output["vendor_case"])
                    return output
                question = output["__interrupt__"][0].value
                kind = question.get("type", question.get("kind"))
                response: dict[str, Any] = {}
                if kind == "step":
                    print(
                        f"Step {question['n']} [{question['kind']}] "
                        f"{question['where']} [{question['source']}: "
                        f"{question.get('source_ref') or 'model'}]: "
                        f"{question['command_or_action']}"
                    )
                    print(
                        f"Expected: {question['expected_output']} | "
                        f"Decision rule: {question['decision_rule']}"
                    )
                    if question.get("risk"):
                        print(
                            f"Risk: {question['risk']}\n"
                            f"Rollback: {question['rollback']}"
                        )
                    if simulator:
                        response = simulator.answer(question)
                    elif sys.stdin.isatty():
                        response = {
                            "status": input("Status [done/skipped/failed]: ").strip(),
                            "output": read_engineer_output(),
                        }
                        if question["kind"] != "read":
                            response["confirmed"] = (
                                input(
                                    "Confirm engineer executed change [y/N]: "
                                ).lower()
                                == "y"
                            )
                    else:
                        response = {
                            "status": "skipped",
                            "output": "No engineer response.",
                        }
                elif kind == "approve_save":
                    response = {"approved": approve_save}
                    if not approve_save and not auto and sys.stdin.isatty():
                        response["approved"] = (
                            input("Approve saving this incident [y/N]: ").lower() == "y"
                        )
                elif kind == "log_access":
                    response = {
                        "approved": auto or approve_logs,
                        "start_time": question.get("start_time"),
                        "end_time": question.get("end_time"),
                    }
                    if not response["approved"] and sys.stdin.isatty():
                        response["approved"] = (
                            input(f"Approve logs {question['folder']} [y/N]: ").lower()
                            == "y"
                        )
                else:
                    for slot in question.get("slots", []):
                        if slot in answers:
                            response[slot] = answers[slot]
                        elif not auto and sys.stdin.isatty():
                            response[slot] = input(f"{slot}: ")
                output = await active_graph.ainvoke(
                    Command(resume=response or {"skip": True}), config=config
                )

    if graph is not None:
        return await drive(graph)
    runs = local_path(get_settings().runs_dir)
    runs.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(
        str(local_path(runs / "checkpoints.sqlite"))
    ) as saver:
        await saver.conn.execute(
            f"PRAGMA busy_timeout={get_settings().sqlite_busy_timeout_ms}"
        )
        saver.serde = JsonPlusSerializer(
            allowed_msgpack_modules=[
                ("flowmedic.graph.state", name)
                for name in vars(contracts)
                if not name.startswith("_")
            ]
        )
        return await drive(build_graph(checkpointer=saver))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id")
    parser.add_argument("--answer", action="append", default=[])
    parser.add_argument("--approve-logs", action="store_true")
    parser.add_argument("--auto", action="store_true")
    parser.add_argument("--approve-save", action="store_true")
    parser.add_argument("--environment")
    args = parser.parse_args()
    answers = {}
    for pair in args.answer:
        if "=" not in pair:
            parser.error("--answer must be k=v")
        key, value = pair.split("=", 1)
        answers[key] = value
    if args.environment:
        answers["environment"] = args.environment
    output = asyncio.run(
        run(
            args.case_id,
            answers,
            approve_logs=args.approve_logs,
            auto=args.auto,
            approve_save=args.approve_save,
        )
    )
    folder = local_path(get_settings().runs_dir)
    folder.mkdir(parents=True, exist_ok=True)
    target = local_path(folder / f"{args.case_id}-full.json")

    def encode(value: Any) -> Any:
        return (
            value.model_dump(mode="json")
            if hasattr(value, "model_dump")
            else str(value)
        )

    target.write_text(json.dumps(output, default=encode, indent=2), encoding="utf-8")
    print(f"Saved runs/{args.case_id}-full.json")


if __name__ == "__main__":
    main()
