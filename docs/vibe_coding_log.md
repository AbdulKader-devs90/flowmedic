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

## Step 3: read-only log reader (MCP), vendor-doc research, Triage Agent (6 Nov 2026)
- Prompt: `docs/prompts/step-03-triage-agent.md`
- Result: FastMCP read-only log server (allowlisted roots, traversal and size checks, masking, flagged lines kept apart), Tavily vendor research with a model-knowledge fallback, and a LangGraph Triage Agent with interrupts for clarifying questions and log access. 89 tests passed. Validation output in `docs/step-03-validation.txt`.
- Iteration: Codex found that Step 2's per-role provider change had not been built (strong was still hard-wired to Anthropic). A follow-up prompt moved all three roles to Nebius; the smoke test then answered on Qwen3-30B (0.55 s), DeepSeek-V4.1-Flash (0.84 s) and GLM-5.3 (1.04 s).
- Demo results: SC-001 -> POOL, known_fix, verified steps from INC-003; SC-007 -> CONN, new_issue, six cited IBM Community steps; SC-009 -> CONN, known_fix (INC-013), injection line quarantined and password masked.
- Review (Claude), carried into Step 4: topology never loaded (no environment), 16 first steps (unrelated runbook included), boilerplate risk/rollback text, unclear overall confidence (50%), and clarifying questions asked before reading logs (SC-007 asked for the platform twice).

## Step 4: triage fixes, Planner Agent, parent graph, SQLite memory, engineer simulator (6-7 Nov 2026)
- Prompt: `docs/prompts/step-04-planner-and-graph.md`. Codex worked for 2 h 15 min, most of it running real demos and fixing what they exposed.
- Result: logs read before clarifying questions, environment default and topology loading, first steps capped at 6, a confidence formula, Planner Agent with step-specific risk and rollback, an interpret node that decides next / insert / re-triage / escalate / resolved, parent graph with Command hand-offs, SQLite checkpoints, environment memory, approved-only incident saving, an engineer simulator and the `flowmedic.run` CLI. 117 tests passed. Output in `docs/step-04-validation.txt`.
- Demo results: SC-001 resolved (and re-triaged to db_blocking_lock when the DBA output showed a blocking session); SC-008 resolved after one re-triage that added db_blocking_lock, the multi-cause outage story; KONG-SC-01 ran on the Kong profile and topology but escalated.
- Iterations Codex hit and fixed: SQLite "database is locked" when demos ran in parallel; a LangGraph InvalidUpdateError (two nodes writing case_id in one step); a planner loop that kept re-inserting the same skipped step; simulator outputs landing on the wrong steps because the fixture keywords were too loose (Claude tightened them; the simulator now picks the best match and uses each entry once).
- Decision: stopped Codex once all three demos had passed, instead of letting it keep polishing. Known limitations are listed in `docs/progress.md`; they are good input for the Week 4 failure analysis (for example, the interpret step sometimes repeats stale reasoning).
- Follow-up (Claude): added backend-fix outputs to the Kong simulator so KONG-SC-01 can resolve instead of escalating.
