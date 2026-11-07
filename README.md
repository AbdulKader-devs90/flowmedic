# FlowMedic

**Diagnose the break. Guide the fix.** FlowMedic is a read-only, two-agent triage assistant for integration-platform incidents, starting with webMethods and a light Kong profile. The Triage Agent classifies incidents and finds solved cases, runbooks or vendor documentation; the Planner Agent guides the engineer through the fix. The engineer runs every command. Steps 1–4 provide triage, topology-aware planning, an engineer step loop, persistent checkpoints, environment memory and approved incident saves. The UI is next.

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git. Run commands from the repository root; uv selects Python 3.11.

macOS:

```sh
uv sync
cp .env.example .env
# Edit .env with your provider keys, model IDs and Nebius console endpoint.
uv run python -m flowmedic.smoke
uv run pytest
```

Windows (PowerShell):

```powershell
uv sync
Copy-Item .env.example .env
# Edit .env with your provider keys, model IDs and Nebius console endpoint.
uv run python -m flowmedic.smoke
uv run pytest
```

No credentials are required to import the package or run unit tests. The smoke check skips roles with missing keys; configured roles also require their model ID and, for Nebius, its base URL. Each role selects its provider independently: `FAST_PROVIDER=nebius`,
`STRONG_PROVIDER=nebius`, `ALT_PROVIDER=anthropic` by default. Valid providers are
`nebius`, `anthropic`, and `openai`. Set `FAST_MODEL`, `STRONG_MODEL`, or `ALT_MODEL`
to override that role's model; an empty value uses `NEBIUS_MODEL`,
`ANTHROPIC_MODEL`, or `OPENAI_MODEL` for the selected provider. To run all roles
through Nebius, set all three provider values to `nebius` and optionally choose
different models per role. Nebius always requires `NEBIUS_BASE_URL`.
Fallbacks are fast → strong and strong → alt; an unkeyed fallback is omitted.
A keyed fallback still needs a valid model and endpoint. Smoke output lists
`role | provider | model | reply | latency`. Set `LANGSMITH_API_KEY` to upload traces to `flowmedic-dev`; tracing is inactive without that key. Smoke replies are displayed only; future outputs used by code must use Pydantic structured output.

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -m live
```

Live tests call a real API and may incur charges; they are excluded by default. Keep `.env` local and never commit secrets.

Two-laptop rule: **pull before work, commit and push after**. On each laptop, run `git pull` before making changes and `git add`, `git commit`, and `git push` after finishing. Keep provider keys in each laptop's local `.env`.

Step 2 adds validated knowledge/scenario loaders, state models, topology checks,
secret masking, diagnostic parsers, and hybrid retrieval. Steps 3–4 add triage and planner graphs; the UI is next.
Seed content is read without modification.

Configure `VECTOR_BACKEND=pinecone` and `PINECONE_API_KEY` in `.env` to use the
shared index (`PINECONE_INDEX`). Ingestion creates a missing serverless index,
uses hosted `EMBED_MODEL=multilingual-e5-large` embeddings, and upserts by document
ID. The ingestion command is explicit approval to index the existing seed content.

```sh
uv run python -m flowmedic.knowledge.ingest
uv run python -m flowmedic.knowledge.try_search SC-001
uv run python -m flowmedic.knowledge.try_search SC-007
```

For a local backend, set `VECTOR_BACKEND=chroma` instead and run ingestion again.
Chroma persists in `chroma_data/` and downloads its default local embedding model
into `.cache/chroma/` on first use. It needs internet for that initial download,
but no API key. All content/config paths resolve from the repository root.

Hybrid scores use `KB_VECTOR_WEIGHT=0.6` and `KB_SIGNATURE_WEIGHT=0.4`.
Cosine similarity is calibrated with
`clamp((raw - VEC_FLOOR) / (VEC_CEIL - VEC_FLOOR), 0, 1)`; the defaults are
`VEC_FLOOR=0.80` and `VEC_CEIL=0.86` for multilingual-e5-large. `KBMatch` retains
both `raw_vector_score` and calibrated `vector_score`. Retune for other embedding
models, including Chroma's default local model.

Signature coverage is the fraction of the document's own signatures matched:
normalized error codes match extracted codes exactly, while phrase signatures
match case-insensitively in masked logs. Version, when supplied, filters documents
with incompatible version lists. `KB_KNOWN_FIX=0.60` requires a signature or explicit
category corroboration; `KB_SIMILAR=0.40` returns similar candidates. These defaults
were tuned on 11 development scenarios, pending the larger Week 4 golden set.
The CLIs use fixture platform/context, problem and logs for retrieval; expected
routes and KB IDs are used only to evaluate predictions.

```sh
uv run python -m flowmedic.knowledge.route_report
# Print the complete parameter grid; reuse each scenario's raw retrieval results.
uv run python -m flowmedic.knowledge.route_report --grid
```

The report excludes clarification scenarios. PASS requires the correct route and,
where expected KB IDs are supplied, a matching top document. Route accuracy covers
all eligible scenarios; top-1 doc accuracy covers only scenarios with expected KB
IDs. Existing `.env` overrides take precedence over defaults; update any older
calibration/threshold entries to the values in `.env.example` when adopting them.

Tools emit LangSmith spans when configured, with version/model/case metadata.
Raw diagnostic arguments and results are omitted from spans; secrets are masked
and suspicious instruction lines quarantined before embedding. The live backend
test is opt-in: `uv run pytest -m live tests/test_knowledge.py`.


Step 3 runs triage from the terminal:

```sh
uv sync
uv run python -m flowmedic.smoke
uv run python -m flowmedic.agents.triage.run SC-001
# Pre-answer missing slots and approve the displayed full log export:
uv run python -m flowmedic.agents.triage.run SC-001 --answer version=10.15 --approve-logs
uv run python -m flowmedic.agents.triage.run SC-007 --answer version=10.15 --answer os=linux --approve-logs
uv run python -m flowmedic.agents.triage.run SC-009 --approve-logs
```

The graph extracts context with the fast model, requests log access, reads approved
evidence, then asks for profile slots still missing after signature inference and
environment memory (up to two rounds). A null window means the whole supplied export. `--approve-logs` approves
that displayed export. In a terminal, enter `y` to approve; without a terminal,
unspecified answers are skipped and log access is denied unless the flag is set.
The final text and `runs/<case_id>.json` include evidence references, source labels,
risks/rollback, diagnostic gaps, and quarantined flags. `runs/` is ignored by Git.
Only the scenario expected.json `environment` field supplies engineer-selected UI
context; expected categories, causes and routes are never passed into triage. SC-007's report omits the
platform; supply `--answer platform=webmethods --answer component=integration_server`
as well when those facts are known, or answer the interactive questions.

The log reader exposes only `list_files`, `grep`, `tail`, and `stats` through the
official FastMCP stdio server. It rejects paths outside the allowlist, traversal,
escaping symlinks, and files over 50 MB. Every returned line is masked; suspicious
lines are separated into flags before parsing or model input. The graph uses only
approved roots; optional additional roots are a JSON list in `LOG_ROOTS`.
`LOG_TRANSPORT=stdio` is the default; `inprocess` uses the same reader for tests.
A failed MCP startup falls back locally with a recorded note; tool rejections do
not trigger fallback. You can also start the configured server directly:

```sh
uv run python -m mcp_servers.log_reader.server
```

Classification uses only IDs from `knowledge/root_causes.yaml`. Known fixes use
verified incident resolutions and their runbooks. Similar matches include those
steps plus vendor research; new issues use vendor research. Configure
`TAVILY_API_KEY` for trusted-domain research (then wider search for sparse results).
Unavailable/empty search retries once, then uses the strong model with every step
labelled `model` and a vendor support suggestion. Cited steps must point to supplied
result URLs. Both model-derived and documented change/destructive steps require
risk and rollback; the engineer executes every step.

`MAX_LLM_CALLS=25` caps model calls including structured-output repairs and vendor
research. Tool failures retry once and reduce confidence through recorded gaps.
The triage-only CLI uses `InMemorySaver`; the full incident CLI below uses SQLite. LangSmith receives one case trace
with graph/resume, node, model, and tool children when tracing is configured.

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run pytest -m live tests/test_triage.py
```

