# Step 1: scaffold, config, model clients, tracing

Paste everything below the line into Codex, started from the repo root (~/dev/flowmedic).

---

You are setting up a new Python project called FlowMedic in this repo. Read docs/PROJECT_PLAN.md first.

FlowMedic is a read-only, two-agent triage assistant for integration-platform incidents (webMethods first, Kong as a light second platform). A Triage Agent classifies the problem and searches a knowledge repo of solved incidents and runbooks, or researches vendor docs. A Planner Agent guides the engineer through a step-by-step fix. The engineer runs every command; the agent never writes to any server.
Stack: Python 3.11, uv, LangGraph + LangChain, LangSmith tracing, Pydantic. Streamlit and Pinecone come in later steps.

This task is ONLY the scaffold. Do not build agents, tools or UI yet.

1. Create AGENTS.md at the repo root with these rules, short and exact:
   - Safety: no code may run commands on, or write to, any remote server, or any log or file outside this repo. Agent tools are read-only. The only write the agent makes is to its own knowledge repo, after human approval.
   - Every LLM output that code depends on uses a Pydantic model via with_structured_output.
   - All LLM and tool calls are traced to LangSmith. Each run carries metadata: case_id (if any), prompt_version, agent_version, model.
   - Prompts live in prompts.py files as versioned constants, for example TRIAGE_SYSTEM_V1.
   - Config only through flowmedic/config.py (pydantic-settings, .env). No keys in code. No hard-coded OS paths; use pathlib. Code must run on Windows and macOS.
   - Data is synthetic or anonymized: fake hosts like is-node-a, IPs from 10.0.0.0/24, no real names. No personal information (emails, phone numbers) anywhere in the repo.
   - Tests use pytest. Unit tests use no network (mock the LLMs). Tests that call real APIs are marked @pytest.mark.live and skipped by default.
   - Keep each change scoped to the current step. At the end of each task, update docs/progress.md: what changed, how to run it, what is next.
   - Style: ruff for lint and format, type hints everywhere.

2. Create the folder structure shown in the "Repo layout" block of docs/PROJECT_PLAN.md. Add empty __init__.py files to make flowmedic/ and its subfolders packages. Leave later-step folders empty (add a .gitkeep). Do not touch the existing files in docs/.

3. pyproject.toml managed by uv, requires-python ">=3.11,<3.12". Dependencies: langchain, langgraph, langchain-anthropic, langchain-openai, langsmith, pydantic, pydantic-settings, python-dotenv, pyyaml. Dev dependencies: pytest, ruff. Configure pytest so tests marked "live" are skipped unless run with -m live. Run uv sync so uv.lock is created.

4. .gitignore: .env, .venv/, __pycache__/, *.pyc, .pytest_cache/, .ruff_cache/, chroma_data/, *.sqlite, *.db, .streamlit/secrets.toml, .DS_Store.
   .gitattributes: "* text=auto eol=lf", "*.png binary", "*.pdf binary".

5. .env.example with every variable, empty secret values, and a one-line comment each:
   ANTHROPIC_API_KEY, ANTHROPIC_MODEL=claude-opus-5-5
   NEBIUS_API_KEY, NEBIUS_BASE_URL (OpenAI-compatible endpoint from the Nebius Token Factory console), NEBIUS_MODEL
   OPENAI_API_KEY, OPENAI_MODEL
   TAVILY_API_KEY
   PINECONE_API_KEY, PINECONE_INDEX=flowmedic-kb, VECTOR_BACKEND=pinecone (pinecone or chroma)
   LANGSMITH_TRACING=true, LANGSMITH_API_KEY, LANGSMITH_PROJECT=flowmedic-dev, LANGSMITH_ENDPOINT=https://api.smith.langchain.com
   AGENT_VERSION=0.1.0

6. flowmedic/config.py: a Settings class (pydantic-settings) that loads .env, with a cached get_settings(). A missing key must not crash import. A provider's key is required only when that provider is used, with a clear error that names the missing variable.

7. flowmedic/llm.py: get_llm(role) where role is "fast", "strong" or "alt".
   - fast: Nebius through ChatOpenAI with NEBIUS_BASE_URL (classification, log summaries)
   - strong: Claude through ChatAnthropic with ANTHROPIC_MODEL (triage synthesis, planning)
   - alt: OpenAI through ChatOpenAI with OPENAI_MODEL (fallback, Week 4 comparison)
   Temperature 0, timeout 60 s, max_retries 2. Add get_llm_with_fallback(role): strong falls back to alt, fast falls back to strong (use .with_fallbacks). Tag each model with metadata {"model_role": role}.

8. flowmedic/tracing.py: run_config(case_id=None, prompt_version=None, run_name=None) returns a LangChain RunnableConfig with tags and metadata (case_id, prompt_version, agent_version, run_name).

9. flowmedic/smoke.py: "uv run python -m flowmedic.smoke" sends "Reply with the word OK" to fast, strong and alt. Skip a role whose key is missing and say so. Print the model name, reply and latency for each. Use run_config(run_name="smoke-test") so the calls appear in LangSmith.

10. Tests: tests/test_config.py (settings load from a temporary .env; a missing key raises the clear error only when used). tests/test_llm.py (get_llm returns the right class per role with mocked env vars; no network). One @pytest.mark.live test that runs the smoke call for "strong".

11. README.md: one paragraph on FlowMedic ("Diagnose the break. Guide the fix."), setup on Windows and macOS with uv (uv sync, copy .env.example to .env, uv run python -m flowmedic.smoke, uv run pytest), and the two-laptop rule: pull before work, commit and push after.

12. docs/progress.md: "Step 1 done" with what was built and how to run it. docs/vibe_coding_log.md: a title line only (Claude maintains this file).

When finished, run these and show me the output:
- uv sync
- uv run ruff check .
- uv run pytest
- uv run python -m flowmedic.smoke
