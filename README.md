# FlowMedic

**Diagnose the break. Guide the fix.** FlowMedic is a read-only, two-agent triage assistant for integration-platform incidents, starting with webMethods and a light Kong profile. The Triage Agent will classify incidents and find solved cases, runbooks or vendor documentation; the Planner Agent will guide the engineer through the fix. The engineer runs every command. This first step supplies configuration, model factories, tracing and a smoke check; agents, tools and UI arrive later.

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

No credentials are required to import the package or run unit tests. The smoke check skips roles with missing keys; configured roles also require their model ID and, for Nebius, its base URL. Strong uses `claude-opus-5-5` by default. Fill model IDs with identifiers available to your provider account. Fallback factories require both participating providers to be configured. Set `LANGSMITH_API_KEY` to upload traces to `flowmedic-dev`; tracing is inactive without that key. Smoke replies are displayed only; future outputs used by code must use Pydantic structured output.

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -m live
```

Live tests call a real API and may incur charges; they are excluded by default. Keep `.env` local and never commit secrets.

Two-laptop rule: **pull before work, commit and push after**. On each laptop, run `git pull` before making changes and `git add`, `git commit`, and `git push` after finishing. Keep provider keys in each laptop's local `.env`.

Step 2 adds validated knowledge/scenario loaders, state models, topology checks,
secret masking, diagnostic parsers, and hybrid retrieval. Agents, graph execution,
and UI remain future steps. Seed content is read without modification.

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
Signature overlap is the fraction of distinct extracted query signatures present
in the document after code normalization. Version, when supplied, filters documents
with incompatible version lists. `KB_KNOWN_FIX=0.80` requires a signature or explicit
category corroboration; `KB_SIMILAR=0.60` returns similar candidates. The CLI uses
only fixture platform/context, problem and logs, never expected diagnoses.

Tools emit LangSmith spans when configured, with version/model/case metadata.
Raw diagnostic arguments and results are omitted from spans; secrets are masked
and suspicious instruction lines quarantined before embedding. The live backend
test is opt-in: `uv run pytest -m live tests/test_knowledge.py`.
