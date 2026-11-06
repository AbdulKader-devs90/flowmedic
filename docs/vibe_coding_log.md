# Vibe Coding Log

How this project is built: Claude (planning, content, reviews, docs) writes one prompt per step; Codex (GPT-6.1 Sol, Medium, full access, local VS Code) writes the code; the engineer runs the acceptance checks and pushes. Every prompt is stored in `docs/prompts/`.

## Step 0: repo and laptop setup (6 Nov 2026)
- Tools: GitHub private repo, Git with the GitHub noreply identity, GitHub CLI, uv with Python 3.11, Codex VS Code extension.
- Iteration: Codex panel disappeared in VS Code Restricted Mode; fixed by trusting the folder.

## Step 1: scaffold, config, model clients, tracing (6 Nov 2026)
- Prompt: `docs/prompts/step-01-scaffold.md`
- Result: AGENTS.md rules, pyproject with uv, config via pydantic-settings, `get_llm(role)` with fallbacks, LangSmith run metadata helper, smoke test. Ruff clean, 15 tests passed. Codex took about 18 minutes.
- Iteration: the first smoke run skipped every role (no `.env` yet). After adding keys, the fast role (Nebius, Qwen3-30B-A3B-Instruct-2507) answered OK in 0.60 s and LangSmith tracing turned on.
- Decision: no paid API credits. The cohort's free credits (Nebius Token Factory, LangSmith, Pinecone, Tavily) cover the project, so all model roles move to Nebius in Step 2. Models chosen from the Nebius catalog after checking the 9 Nov 2026 deprecation list and tool-calling support.

## Content added by Claude before Step 2
- 16 incidents, 14 runbooks (from field experience plus IBM docs and community threads), 5 platform profiles (webMethods, Kong, Oracle, Linux, Windows), 2 anonymized topologies, a fixed category list, controlled root-cause IDs, and 12 test scenarios with expected answers (`data/scenarios/`).
