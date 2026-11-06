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

## Step 2: data models, loaders, parsers, redaction, topology, knowledge search (6 Nov 2026)
- Prompt: `docs/prompts/step-02-knowledge-layer.md`
- Result: per-role providers (all three roles on Nebius), Pydantic state models, loaders that validate all content against the category and root-cause vocabularies, signature/jstack/vmstat/ss parsers, secret masking and injection flagging, topology dependency walk, Pinecone ingest (30 documents, hosted multilingual-e5-large embeddings) with a Chroma fallback, hybrid search and routing. 28 tests passed.
- Iteration: SC-001 ranked the right incident (INC-003) first but routed "similar" (score 0.712 < 0.80). Diagnosis (Claude): e5 cosine scores are compressed (unrelated documents still scored ~0.82), and phrase signatures were not matched against the log text, so only error codes counted.

## Step 2b: routing calibration (6 Nov 2026)
- Prompt: `docs/prompts/step-02b-routing-calibration.md`
- Changes: phrase signatures matched against masked log text; signature score = coverage of the document's own signatures; vector score rescaled between a floor and ceiling; a `route_report` CLI over all scenarios; a 108-combination grid search for the weights and thresholds (results in `docs/retrieval-grid.txt`).
- Chosen values: VEC_FLOOR=0.80, VEC_CEIL=0.86, weights 0.60 vector / 0.40 signatures, KB_KNOWN_FIX=0.60, KB_SIMILAR=0.40.
- Result: route accuracy 11/11 and top-1 document accuracy 9/9 on the dev scenarios; 40 tests passed.
- Caveat: tuned on the same 11 scenarios it is scored on, and the vector band (0.80-0.86) is narrow. The Week 4 golden set (40 cases) checks whether this generalizes.
