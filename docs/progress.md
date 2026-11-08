# Step 2 done

Implemented small Pydantic state contracts, repository-root loaders with controlled
category/root-cause validation, platform profiles and scenario loading, ordered
topology checks, diagnostic parsers (signatures, thread dumps, memory/load/swap,
connections), secret masking and suspicious-line quarantine. Existing knowledge,
profiles, topologies and scenario content were read without changes.

Added a VectorStore protocol, Pinecone hosted inference/serverless ingestion and
local Chroma persistence with its default embedding model. Ingestion upserts one
vector per document ID. Hybrid search combines configured vector similarity and
normalized signature overlap; routing requires corroboration for a known fix.
Tool tracing carries case/version/model metadata and omits raw diagnostic payloads.
No agents, graph execution or UI were added.

Run from the repository root:

```sh
uv sync
# Configure .env: VECTOR_BACKEND=pinecone and PINECONE_API_KEY,
# or VECTOR_BACKEND=chroma for local embeddings (initial model download required).
uv run ruff check .
uv run pytest
uv run python -m flowmedic.knowledge.ingest
uv run python -m flowmedic.knowledge.try_search SC-001
uv run python -m flowmedic.knowledge.try_search SC-007
# Optional real-backend test:
uv run pytest -m live tests/test_knowledge.py
```

Validation: lint and format checks passed; 40 offline tests passed, with 2 live
tests deselected by default. Backend adapter and trace metadata tests use mocks.
The configured Pinecone backend previously ingested all 30 documents successfully.
Chroma is implemented; real Chroma model download/embedding has not been validated.

## Step 2 follow-up: signature coverage and vector calibration

Replaced query-signature coverage with coverage of each document's own signatures.
Normalized error codes must match extracted codes exactly. Phrase signatures match
case-insensitively in masked logs; quarantined injection lines cannot create hits.
The CLI passes logs separately so problem text cannot provide phrase corroboration.
`KBMatch.signature_score` records coverage, `raw_vector_score` retains the backend
cosine, and `vector_score` records the calibrated value. Empty signature lists
contribute zero coverage. No scenario or document IDs appear in scoring rules.

Vector calibration uses `clamp((raw - floor) / (ceil - floor), 0, 1)`. Configuration
validates `floor < ceil`, weights summing to one, and ordered route thresholds.
Chosen defaults:

| Setting | Value |
| --- | --- |
| VEC_FLOOR | 0.80 |
| VEC_CEIL | 0.86 |
| KB_VECTOR_WEIGHT | 0.60 |
| KB_SIGNATURE_WEIGHT | 0.40 |
| KB_KNOWN_FIX | 0.60 |
| KB_SIMILAR | 0.40 |

Tried the Cartesian grid of floors {0.80, 0.82}, ceilings {0.88, 0.86}, vector
weights {0.50, 0.60, 0.40} (signature weight is the complement), known-fix
thresholds {0.80, 0.70, 0.60}, and similar thresholds {0.60, 0.50, 0.40}:
108 configurations. Each scenario is searched once, then all candidates' raw
scores are replayed locally for each configuration without repeated embeddings.
The grid ranks by route accuracy, then expected top-1 accuracy, then the explicit
grid order to prefer round values and original thresholds when equally accurate.

The selected configuration was the sole 11/11 route winner in this run, with
9/9 expected top-1 documents correct; the next-best configurations scored 10/11
routes. It keeps the original 60/40 weights. The cosine range removes the inflated
baseline while spreading relevant similarities; thresholds were adjusted for the
new score scale. SC-001 now has all three document signatures present and scores
about 0.940, routing to known_fix. SC-006 has no heap-OOM phrase match and scores
about 0.473, routing to similar. SC-009's exact connection-refused phrase and
weaker vector similarity score about 0.616, still known_fix. The two new-issue
cases score below 0.40. These values are observations, not special-case rules.

**These defaults were tuned on 11 dev scenarios and will be checked on the larger
Week 4 golden set.** This is development-set accuracy, not held-out evidence of
generalization. The calibration is specific to the current multilingual-e5 index;
retune it for other embedding models. Seed content and expected labels were not
changed. The full grid output is saved in [retrieval-grid.txt](retrieval-grid.txt).

```sh
uv run ruff check .
uv run pytest
uv run python -m flowmedic.knowledge.route_report
uv run python -m flowmedic.knowledge.route_report --grid
```