Offline coverage includes the actual graph and a local MCP stdio round trip, with
fake structured LLMs, retrieval and Tavily. The live triage test calls real models,
retrieval and potentially vendor search; it is deselected by default.


Step 4 runs the full incident workflow:

```sh
uv sync
uv run python -m flowmedic.run SC-001 --auto --answer version=10.15
uv run python -m flowmedic.run SC-008 --auto
uv run python -m flowmedic.run KONG-SC-01 --auto
# Interactive engineer answers, log approval and step confirmation:
uv run python -m flowmedic.run SC-001 --environment sample-prod
```

`--answer k=v` is repeatable. `--auto` approves the scenario log export and uses
its scripted engineer responses, including confirmation of changes. The simulator
selects the unused entry with the most keywords when every keyword matches
case-insensitively, breaks ties in file order, and consumes each entry once per
incident (including re-triage). It falls back to the fixture default. Run demos
sequentially against the shared SQLite file. Neither mode
executes plan commands. Saves are rejected by default in automatic demos;
`--approve-save` explicitly approves writing the displayed incident record into
`knowledge/incidents/` and indexing that single document. Interactive mode asks
for save approval. Existing seed documents are never overwritten. Failed indexing
leaves the approved Markdown in place with a recorded gap for explicit reindexing.

Each step shows its topology component, provenance, expected output and decision
rule. Interactive output accepts multiple lines; finish the paste with a single
`.` on its own line. Change/destructive steps require specific risk/rollback and engineer
confirmation. Output is masked and parsed before structured interpretation. New
root-cause evidence hands back to triage, at most twice; exhausted plans, budgets
or iteration limits escalate with a vendor support draft. Incident records use
literal masked engineer observations (bounded excerpts), so summarization cannot
invent command execution. A successful diagnostic alone does not establish a fix.

