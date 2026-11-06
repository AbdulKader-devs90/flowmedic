# FlowMedic

**Diagnose the break. Guide the fix.** FlowMedic is a read-only, two-agent triage assistant for integration-platform incidents, starting with webMethods and a light Kong profile. The Triage Agent will classify incidents and find solved cases, runbooks or vendor documentation; the Planner Agent will guide the engineer through the fix. The engineer runs every command. Steps 1–3 provide configuration, knowledge retrieval, safe log access, vendor research, and a checkpointed Triage Agent CLI. The Planner Agent and UI are future steps.

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
secret masking, diagnostic parsers, and hybrid retrieval. Step 3 adds graph execution and triage; the Planner and UI remain future steps.
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

The graph extracts context with the fast model, pauses for missing profile slots
(up to two rounds), and requests a specific log folder and time window before
reading. A null window means the whole supplied export. `--approve-logs` approves
that displayed export. In a terminal, enter `y` to approve; without a terminal,
unspecified answers are skipped and log access is denied unless the flag is set.
The final text and `runs/<case_id>.json` include evidence references, source labels,
risks/rollback, diagnostic gaps, and quarantined flags. `runs/` is ignored by Git.
Scenario expected labels are never used by triage. SC-007's report omits the
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
Graph state uses `InMemorySaver`: interrupts resume within the same CLI process;
state does not survive restarting the process. LangSmith receives one case trace
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