The report searches every scenario whose expected route is known_fix, similar or
new_issue (11 cases; clarify is excluded). Expected labels are read only for
eligibility and evaluation, never passed to ranking. PASS checks route and any
expected top-1 KB ID. Overall route accuracy uses all 11 cases; top-1 doc accuracy
uses only the 9 cases with expected KB IDs. Existing .env calibration settings
override the new defaults; .env.example documents all six parameters.

Next: Step 3 triage intake, clarification, classification and evidence gathering.
Preserve the read-only operations boundary and human execution/approval flow.

## Step 3: triage graph, log MCP and vendor research

Implemented the read-only FastMCP log server and a langchain-mcp-adapters stdio
client. The same reader supplies in-process tests and a startup-only fallback.
Allowed paths are restricted to scenario logs or configured LOG_ROOTS; the client
narrows each server to the approved folder. Traversal, escaping symlinks, and files
over 50 MB are rejected. Time filtering preserves original line references and
continuation lines. Secrets, including multiline private keys, are masked;
suspicious lines have separate flags and never enter classification or retrieval.

Added Tavily research with trusted platform domains, one broader search for
sparse results, one retry/backoff for search failures, and a strong-model fallback
labelled `model` with a vendor support suggestion. Structured vendor findings
validate citations against supplied results. Prompts distinguish incident facts
from search examples and favor capability checks/supported upgrades over weakened
cryptography. Unknown platforms can research the open web with an applicability
gap rather than failing profile loading.

Added an interruptible LangGraph StateGraph with InMemorySaver: structured intake,
profile clarification (two rounds), log approval, evidence/parsers, controlled
classification, hybrid KB routing, verified incident/runbook steps, vendor
research, one evidence clarification loop, and deterministic synthesis. Approved
logs can identify a missing platform only when exactly one profile has specific
signature matches beyond generic exception/Oracle extraction. Explicit CLI answers
are retained even before their slot is requested. Existing profiles, knowledge,
parsers, redaction and topology walking are reused. No Planner or UI was added.

Root-cause IDs are an enum from the existing vocabulary; classification includes
taxonomy definitions and checks evidence references. Changes/destructive steps
require risk and rollback. Model attempts, including repairs and vendor research,
share MAX_LLM_CALLS (25 maximum). Structured errors repair once then stop cleanly;
tool failures retry once then become confidence-reducing gaps. Known steps remain
available if vendor research stops. One LangSmith case span contains graph/resume,
node, model and tool children; the MCP adapter traces stdio calls in the parent
process. Configured tracing is explicitly enabled without relying on dotenv being
loaded into the process environment.

Completed the omitted per-role provider configuration: FAST_PROVIDER,
STRONG_PROVIDER and ALT_PROVIDER independently select nebius/anthropic/openai,
defaulting to nebius/nebius/anthropic. FAST_MODEL/STRONG_MODEL/ALT_MODEL override the
selected provider's model; otherwise its provider model setting is used. Key/model
errors identify the provider and missing variable. Fallbacks are included only
when the fallback role's provider has a key. Smoke output includes role, provider,
model, reply and latency. The configured local Nebius models answered for all
three roles; no credential changes were needed.

Run from the repository root:

```sh
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python -m flowmedic.smoke
uv run python -m flowmedic.agents.triage.run SC-001 --answer version=10.15 --approve-logs
uv run python -m flowmedic.agents.triage.run SC-007 --answer version=10.15 --answer os=linux --approve-logs
uv run python -m flowmedic.agents.triage.run SC-009 --approve-logs
# Optional real-model end-to-end test:
uv run pytest -m live tests/test_triage.py
```

CLI results are displayed and saved under ignored `runs/<case_id>.json`.
Non-interactive omissions are explicit skips and never silently approve logs.
A null approved time window means the complete supplied export. Tests keep
artifacts under `.cache/pytest` inside the repository. Offline verification:
89 passed, 3 live tests deselected, including a real local MCP stdio round trip,
provider/role combinations, root allowlists, SC-009 masking/quarantine, interrupted
clarification, all route branches, unavailable Tavily, citation rejection, bounded
repairs, tool retries, declined reads, and the full 25-call budget.

