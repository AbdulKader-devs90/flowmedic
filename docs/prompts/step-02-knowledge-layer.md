# Step 2: data models, loaders, parsers, knowledge repo search

Paste everything below the line into Codex (GPT-6.1 Sol, Medium, Full access), from the repo root.

---

Read AGENTS.md, docs/progress.md and docs/PROJECT_PLAN.md (sections "Scope", "Tools, memory, approvals and failure handling", "Platform topology"). Step 1 is done.

The content for this step already exists in the repo. Do NOT rewrite it; only read it:
- knowledge/categories.yaml (fixed triage labels), knowledge/root_causes.yaml (controlled root-cause IDs)
- knowledge/incidents/*.md and knowledge/runbooks/*.md (YAML front matter + markdown body)
- platforms/*.yaml (platform profiles), environments/*/topology.yaml (component graphs)
- data/scenarios/*/ (problem.md, logs/, expected.json)

Build the data and knowledge layer. No agents, no graph, no UI yet.

1. flowmedic/graph/state.py: Pydantic models used by later steps.
   - Category (enum from categories.yaml codes), Severity (P1-P4), Route ("known_fix" | "similar" | "new_issue" | "clarify"), StepKind ("read" | "change" | "destructive"), Source ("verified" | "cited" | "model").
   - TriageContext: platform, component, version, os, environment, start_time, scope, recent_changes (all optional) + missing_slots(profile) -> list[str].
   - Evidence: source_file, line_no, text (masked), signature (optional).
   - KBMatch: doc_id, doc_type ("incident" | "runbook"), title, score, signature_hits, vector_score.
   - TriageResult: category, secondary_categories, severity, root_causes (ranked list of {id, confidence, evidence_refs}), route, kb_matches, related_components, first_steps (list of PlanStep), confidence, notes.
   - PlanStep: n, title, kind (StepKind), command_or_action, where (component), expected_output, risk, rollback, source (Source), source_ref.
   Keep them small and documented; later steps may extend them.

2. flowmedic/knowledge/loaders.py (new package flowmedic/knowledge/):
   - load_categories(), load_root_causes(), load_profile(platform_id), load_topology(environment).
   - load_documents(): parse every incident and runbook markdown into a KnowledgeDoc (front matter fields + body text). Validate that every root_causes ID and category exists in the YAML vocabularies; fail with a clear message if not.
   - load_scenario(case_id) and list_scenarios(): problem text, log files, expected.json as a Scenario model.
   All paths resolve from the repo root via pathlib (not the current working directory).

3. flowmedic/tools/topology.py: dependencies(env, component_id) (hard first, then soft), callers(env, component_id), related_checks(env, component_id) returning an ordered list: dependencies first, then callers. Pure Python, no LLM.

4. flowmedic/tools/parsers/: plain Python, no LLM.
   - signatures.py: extract error signatures from log text using the regex patterns in the platform profile, plus ORA-xxxxx codes and Java exception class names. Normalize webMethods codes so "ART.0118.5053E" and "ART.118.5053" match (strip leading zeros in each numeric group and the trailing severity letter). Return per signature: count, first_seen, last_seen, sample line.
   - jstack.py: summarize a thread dump or the threaddump-summary.txt format into counts by top frame and by client IP.
   - vmstat.py (vmstat/free/uptime text -> load, swap used, si/so), ss.py (connection counts per target).
   - redact.py (in flowmedic/tools/): mask secrets before any text reaches a model: password=..., Authorization: Basic/Bearer values, tokens, private keys. Also flag instruction-like lines aimed at an AI (for example "ignore previous instructions", "NOTE TO AI") as suspicious and return them separately. Test it on data/scenarios/SC-009.

5. flowmedic/tools/knowledge_repo.py: hybrid search.
   - A VectorStore interface with two backends chosen by VECTOR_BACKEND: PineconeStore (Pinecone serverless index PINECONE_INDEX; embeddings with Pinecone's hosted inference model, configurable via EMBED_MODEL in config, default "multilingual-e5-large"; create the index if missing) and ChromaStore (local persistent folder chroma_data/, Chroma's default local embedding, no API key).
   - knowledge/ingest.py CLI: "uv run python -m flowmedic.knowledge.ingest" embeds incidents and runbooks (one vector per document: title + symptoms/signals + root cause text) with metadata (doc_id, doc_type, platform, category, versions, components). Idempotent (upsert by doc_id).
   - search(query_text, signatures, platform, version=None, k=5) -> list[KBMatch]: vector score from the store, plus exact signature overlap computed in Python over the loaded documents (normalized codes). Final score = 0.6 * vector + 0.4 * signature_overlap, filtered to the platform. Put the weights and the route thresholds in config: KB_KNOWN_FIX=0.80, KB_SIMILAR=0.60.
   - route_for(matches) -> Route using those thresholds (known_fix needs score >= 0.80 AND a signature or category match).
   - Add EMBED_MODEL, KB_KNOWN_FIX, KB_SIMILAR to config.py and .env.example. Add pinecone and chromadb dependencies.

6. Tests (no network): loaders validate all current content; topology walk for is-cluster returns tsa, um, is-db before backends and lists api-gw and digital-gw as callers; signature extraction finds ART.118.5053 in SC-001 and ORA-01653 in SC-002; redact masks the password and Basic header in SC-009 and flags the injection line; search and route_for work with an in-memory fake VectorStore. One @pytest.mark.live test that ingests and searches the real backend.

7. A small CLI for me to check results: "uv run python -m flowmedic.knowledge.try_search SC-001" loads the scenario, extracts signatures from its logs, searches, and prints the top 3 matches with scores and the route.

8. Update docs/progress.md (Step 2 done, how to run) and README.md (ingest command).

When finished, run and show me the output:
- uv run ruff check .
- uv run pytest
- uv run python -m flowmedic.knowledge.ingest
- uv run python -m flowmedic.knowledge.try_search SC-001
- uv run python -m flowmedic.knowledge.try_search SC-007
