"""HTTP adapter; graph tools remain read-only and execution stays with humans."""

import asyncio
import codecs
import json
import logging
import re
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import START
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sse_starlette.sse import EventSourceResponse

from flowmedic.agents.triage.run import initial_state
from flowmedic.config import get_settings
from flowmedic.graph import state as contracts
from flowmedic.graph.main_graph import build_graph
from flowmedic.graph.state import Evidence, Interpretation, StepReply
from flowmedic.knowledge.loaders import (
    list_scenarios,
    load_documents,
    load_scenario,
    load_topology,
)
from flowmedic.tools.environment_memory import local_path
from flowmedic.tools.redact import redact
from flowmedic.tracing import case_trace, run_config, tool_context

logger = logging.getLogger(__name__)


class CreateIncident(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(default="", max_length=100_000)
    platform: str | None = None
    environment: str | None = None
    scenario_id: str | None = None


class ResumeIncident(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["answer", "approve_logs", "step_result", "approve_save", "retriage"]
    payload: dict[str, Any] | bool


def safe_output(value: Any) -> Any:
    """Mask all response strings; quarantine appears only in a flags array."""

    def clean(item: Any, *, flags: bool = False) -> Any:
        if isinstance(item, str):
            masked = redact(item)
            return (
                ("\n".join(masked.suspicious_lines) or masked.text)
                if flags
                else masked.text
            )
        if isinstance(item, list):
            return [clean(v, flags=flags) for v in item]
        if isinstance(item, dict):
            return {k: clean(v, flags=k == "flags") for k, v in item.items()}
        return item

    return clean(jsonable_encoder(value))


def merged(snapshot: Any) -> dict[str, Any]:
    values = dict(snapshot.values)
    for task in snapshot.tasks:
        if hasattr(task.state, "values"):
            values.update(merged(task.state))
    return values


def pending(snapshot: Any) -> list[Any]:
    found = list(getattr(snapshot, "interrupts", ()))
    for task in snapshot.tasks:
        found.extend(task.interrupts)
        if hasattr(task.state, "values"):
            found.extend(pending(task.state))
    return list({item.id: item for item in found}.values())


def leaf(snapshot: Any) -> Any:
    for task in snapshot.tasks:
        if hasattr(task.state, "values"):
            return leaf(task.state)
    return snapshot


def stage(values: dict[str, Any], snapshot: Any) -> str:
    if values.get("incident_record") or not snapshot.next:
        return "closed"
    return "planner" if values.get("result") else "triage"


def plan_view(values: dict[str, Any]) -> Any:
    plan = jsonable_encoder(values.get("plan"))
    if not plan:
        return None
    history = values.get("history", [])
    for step in plan["steps"]:
        step["status"] = next(
            (
                entry["reply"]["status"]
                for entry in reversed(history)
                if entry["step"]["command_or_action"] == step["command_or_action"]
                and entry["step"]["where"] == step["where"]
            ),
            "pending",
        )
    return plan


def create_app(*, graph: Any = None) -> FastAPI:
    """Inject a compiled fake graph for offline HTTP and streaming tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Multipart parsers spool large uploads before the handler sees them.
        # Keep those temporary files inside the repository too.
        spool = local_path(get_settings().runs_dir / ".multipart")
        spool.mkdir(parents=True, exist_ok=True)
        previous_tempdir = tempfile.tempdir
        tempfile.tempdir = str(spool)
        try:
            async with graph_lifetime(app):
                yield
        finally:
            tempfile.tempdir = previous_tempdir

    @asynccontextmanager
    async def graph_lifetime(app: FastAPI) -> AsyncIterator[None]:
        if graph is not None:
            app.state.graph = graph
            yield
            return
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
            app.state.graph = build_graph(checkpointer=saver)
            yield

    app = FastAPI(title="FlowMedic", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().api_cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Validation errors must not echo rejected diagnostic input or secrets.
        errors = [
            {key: error[key] for key in ("loc", "msg", "type")}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content=safe_output({"detail": errors}))

    locks: dict[str, asyncio.Lock] = {}
    commands: dict[str, Command] = {}

    def config(incident_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"[\w-]+", incident_id):
            raise HTTPException(404, "Unknown incident")
        cfg = run_config(incident_id, "TRIAGE_V2+PLANNER_V1", "incident-api")
        cfg["metadata"]["model"] = "per-role"
        cfg["configurable"] = {"thread_id": incident_id}
        cfg["recursion_limit"] = 200
        return cfg

    async def snapshot(incident_id: str) -> Any:
        result = await app.state.graph.aget_state(config(incident_id), subgraphs=True)
        if not result.values:
            raise HTTPException(404, "Unknown incident")
        return result

    def idle(incident_id: str) -> asyncio.Lock:
        lock = locks.setdefault(incident_id, asyncio.Lock())
        if lock.locked() or incident_id in commands:
            raise HTTPException(409, "Incident is running or has a queued resume")
        return lock

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/scenarios")
    async def scenarios() -> Any:
        result = []
        for case_id in list_scenarios():
            scenario = load_scenario(case_id, include_logs=False)
            result.append(
                {
                    "id": case_id,
                    "title": scenario.problem.splitlines()[0].lstrip("# "),
                    "platform": scenario.expected.get("platform"),
                    "environment": scenario.expected.get("environment"),
                }
            )
        return safe_output(result)

    @app.post("/api/incidents", status_code=201)
    async def create(body: CreateIncident) -> Any:
        incident_id = uuid4().hex
        if body.scenario_id:
            try:
                state = initial_state(body.scenario_id)
            except (ValueError, FileNotFoundError):
                raise HTTPException(404, "Unknown scenario") from None
        else:
            if not body.message.strip():
                raise HTTPException(422, "message or scenario_id is required")
            safe = redact(body.message)
            state = {
                "problem": safe.text,
                "flags": safe.suspicious_lines,
                "context_answers": {},
                "model_calls": 0,
                "notes": [],
            }
        state["case_id"] = incident_id
        for key in ("platform", "environment"):
            value = getattr(body, key)
            if value:
                state["context_answers"][key] = redact(value).text
        await app.state.graph.aupdate_state(config(incident_id), state, as_node=START)
        return {"incident_id": incident_id}

    @app.get("/api/incidents")
    async def incidents() -> Any:
        result = []
        # SQLite holds its cursor lock across yields: consume before state reads.
        checkpoints = [item async for item in app.state.graph.checkpointer.alist(None)]
        for checkpoint in checkpoints:
            # History is newest-first; only the newest root checkpoint per thread.
            cfg = checkpoint.config.get("configurable", {})
            if cfg.get("checkpoint_ns"):
                continue
            incident_id = cfg["thread_id"]
            if any(item["id"] == incident_id for item in result):
                continue
            try:
                current = await snapshot(incident_id)
            except Exception as exc:  # noqa: BLE001 - one bad checkpoint must not hide the rest
                logger.warning("Skipping unreadable incident %s: %s", incident_id, exc)
                continue
            values = merged(current)
            context = jsonable_encoder(values.get("context", {}))
            triage = jsonable_encoder(values.get("result", {}))
            result.append(
                {
                    "id": incident_id,
                    "title": values.get("problem", "").split("\n")[0],
                    "severity": triage.get("severity"),
                    "category": triage.get("category"),
                    "stage": stage(values, current),
                    "environment": context.get("environment")
                    or values.get("context_answers", {}).get("environment"),
                    "updated_at": max(
                        current.created_at or "", leaf(current).created_at or ""
                    ),
                }
            )
        return safe_output(result)

    @app.get("/api/incidents/{incident_id}")
    async def incident(incident_id: str) -> Any:
        snap = await snapshot(incident_id)
        values = merged(snap)
        interrupts = pending(snap)
        question = dict(interrupts[0].value) if interrupts else None
        if question and question.get("kind") == "log_access":
            question["folder"] = values.get("log_root", question.get("folder"))
        return safe_output(
            {
                "id": incident_id,
                "context": values.get("context", values.get("context_answers", {})),
                "stage": stage(values, snap),
                "triage_result": values.get("result"),
                "plan": plan_view(values),
                "flags": values.get("flags", []),
                "evidence": values.get("evidence", [])
                + values.get("engineer_evidence", []),
                "pending_interrupt": {
                    "type": question.get("type", question.get("kind")),
                    "payload": question,
                }
                if question
                else None,
            }
        )

    @app.post("/api/incidents/{incident_id}/logs")
    async def upload(incident_id: str, file: UploadFile) -> Any:
        lock = idle(incident_id)
        async with lock:
            snap = await snapshot(incident_id)
            values = merged(snap)
            questions = pending(snap)
            if (
                values.get("approved")
                or (questions and questions[0].value.get("kind") != "log_access")
                or values.get("result")
            ):
                raise HTTPException(409, "Upload before log approval")
            name = file.filename or ""
            if not re.fullmatch(r"[\w.-]+", name) or name in {".", ".."}:
                raise HTTPException(422, "Invalid filename")
            if not (file.content_type or "").startswith("text/"):
                raise HTTPException(415, "Only UTF-8 text uploads are accepted")
            folder = local_path(get_settings().runs_dir / "uploads" / incident_id)
            folder.mkdir(parents=True, exist_ok=True)
            target = local_path(folder / name)
            temporary = local_path(folder / f".{uuid4().hex}.part")
            size = 0
            decoder = codecs.getincrementaldecoder("utf-8")()
            try:
                with temporary.open("xb") as stream:
                    while chunk := await file.read(1024 * 1024):
                        size += len(chunk)
                        if size > get_settings().api_upload_max_bytes:
                            raise HTTPException(413, "File exceeds 50 MB")
                        if b"\x00" in chunk:
                            raise HTTPException(415, "Binary content is not accepted")
                        decoder.decode(chunk)
                        stream.write(chunk)
                    decoder.decode(b"", final=True)
                if target.exists():
                    raise HTTPException(409, "File already exists")
                temporary.replace(target)
                await app.state.graph.aupdate_state(
                    leaf(snap).config, {"log_root": str(folder)}
                )
            except UnicodeDecodeError:
                raise HTTPException(415, "Upload must be UTF-8 text") from None
            finally:
                temporary.unlink(missing_ok=True)
                await file.close()
            return safe_output({"filename": name, "size": size})

    @app.post("/api/incidents/{incident_id}/resume", status_code=202)
    async def resume(incident_id: str, body: ResumeIncident) -> Any:
        lock = idle(incident_id)
        async with lock:
            snap = await snapshot(incident_id)
            interrupts = pending(snap)
            if not interrupts:
                raise HTTPException(409, "Incident has no pending interrupt")
            question = interrupts[0].value
            kind = question.get("type", question.get("kind"))
            payload = body.payload
            if body.kind == "retriage":
                values = merged(snap)
                if kind != "step" or values.get("retriage_rounds", 0) >= 2:
                    raise HTTPException(
                        409, "Re-triage requires an active step and budget"
                    )
                text = payload.get("output", "") if isinstance(payload, dict) else ""
                safe = redact(text)
                await app.state.graph.aupdate_state(
                    leaf(snap).config,
                    {
                        "decision": Interpretation(
                            decision="retriage", reason="Engineer request"
                        ),
                        "retriage_rounds": values.get("retriage_rounds", 0) + 1,
                        "engineer_evidence": [
                            *values.get("engineer_evidence", []),
                            *[
                                Evidence(source_file="engineer", line_no=n, text=line)
                                for n, line in enumerate(safe.text.splitlines(), 1)
                            ],
                        ],
                        "flags": [*values.get("flags", []), *safe.suspicious_lines],
                    },
                    as_node="interpret",
                )
                response = {}
            elif body.kind in {"approve_save", "approve_logs"}:
                expected = (
                    "approve_save" if body.kind == "approve_save" else "log_access"
                )
                if kind != expected:
                    raise HTTPException(409, "Resume kind does not match interrupt")
                response = (
                    {"approved": payload}
                    if isinstance(payload, bool)
                    else dict(payload)
                )
                if type(response.get("approved")) is not bool:
                    raise HTTPException(422, "approved must be a boolean")
                if body.kind == "approve_logs":
                    root = merged(snap).get("log_root")
                    if response.get("roots") not in (None, [root]):
                        raise HTTPException(
                            422, "Log approval cannot broaden the incident root"
                        )
                    window = response.get("window") or {}
                    if not isinstance(window, dict):
                        raise HTTPException(422, "window must be an object")
                    response = {
                        "approved": response["approved"],
                        "start_time": window.get("start_time"),
                        "end_time": window.get("end_time"),
                    }
            elif body.kind == "step_result":
                if kind != "step" or not isinstance(payload, dict):
                    raise HTTPException(409, "Expected step result")
                if payload.get("step", payload.get("n")) != question["n"]:
                    raise HTTPException(422, "Step number must match the pending step")
                try:
                    response = StepReply.model_validate(payload).model_dump()
                except ValidationError:
                    raise HTTPException(422, "Invalid step result") from None
            else:
                if kind not in {"context", "evidence"} or not isinstance(payload, dict):
                    raise HTTPException(409, "Expected clarification answer")
                allowed = set(question.get("slots", []))
                if set(payload) - allowed or any(
                    not isinstance(v, str) for v in payload.values()
                ):
                    raise HTTPException(
                        422, "Answer must contain requested string slots"
                    )
                response = payload or {"skip": True}
            commands[incident_id] = Command(resume=response)
        return {"incident_id": incident_id}

    @app.get("/api/incidents/{incident_id}/events")
    async def events(incident_id: str) -> EventSourceResponse:
        snap = await snapshot(incident_id)
        lock = locks.setdefault(incident_id, asyncio.Lock())
        if lock.locked():
            raise HTTPException(409, "Incident already has an active event stream")
        await lock.acquire()

        async def stream() -> AsyncIterator[dict[str, str]]:
            def event(name: str, data: Any) -> dict[str, str]:
                return {"event": name, "data": json.dumps(safe_output(data))}

            try:
                command = commands.pop(incident_id, None)
                if pending(snap) and command is None:
                    for item in pending(snap):
                        yield event("interrupt", item.value)
                elif snap.next or command is not None:
                    cfg = config(incident_id)
                    with case_trace(cfg), tool_context(incident_id):
                        async for namespace, mode, data in app.state.graph.astream(
                            command,
                            config=cfg,
                            stream_mode=["updates", "custom"],
                            subgraphs=True,
                        ):
                            if mode == "custom":
                                yield event(data.get("event", "node_started"), data)
                                continue
                            for node, update in data.items():
                                if node == "__interrupt__":
                                    for item in update:
                                        yield event("interrupt", item.value)
                                    continue
                                if not isinstance(update, dict):
                                    continue
                                summary = (
                                    f"{len(update['signatures'])} signatures found"
                                    if node == "evidence" and "signatures" in update
                                    else node.replace("_", " ") + " complete"
                                )
                                yield event(
                                    "node_finished", {"node": node, "summary": summary}
                                )
                                if update.get("result"):
                                    yield event(
                                        "triage_result",
                                        update["result"].model_dump(exclude={"flags"}),
                                    )
                                if update.get("plan"):
                                    yield event("plan_updated", plan_view(update))
                yield event("done", {"incident_id": incident_id})
            except Exception as exc:
                # Exception messages can contain provider requests/raw diagnostic data.
                yield event(
                    "error",
                    {
                        "type": type(exc).__name__,
                        "message": "Incident run failed; inspect local diagnostics",
                    },
                )
                yield event("done", {"incident_id": incident_id})
            finally:
                lock.release()

        return EventSourceResponse(stream())

    @app.get("/api/environments/{environment}/topology")
    async def topology(environment: str, incident_id: str | None = None) -> Any:
        try:
            topo = load_topology(environment)
        except (ValueError, FileNotFoundError):
            raise HTTPException(404, "Unknown environment") from None
        values = merged(await snapshot(incident_id)) if incident_id else {}
        context = jsonable_encoder(values.get("context", {}))
        if context.get("environment") not in (None, environment):
            raise HTTPException(409, "Incident belongs to a different environment")
        result = jsonable_encoder(values.get("result", {}))
        related = result.get("related_components", [])
        nodes = []
        for component in topo["components"]:
            node = {**component, "status": "quiet"}
            cid = component["id"]
            if cid in related:
                node.update(status="check_next", order=related.index(cid) + 1)
            for entry in values.get("history", []):
                if entry["step"]["where"] == cid:
                    reply = entry["reply"]["status"]
                    if reply != "skipped":
                        node["status"] = (
                            "checked_issue"
                            if reply == "failed"
                            or entry["decision"]["decision"] in {"retriage", "escalate"}
                            else "checked_ok"
                        )
            if cid == result.get("affected_component"):
                node["status"] = "affected"
            nodes.append(node)
        return safe_output({"nodes": nodes, "edges": topo["links"]})

    @app.get("/api/knowledge/{doc_id}")
    async def knowledge(doc_id: str) -> Any:
        for doc in load_documents():
            if doc.doc_id == doc_id:
                front = doc.model_dump(mode="json", by_alias=True, exclude={"body"})
                return safe_output(
                    {
                        "id": doc.doc_id,
                        "title": doc.title,
                        "type": doc.doc_type,
                        "front_matter": front,
                        "body": doc.body,
                    }
                )
        raise HTTPException(404, "Unknown knowledge document")

    dist = local_path(get_settings().api_static_dir)
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app


def main() -> None:
    settings = get_settings()
    uvicorn.run(create_app(), host=settings.api_host, port=settings.api_port)