Limitations: in-memory checkpoints survive only within the current CLI process.
A named environment needs an actual reviewed topology; production labels are not
silently mapped to sample-prod. Generic safeguards are attached to verified
knowledge changes when the seed document supplies no recovery procedure: the
engineer must define and approve the actual recovery before executing. Web
citations enforce URL provenance, not an independent entailment proof; vendor
hypotheses remain unconfirmed. The live test remains opt-in.

Next: Step 4 Planner Agent, SQLite checkpoint persistence, environment memory and
human-confirmed execution guidance. Preserve the read-only server boundary.


Final demo observations (real configured Nebius models and services):

| Scenario | Category | Route | Outcome |
| --- | --- | --- | --- |
| SC-001 | POOL | known_fix | INC-003 resolution plus RB-02/RB-04, source verified |
| SC-007 | CONN | new_issue | SFTP algorithm mismatch; six cited steps from IBM community results |
| SC-009 | CONN | known_fix | INC-013, password masked, injection quarantined |

SC-001 reported a production environment for which no reviewed topology exists;
this is a recorded gap, not a silent substitution of sample-prod. SC-007 first
records the unanswered platform question, then identifies webMethods from the
approved logs. These are development demonstrations, not held-out evaluation.
Actual LangSmith API inspection confirmed a single case root with graph/model/tool
children for all three demos. Lint and formatting passed. Full command output,
with repository paths normalized to `<repo>`, is in [step-03-validation.txt](step-03-validation.txt).


## Step 4: planner, parent graph and environment memory

Implemented log approval/evidence before clarification, component inference from
profile signatures, engineer-selected scenario environments, configurable defaults
and Kong's profile default. Classification validates affected_component against the
reviewed topology and repairs once. Related checks use dependencies before callers.
Triage first steps are capped at six and scoped to the selected incident and its
linked runbooks; confidence uses one documented route formula, with a 0.7 penalty
for actual missing-tool evidence rather than informational notes.

Added structured strong-model planning, step-specific recovery validation,
engineer step interrupts, confirmation of changes, masked diagnostic interpretation,
validated insertions (deduplicated against the queue and history), and Command handoffs to triage for new causes (two rounds
maximum). The initial plan has 5–10 steps; inserted steps use a bounded queue,
with a 30-observation loop limit and the shared 25-call budget. Blocking lock output
is parsed explicitly. Final records retain bounded literal engineer observations;
no model summary can invent execution. Escalations include a vendor case draft.

The parent uses SQLite checkpoints, custom progress events and one LangSmith
incident trace. Blocking SDK work runs in threads so checkpoint writes can finish.
MAX_OUTPUT_TOKENS defaults to 16384: the configured reasoning model exhausted an
8192-token limit while building plans. Strong/alternate request timeouts are
configurable (180 seconds by default), after live re-planning exhausted the old
60-second timeout. Fast requests retain 60 seconds. Paths are controlled through config and
must stay in the repository. Environment memory uses LangGraph SqliteStore when available (as in this install),
with a JSON fallback under runs,
storing report/answer context and approved log roots without granting future access.

Approved incident saves use exclusive next-ID allocation and the existing YAML
front-matter contract, then upsert only the new document. Index retries reuse the
same document; failed indexing leaves the approved Markdown with a recorded gap.
Rejected saves do not create files. Automatic demos reject saving by default.

The simulator now selects the most specific unused matching entry (all keywords,
case-insensitive; file-order ties), consumes entries once across re-triage, and
falls back to default. Demo validation runs sequentially to avoid SQLite contention.
The full CLI prints triage, steps, observations, decisions, re-triage and records,
and writes runs/<case_id>-full.json. The triage-only CLI remains available.

Run from the repository root:

```sh
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python -m flowmedic.run SC-001 --auto --answer version=10.15
uv run python -m flowmedic.run SC-008 --auto
uv run python -m flowmedic.run KONG-SC-01 --auto
# Interactive engineer, with an explicit reviewed environment:
uv run python -m flowmedic.run SC-001 --environment sample-prod
# Optional real-model full-graph test:
uv run pytest -m live tests/test_planner.py
```

The CLI creates a new incident thread each invocation. The graph/saver API can
resume a persisted thread with Command(resume=...), verified by rebuilding the
graph after closing and reopening SQLite. There is no CLI resume flag yet.
Environment memory uses a separate local SQLite store; the JSON fallback is
intended for minimal, single-user installations. Fixture matching is lexical, so these
demos exercise scripted observations rather than real remediation efficacy.

