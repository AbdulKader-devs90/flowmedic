# Step 1 done

Built the Python 3.11 uv scaffold, repository rules, package and future-step placeholders, central environment settings, three model roles with fallbacks, LangSmith run configuration, versioned smoke prompt, and offline unit tests plus an opt-in strong-provider live test. No agents, tools or UI are implemented.

Run from the repository root:

```sh
uv sync
# macOS: cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
# Fill provider keys, model IDs, Nebius endpoint and LangSmith key in .env.
uv run ruff check .
uv run pytest
uv run python -m flowmedic.smoke
```

Missing provider keys skip their smoke calls; live calls and LangSmith trace uploads require configured credentials. Use `uv run pytest -m live` to opt into the strong-provider API test.

Validation: `uv sync` succeeded and created `uv.lock`; ruff lint and format checks passed; pytest reported 15 passed and 1 live test deselected. The smoke command exited successfully with all three roles skipped for missing API keys. Provider connectivity and LangSmith uploads remain unverified until credentials are configured.

Next: platform profiles, anonymized topology, synthetic incidents and runbooks, and knowledge-repo ingestion/search. Later implement the agents, read-only tools and UI.
