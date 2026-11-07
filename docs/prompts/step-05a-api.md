# Step 5a: FastAPI layer around the agents (streaming + resume)

Paste below the line into a NEW Codex chat (GPT-6.1 Sol, Medium, Full access) after Step 4 (Planner + parent graph + SQLite checkpointer) is committed.

---

**Budget (from AGENTS.md):** 45 minutes of work at most. Offline tests with fake models first; live checks at most 2 attempts each, one at a time. If a check still fails after 2 fixes, stop and report. Stay in scope.

Read AGENTS.md, docs/progress.md, and the parent graph from Step 4 (flowmedic/graph/main_graph.py). Build an HTTP API the React UI will use. Do not change agent behavior.

1. flowmedic/api/app.py (FastAPI) + a console script "flowmedic-api" (uvicorn, 127.0.0.1:8000). Add fastapi, uvicorn and sse-starlette (or equivalent) dependencies.
2. Endpoints:
   - GET  /api/health
   - GET  /api/scenarios -> demo scenarios (id, title from the first line of problem.md, platform, environment)
   - POST /api/incidents {message, platform?, environment?, scenario_id?} -> {incident_id}. scenario_id loads that scenario's problem text and makes its logs/ folder the allowlisted log root for this incident.
   - POST /api/incidents/{id}/logs (multipart) -> saves uploads to runs/uploads/<id>/ (allowlisted read-only root for that incident; reject files over 50 MB and non-text types).
   - GET  /api/incidents -> list (id, title, severity, category, stage, environment, updated_at) from the checkpointer.
   - GET  /api/incidents/{id} -> state snapshot: context, stage ("triage" | "planner" | "closed"), triage result, plan with step statuses, flags, evidence list, pending interrupt (type + payload) if any.
   - GET  /api/incidents/{id}/events -> Server-Sent Events while the graph runs: node_started, node_finished (node, short summary such as "3 signatures found"), tool_called (tool, target, ok/error), interrupt (the structured question or approval request), triage_result, plan_updated, error, done. Use graph.astream with stream modes "updates" and "custom"; emit custom events from nodes where a summary is useful (add small get_stream_writer calls in nodes if missing, no behavior change).
   - POST /api/incidents/{id}/resume {kind, payload}: kind = "answer" (clarifying slots), "approve_logs" (approved true/false, roots, window), "step_result" (step n, status done/skipped/failed, pasted output), "approve_save" (true/false), "retriage". Resumes the graph with Command(resume=...) on the same thread_id and streams again on /events.
   - GET  /api/environments/{env}/topology?incident_id= -> nodes and edges from the topology file, plus per-node status for that incident: "affected", "check_next" (with order), "checked_ok", "checked_issue", or "quiet".
   - GET  /api/knowledge/{doc_id} -> title, type, front matter and markdown body for "Open INC-003".
3. Masking: every string the API returns that came from logs passes through redact; flagged lines are returned only in the flags list.
4. CORS for http://localhost:5173 in dev. When app/web/dist exists, serve it as static files at "/" so one command runs everything.
5. Tests with httpx TestClient and a fake graph: create from scenario, SSE emits node events and an interrupt, resume answer continues, topology statuses, knowledge doc fetch, upload rejects a 60 MB file.
6. Update docs/progress.md and README.md (how to run the API).

Run and show: uv run ruff check . ; uv run pytest ; then start "uv run flowmedic-api" and show the output of:
curl -s localhost:8000/api/health ; curl -s localhost:8000/api/scenarios | head -c 400 ; curl -s -X POST localhost:8000/api/incidents -H 'content-type: application/json' -d '{"scenario_id":"SC-001"}'