Next: Step 5 Streamlit incident UI, showing progress, evidence, topology, human
step confirmation and save approval, while retaining the read-only server boundary.


### Step 4 final validation and known limitations

Latest completed checks: ruff passed; pytest reported 117 passed and 4 live tests
deselected. The demos ran sequentially: SC-001 resolved; SC-008 resolved after one
re-triage and added db_blocking_lock; KONG-SC-01 used the Kong profile and
kong-sample topology, then escalated. Full latest completed outputs are saved in
[step-04-validation.txt](step-04-validation.txt). No demo approved a knowledge save.

Known limitations:

- Kong escalates because the simulator has no output for the backend-change step.
- Lexical, one-use simulator matches can skip valid steps when generated wording differs from fixture keywords.
- Fast-model interpretation sometimes repeats stale reasoning or overstates the latest evidence.
- Numbered decision rules remain advisory: next advances sequentially, and insertions can leave stale step references.
- Strong-model planning can exhaust output or timeout budgets despite the increased limits.
- The extra SC-001 verification-before-closure live regression was stopped at the user's request; the guard passed its offline test.
- Persisted incidents can resume through the graph API, but the CLI has no resume flag.
- Custom KNOWLEDGE_DIR affects saves; retrieval loaders still read the default knowledge directory.
- Provenance validation checks references and component IDs, not independent semantic entailment of every proposed action.
- Windows runtime behavior has not been exercised in this environment.

## Step 5a: local HTTP API for the React UI

Added the FastAPI adapter in `flowmedic/api/app.py` and the `flowmedic-api`
console script, defaulting to `127.0.0.1:8000`. Added FastAPI, uvicorn,
sse-starlette, multipart support and the httpx test dependency. All API settings
live in `flowmedic/config.py`; development CORS permits localhost:5173, and a
built `app/web/dist` is served at `/` when present at startup.

Implemented health, scenario catalog, incident creation/list/snapshot, UTF-8 text
uploads, SSE execution/resume, topology status and knowledge-document endpoints.
Creation persists an initial checkpoint without a model call. Scenario creation
uses its problem and selected environment with its logs as the incident root.
Uploads switch that incident to a repository-local `runs/uploads/<id>/` read-only
root and still require log approval. Uploads reject files over 50 MiB, non-text
MIME types, NUL bytes, invalid UTF-8, unsafe names and overwrites. Multipart spool
files also stay in the configured repository-local runs folder.

SSE uses `graph.astream` with updates/custom modes and subgraph streaming.
Existing node progress events supply starts, updates supply finishes and summaries,
and small custom events expose tool successes/errors and save approval. Graph
behavior and model prompts are unchanged. Resume validates the pending question,
step identity and approval root. Explicit re-triage uses the existing planner
handoff and retains its two-round bound. Snapshots merge interrupted subgraph
state. Every response string is redacted; quarantined lines appear only in flags.
Validation errors omit rejected inputs so diagnostic secrets cannot be echoed.

Run from the repository root:

```sh
uv sync
uv run ruff check .
uv run pytest
uv run flowmedic-api
# Separate terminal:
curl -s localhost:8000/api/health
curl -s localhost:8000/api/scenarios | head -c 400
curl -s -X POST localhost:8000/api/incidents -H 'content-type: application/json' -d '{"scenario_id":"SC-001"}'
```

README documents SSE pauses, resume bodies, uploads and configuration. Offline
HTTP tests use fake graphs plus the real nested parent with fake model-dependent
nodes: scenario creation, node/tool/interrupt events, clarification resume, log
approval, masking/quarantine, step statuses, topology states, save rejection,
bounded explicit re-triage, 60 MiB upload rejection, SQLite restart persistence,
CORS and built-static serving. Verification: ruff passed; pytest reported
124 passed and 4 live tests deselected. No real model/backend calls were needed.
The requested local curl checks returned health `{"status":"ok"}`, the first
400 bytes of the scenario catalog, and incident creation
`{"incident_id":"eb7e0ccb0aeb49ecb6aceb37231343e0"}`. The dev server started once
and was stopped after checking it; the created incident remains checkpointed.

