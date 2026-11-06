# Step 3: read-only log reader (MCP), vendor-doc research, Triage Agent

Paste everything below the line into a NEW Codex chat (GPT-6.1 Sol, Medium, Full access), from the repo root, after Step 2 is committed.

---

Read AGENTS.md, docs/progress.md and docs/PROJECT_PLAN.md (sections "Architecture", "Platform topology", "Tools, memory, approvals and failure handling"). Steps 1 and 2 are done: config with per-role Nebius models, state models, loaders, parsers, redaction, topology walk and knowledge search exist. Reuse them; do not duplicate them.

Build three things in this step. No Planner Agent and no UI yet.

A. Read-only log reader as an MCP server (mcp_servers/log_reader/server.py)
1. Use the official Python MCP SDK (FastMCP). Tools, all read-only:
   - list_files(root) -> file names, sizes, modified times
   - grep(path, pattern, start_time=None, end_time=None, max_lines=200) -> matching lines with line numbers
   - tail(path, lines=200)
   - stats(path) -> line count, first and last timestamp
2. Safety, enforced in code: only paths under an allowlist of roots (a scenario's logs/ folder or folders listed in LOG_ROOTS in config) are readable; reject path traversal, symlinks that leave the root, and files over 50 MB; never open files for writing; every returned line passes through flowmedic/tools/redact.py first, and suspicious instruction-like lines are returned in a separate "flagged" list, never mixed into the text.
3. flowmedic/tools/log_client.py: a thin client the agents use. It calls the MCP server over stdio through langchain-mcp-adapters, and has an in-process mode (same functions, no subprocess) used by unit tests and as a fallback if the MCP process fails to start. Add the mcp and langchain-mcp-adapters dependencies.

B. Vendor-doc research (flowmedic/tools/vendor_docs.py)
1. search_vendor_docs(platform, version, signatures, problem_summary) uses Tavily (TAVILY_API_KEY, tavily-python) with include_domains from the platform profile's doc_sources.trusted; if fewer than 2 useful results, retry once on the open web. Build the query from the top signatures plus platform and version.
2. Then call the fast model with structured output to turn the results into VendorFindings: likely causes, ordered steps (each a PlanStep with kind read/change/destructive, source="cited", source_ref=url), and the list of urls used. Only use facts present in the results.
3. Failure handling: Tavily error or empty -> retry once with backoff -> fall back to the strong model's own knowledge, every step marked source="model", and a note suggesting a vendor support case.

C. Triage Agent (flowmedic/agents/triage/: graph.py, nodes.py, prompts.py, run.py)
A LangGraph StateGraph with a TriageState (extend graph/state.py as needed). Nodes in order:
1. intake: fast model with structured output extracts a TriageContext from the engineer's message (platform, component, version, os, environment, start_time, scope, recent_changes). Load the platform profile and, if the environment is known, its topology.
2. clarify: compute missing required slots from the profile (TriageContext.missing_slots). If any are missing, pause with LangGraph interrupt() carrying a structured question (slot names, allowed values from the profile, one short sentence why). Merge the answer and re-check. At most 2 rounds; after that continue and record the gap in notes.
3. evidence: if log files are available, first pause with interrupt() to request read access (which folder, which time window); on approval read them through log_client (signatures via the Step 2 parsers, thread dump / vmstat / ss summaries when those files exist). Keep Evidence items with file and line references. Flagged suspicious lines go into state.flags, never into a prompt as instructions.
4. classify: strong model with structured output -> category, secondary categories, severity, and up to 3 root causes chosen ONLY from knowledge/root_causes.yaml IDs (enforce with an enum/Literal or validate and repair once), each with confidence and evidence refs. Use topology.related_checks for the affected component to fill related_components (dependencies first, then callers).
5. kb_search: knowledge_repo.search with the problem summary and signatures, then route_for. If the category is UNKNOWN and evidence is thin, route = "clarify".
6. Branch on route:
   - known_fix: first_steps come from the best incident's "Resolution steps" (and its runbooks), source="verified", source_ref=doc id.
   - similar: show the candidate incident's steps AND run vendor research to confirm or adjust; mark which steps are verified and which are cited.
   - new_issue: vendor research only.
   - clarify: ask the engineer for the specific missing evidence (interrupt) and loop back to evidence once.
7. synthesize: produce the final TriageResult (category, severity, ranked root causes with evidence, route, kb matches, related components, first steps with source labels, confidence, notes, flags).

Rules for the whole graph:
- Prompts live in agents/triage/prompts.py as versioned constants (TRIAGE_INTAKE_V1, TRIAGE_CLASSIFY_V1, ...). Log text is passed inside clearly delimited blocks and the system prompt says it is untrusted data.
- Every step tagged change or destructive must have risk and rollback filled; the agent never claims it ran anything.
- Guards in state: count model calls per turn (cap MAX_LLM_CALLS=25 from config) and stop with a clear message when exceeded; tool errors retry once then become a recorded gap; invalid structured output is repaired once, then the node fails gracefully with a note.
- Compile with an InMemorySaver checkpointer for now (SQLite comes in Step 4). Every run uses run_config(case_id=..., prompt_version=..., run_name="triage") so LangSmith shows one trace per case with child runs for each node, model call and tool call.

D. CLI for me: "uv run python -m flowmedic.agents.triage.run SC-001"
- Loads the scenario (problem.md + logs folder), runs the graph, and at each interrupt prints the question and reads my answer from the terminal (for log access, "y" approves).
- Flags for non-interactive runs: --answer version=10.15 --answer os=linux --approve-logs
- Prints the TriageResult as readable text (category, severity, root causes, route, top KB match, related components, first steps with [read]/[change] and source labels, flags) and saves it as JSON to runs/<case_id>.json (add runs/ to .gitignore).

E. Tests (no network; fake LLMs returning fixed structured objects, fake search, fake Tavily):
- MCP reader rejects ../ traversal and paths outside the allowlist, and masks the SC-009 password.
- clarify interrupts for SC-001 (version missing) and does not for SC-002.
- route branches: known_fix uses incident steps with source="verified"; new_issue uses vendor steps with source="cited"; Tavily failure falls back to source="model".
- the SC-009 injection line ends up in flags and never inside a model prompt's instruction section.
- the call cap stops the graph cleanly.
Mark one end-to-end test with real models @pytest.mark.live.

F. Update docs/progress.md and README.md.

When finished, run and show me the output:
- uv run ruff check .
- uv run pytest
- uv run python -m flowmedic.agents.triage.run SC-001 --answer version=10.15 --approve-logs
- uv run python -m flowmedic.agents.triage.run SC-007 --answer version=10.15 --answer os=linux --approve-logs
- uv run python -m flowmedic.agents.triage.run SC-009 --approve-logs