The initial plan has 5–10 steps. Validated insertions can extend the execution
queue to 40 entries; the loop stops after 30 observations or `MAX_LLM_CALLS`.
`MAX_OUTPUT_TOKENS=16384` includes both reasoning and the structured answer.
`FAST_TIMEOUT_SECONDS=60`, `STRONG_TIMEOUT_SECONDS=180` and
`ALT_TIMEOUT_SECONDS=180` allow longer structured plans to finish.
The parent emits custom `{node, summary}` progress events for the future UI.
One LangSmith `incident` root spans triage, planning, pauses and re-triage.

Full transcripts/state are saved to `runs/<case_id>-full.json`. SQLite checkpoints
are in `runs/checkpoints.sqlite`, with a unique `<case_id>-<UTC timestamp>` thread.
The graph API can resume that thread with `Command(resume=...)` after reconstructing
the graph and saver; the CLI starts a new incident each invocation. Environment
memory uses LangGraph `SqliteStore` in `runs/environments.sqlite` when available,
with `runs/environments.json` as a fallback, keyed by environment,
containing engineer-provided platform/version/OS and approved log roots. It does
not authorize subsequent log access. Explicit environment selection takes
precedence over the last confirmed environment for the platform; defaults are `DEFAULT_ENVIRONMENT=sample-prod`, or the Kong profile's
`kong-sample`. An unknown environment records a missing-topology gap.

`RUNS_DIR` and `KNOWLEDGE_DIR` may be configured to other in-repository folders.
Unit tests use fake models and temporary knowledge directories; real full-graph
coverage is opt-in with `uv run pytest -m live tests/test_planner.py`.

### Local HTTP API (Step 5a)

```sh
uv sync
uv run flowmedic-api
# In another terminal:
curl -s localhost:8000/api/health
curl -s localhost:8000/api/scenarios
curl -s -X POST localhost:8000/api/incidents \
  -H 'content-type: application/json' -d '{"scenario_id":"SC-001"}'
# Use incident_id from the response:
curl -N localhost:8000/api/incidents/INCIDENT_ID/events
```

The server binds to `127.0.0.1:8000`. `API_HOST`, `API_PORT`,
`API_CORS_ORIGINS` (JSON array) and `API_STATIC_DIR` are settings in `.env`.
Development CORS permits `http://localhost:5173`. When `app/web/dist` exists at
startup, its files and index are served at `/`. Interactive endpoint documentation
is at `/docs`.

Creating an incident checkpoints its initial state without making a model call.
Subscribe to `GET /api/incidents/{id}/events` to run it until the next interrupt
or completion. Events include node start/finish, tool results, triage/plan updates,
structured interrupts, errors and done. `done` means this stream ended; inspect
`pending_interrupt` to distinguish a pause from completion. One stream per incident
is allowed. Reopening a paused incident replays its question without running it.
After `POST /api/incidents/{id}/resume`, subscribe to `/events` again. The resume
is queued in this process until subscribed; after a server restart, resubmit any
unconsumed resume. Checkpointed incident state and questions survive restarts.
Disconnecting cancels the active stream; inspect the latest checkpoint before
reconnecting. Use one server worker for the local API.

Resume bodies use `{ "kind": ..., "payload": ... }`:

- `answer`: requested context slots, such as `{"version":"10.15"}`, or
  `{"evidence":"timestamped diagnostic text"}` for evidence questions.
- `approve_logs`: `{"approved":true,"roots":["the pending folder"],"window":
  {"start_time":null,"end_time":null}}`. Roots cannot broaden the incident's
  allowlist. `false` declines access.
- `step_result`: `{"step":1,"status":"done","output":"pasted output",
  "confirmed":true}`. Status also accepts `skipped` or `failed`. Mutations still
  require explicit human execution confirmation; the API never executes commands.
- `approve_save`: `true` or `false` (or `{"approved":true}`). This retains the
  existing human-approved knowledge save and indexing behavior.
- `retriage`: `{"output":"new diagnostic evidence"}` at a pending planner step,
  using the existing handoff and two-round limit.

`GET /api/incidents` lists checkpointed threads. `GET /api/incidents/{id}` exposes
context, triage, the plan with step statuses, flags, evidence and pending question.
Topology is at `/api/environments/{env}/topology?incident_id=...`; knowledge is at
`/api/knowledge/INC-003`. Topology `checked_ok` means a completed check whose
recorded decision continued; it is not an independent assertion of system health.

Upload one UTF-8 text export per multipart `file` field with
`POST /api/incidents/{id}/logs`, before log approval. Repeat to add files. Files
over 50 MiB, non-text MIME types, invalid UTF-8, NUL bytes and unsafe filenames
are rejected. Files go under `runs/uploads/{id}/` (relative to `RUNS_DIR`), replacing
the scenario folder as that incident's selectable read-only log root. Existing
filenames are not overwritten. Multipart spill files also stay under `RUNS_DIR`.
Every response string is masked; quarantined lines appear only in `flags`.
Raw exports remain local and are read only after approval.

```sh
uv run ruff check .
uv run pytest
```