Runtime limits: use one server worker and one event stream per incident. A
submitted resume is queued in memory until `/events` consumes it; resubmit an
unconsumed resume after restart. Durable graph checkpoints and pending questions
survive restarts. A disconnected event stream cancels execution; inspect its
latest checkpoint before reconnecting. Topology `checked_ok` reflects a completed
engineer check followed by a continuing decision, not independent health proof.
Windows runtime remains untested.

Next: Step 5b React UI consuming the HTTP endpoints and structured human approvals.

## Impeccable init: existing product context

Preserved all existing PRODUCT.md text and appended the product-schema marker,
web platform, operating context, constraints, evidence sources and established
accessibility requirements. DESIGN.md remains unchanged. No UI code was created.
Facts were drawn from the existing product/design docs, README and Step 5a/5b
records; no new product decisions or visual direction were introduced.

Review with `git diff -- PRODUCT.md DESIGN.md docs/progress.md`. This is a
documentation-only update; no app, tests or live model calls were run. The
Impeccable launcher was not run because its cache/download behavior can write
outside the repository; existing context was read directly instead. The optional
build-path preference is now explicitly confirmed as code-first and saved as
`"buildPath": "code"` in `.impeccable/config.json`. Existing local hook consent
is preserved. No live-mode configuration was added because the web UI
is not implemented yet.

Next: Step 5b war-room UI, following PRODUCT.md and DESIGN.md.


## Step 5b: React incident war room

Implemented `app/web/` with Vite, strict TypeScript, React, Tailwind CSS, shadcn
Radix dialog/command/button primitives, Framer Motion, lucide-react and React
Query. Animated Beam, Border Beam and Number Ticker were installed through the
shadcn Magic UI registry, then adapted to the committed tokens and finite motion.
Geist Sans and JetBrains Mono are bundled locally. DESIGN.md remains unchanged;
its colors, type scale, spacing base, widths, radii and timing tokens are mapped
to CSS variables and the Tailwind theme.

Added the incident rail, timeline, new incident/scenario dialog, UTF-8 file
attachments, Command-K/Control-K palette, typed HTTP/SSE handling, structured
clarification/log/step/save cards, triage assessment, provenance badges, confidence
bars, knowledge/log evidence drawers, layered topology, plan stepper, clipboard
feedback and explicit execution confirmation for change steps. Shared triage
layout and a finite handoff beam connect diagnosis to planning. Reduced-motion
preferences suppress topology/beam effects; fades remain. Topology refreshes from
checkpoints after stream completion. Below 1024px, details move into a Radix drawer.

Updated README with installation, API/UI development commands, SC-001 walkthrough,
static build and validation instructions. Added ignores for npm dependencies,
frontend output and TypeScript build metadata.

Completed checks:

- `npm --prefix app/web run build`: PASS (strict TypeScript and Vite output to
  `app/web/dist`). Non-fatal advisory: main JS chunk is about 514 kB before gzip.
- `npm --prefix app/web run lint`: PASS, no findings.
- `npx impeccable detect app/web/src`: one warning, `overused-font` for Geist;
  exit 2. Retained because the task and DESIGN.md explicitly mandate Geist.
  A JSON scan confirmed warning severity and no high-severity findings. Source
  scanning is regex-only and does not verify rendered contrast.
- `npm --prefix app/web test`: 3 offline browser checks PASS against a fake
  HTTP/SSE API using local Chrome, including the SC-001-shaped approval workflow,
  exact resume payloads, masked/quarantined evidence, knowledge, keyboard focus,
  960px details drawer, reduced motion and API failure recovery.
- `uv run pytest tests/test_api.py`: 7 PASS with fake graphs/models.
- `npm --prefix app/web audit --omit=dev`: zero production vulnerabilities.
  npm reports seven moderate findings in the development lint dependency tree.

Visually inspected desktop empty/log-approval/plan states and the laptop drawer.
Local screenshots and Playwright failure traces are under ignored `.cache/`.
The first build exposed the Geist package export restriction; the first browser
check exposed an ambiguous test locator. Both passed after one correction. The
laptop render exposed inherited dialog positioning; corrected and rechecked.
No real Nebius, Tavily or Pinecone calls were made. The existing API was not
listening on localhost:8000 at verification time (connection refused), so the
Vite proxy could not return health and no live SC-001 session was attempted.
The Vite server was started once for offline checks and stopped before finishing.

Run from the repository root in two terminals:

