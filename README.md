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
