# Repository rules

- Safety: no code may run commands on, or write to, any remote server, or any log or file outside this repo. Agent tools are read-only. The only write the agent makes is to its own knowledge repo, after human approval.
- Every LLM output that code depends on uses a Pydantic model via `with_structured_output`.
- All LLM and tool calls are traced to LangSmith. Each run carries metadata: `case_id` (if any), `prompt_version`, `agent_version`, `model`.
- Prompts live in `prompts.py` files as versioned constants, for example `TRIAGE_SYSTEM_V1`.
- Config only through `flowmedic/config.py` (pydantic-settings, `.env`). No keys in code. No hard-coded OS paths; use pathlib. Code must run on Windows and macOS.
- Data is synthetic or anonymized: fake hosts like `is-node-a`, IPs from `10.0.0.0/24`, no real names. No personal information (emails, phone numbers) anywhere in the repo.
- Tests use pytest. Unit tests use no network (mock the LLMs). Tests that call real APIs are marked `@pytest.mark.live` and skipped by default.
- Keep each change scoped to the current step. At the end of each task, update `docs/progress.md`: what changed, how to run it, what is next.
- Style: ruff for lint and format, type hints everywhere.