```sh
uv run flowmedic-api
npm --prefix app/web run dev
```

Open http://localhost:5173, load SC-001, answer requested context, approve logs,
and report manually executed checks. The API still owns all model/tool tracing,
validation and explicit knowledge-save approval. No backend execution behavior
or prompts changed.

Time box reached: implementation and offline checks are complete; live browser
integration against the configured providers remains unverified. Existing API
limitations remain: one worker/stream per incident; earlier activity rows are
not persisted; evidence consists of checkpointed excerpts. The UI infers its
selectable environments from scenarios because no environment-list API exists.
Knowledge document bodies render safely as text with heading recognition, not
full Markdown formatting. Windows runtime and rendered automated contrast audit
remain unverified. No further implementation or validation was pursued past the
budget.

Next: manually walk through SC-001 with the running API and review actual model
outputs, reconnect behavior and evidence references before considering Step 5b
fully validated in the live environment.

## Step 5c-1: guided flow

Built the DESIGN.md guided war-room layout without backend or model changes.
First extracted the shell, rail, action and reference regions and formatted the
existing components without changing their behavior; build and lint passed before
implementing the guided behavior. The final regions are AppShell, LeftRail,
StageTracker, StoryTimeline, YourTurnCard and InspectorTabs with DiagnosisTab,
PlanTab, TopologyTab and EvidenceTab. Existing API client and SSE hook are retained.

- Added pure stage/progress/status derivation in `app/web/src/lib/stage.ts`, with
  Report → Logs → Diagnose → Fix → Close, agent names, plain activity labels,
  preserved acronyms and explanatory stage tooltips. Incident rows use checkpoint
  queries to show waiting, fixing/progress and closed states accurately.
- All clarification, log approval, step output and save controls now live in the
  pinned centre Your turn region at desktop and laptop widths. Commands include
  copy feedback, location, expected output, risk/rollback and the existing change
  confirmation. Sent step results show a review status until the next interrupt.
- The story groups report, approval, diagnosis, hand-off, completed steps,
  re-plans and closure by stage. Technical activity is collapsed by default;
  node start/finish pairs become one row, while tool events stay separate.
- Reference-only inspector tabs have descriptions and helpful empty states.
  Plan opens at hand-off and re-plan; active-step scrolling stays inside the
  inspector and respects reduced motion. Re-plans have a banner.
- Added War room / Setup / Knowledge navigation, next-step placeholders, the
  four-step introduction above demos and an app-bar help dialog.
- Selected incident and missing story details survive refresh in sessionStorage;
  diagnosis, plan statuses and closure still derive from API snapshots. Updated
  the existing fake-API Playwright spec for the new layout and refresh behavior.

Verified offline:

- `npm --prefix app/web run build`: PASS (TypeScript and Vite); existing non-fatal
  large-chunk advisory remains, approximately 526 kB uncompressed.
- `npm --prefix app/web run lint`: PASS.
- `npx impeccable detect app/web/src`: exit 2, only `overused-font` for Geist.
  Retained because DESIGN.md mandates Geist. Used the cached CLI with offline npm;
  the source-only detector does not check rendered contrast.
- Playwright: 5 PASS in one final suite run against the fake HTTP/SSE API. Covers
  exact approval/result payloads, confirmation gating, controls only in Your turn,
  automatic Plan selection, refresh recovery, evidence masking, re-planning,
  placeholders/help, reduced-motion laptop drawer, keyboard use and API recovery.
- `uv run pytest -q -m "not live"`: 124 PASS, 4 deselected.
- Inspected screenshots captured by that spec for desktop empty/plan and laptop
  drawer states; corrected the introduction's decimal list style after Tailwind's
  reset suppressed its markers. Final build/lint also cover this CSS correction.
  No exploratory browser sessions or live provider calls. Vite was started once
  for the spec and stopped after verification.

Run locally with the existing API and `npm --prefix app/web run dev`. Offline
browser verification uses that Vite server plus
`cd app/web && npx --offline playwright test`; all API requests in the spec are
intercepted by its fake API.

Deferred / limits: Step 5d visual polish and Step 5c-2 Setup/Knowledge pages.
The existing snapshot API omits approved folders/windows, engineer result text,
prior plan versions, revision reasons and final outcome. Those observed details
are retained only for the current browser session (including refresh); a fresh
browser session restores the facts present in the checkpoint and does not invent
missing approvals or an outcome. Revision context uses the current root cause
when available. Technical activity from earlier browser sessions remains
unavailable. No backend features were added to fill these gaps. Windows runtime
and live-model integration were not exercised in this offline step.

Next: Step 5c-2, read-only Setup and Knowledge pages; then Step 5d visual polish.

## Step 5c-2: Setup, Knowledge and help

Implemented the read-only Setup and Knowledge pages in the existing design system.
No configuration-writing UI, live model calls or new agent actions were added.

- Added GET `/api/platforms`, `/api/environments` and searchable `/api/knowledge`
  catalogs using the existing loaders. Responses include repository-relative
  source files, profile questions, log samples/pattern counts, topology counts,
  architecture availability and document verification. Architecture PNGs have a
  read-only, environment-validated endpoint. Knowledge source metadata is excluded
  from existing document serialization and embedding payloads.
- Setup lists all profiles, questions in plain language, components/log patterns,
  knowledge counts and environments using the existing topology component. Added
  expandable Kong configuration guides and `docs/CONFIGURE.md`, linked from README.
  The real topology schema uses `components` and `links`, not `nodes` and `edges`;
  layers derive from component type and dependencies use `hard: true/false`.
  The ingest command is `uv run python -m flowmedic.knowledge.ingest`.
- Knowledge supports ID/title search, table rows and keyboard-accessible document
  buttons opening the existing evidence viewer. Verification reflects front matter.
- Added field hints, platform names in environment choices, grouped demo scenarios,
  the read-only safety explanation, source/kind/severity/confidence tooltips, and
  first-visit help remembered with guarded localStorage access.
- Preserved absolute approval paths internally; UI evidence, approval and story
  paths use the snapshot's display root to render repository-relative references.
  Log discovery now excludes hidden paths and empty files, with a unit test.
  Clarified blank approval times, standardized topology label sizes, and retained
  bottom-centre → top-centre edge anchors already used by the topology component.
- Corrected re-triage status, skipped Logs/Fix stage indications, duplicate diagnosis
  notes and plan-version story labels. Save approval shows a readable record with
  collapsed JSON and explicit escalation-note wording when no steps worked.
- War room navigation, the logo, All incidents and completion actions return home.
  Incident selection uses `?incident=<id>` with browser history and refresh support;
  Escape only closes dialogs. Completion also offers Start a new incident.

Checks (offline only):

- Build: PASS after correcting the Setup preview's TypeScript snapshot shape.
  Vite retains a non-fatal chunk-size advisory (approximately 538 kB uncompressed).
- ESLint: PASS, zero warnings in the final run. Python ruff lint/format: PASS.
- `npx impeccable detect app/web/src`: one finding, `overused-font` for Geist.
  Retained as required by DESIGN.md; source scanning does not verify rendered contrast.
- Playwright: 7 PASS using the existing fake HTTP/SSE spec, extended for the catalogs,
  evidence/search, first visit and URL navigation. The supplied root invocation
  did not discover `app/web/playwright.config.ts` and failed before executing tests
  because its default Chromium binary was unavailable. Retried with
  `npx --prefix app/web playwright test --config app/web/playwright.config.ts`;
  the configured installed Chrome ran all seven successfully. No downloads or live APIs.
- `uv run pytest -q -m "not live"`: 126 PASS, 4 deselected, one final suite run.
- Inspected captured Setup, Knowledge and approval screenshots. Added explicit
  decimal list markers after Tailwind reset hid guide numbering, and made the log
  attachment hint stack below its input. Final build/lint cover these small visual
  corrections; the browser suite was not repeated for visual polish.
- Vite was started once for the fake-API checks and stopped. Existing unrelated
  development processes were left alone. Screenshots are available in `.cache/`.

Run the app with the existing local API and `npm --prefix app/web run dev`.
For offline browser checks, run the Vite server and
`cd app/web && npx --offline playwright test` (or pass the explicit config from
repo root as above). All spec API requests are intercepted. New pytest coverage
is in `tests/test_api.py` and `tests/test_log_discovery.py`.

Next: Step 5d visual polish. Live providers and Windows runtime were not exercised.
Approval stories, prior plan versions and result excerpts remain browser-session
history; the new approval boolean restores skipped-stage accuracy from checkpoints.
