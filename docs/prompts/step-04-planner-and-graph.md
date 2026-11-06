# Step 4: Triage fixes, Planner Agent, parent graph, memory, engineer simulator

Paste below the line into a NEW Codex chat (GPT-6.1 Sol, Medium, Full access) after Step 3 is committed.

---

Read AGENTS.md, docs/progress.md, docs/step-03-validation.txt and docs/PROJECT_PLAN.md ("Architecture", "Tools, memory, approvals and failure handling", "Platform topology"). Steps 1-3 are done. Reuse existing code; keep all current tests passing.

A. Triage fixes (from the Step 3 review)
1. Node order: intake -> request log access -> evidence -> clarify -> classify -> kb_search -> route -> synthesize. Clarify asks only for slots still missing after inferring from the approved logs (signature patterns in each platform profile identify the platform and component) and from environment memory.
2. Environment: TriageContext.environment comes from the engineer, else environment memory, else DEFAULT_ENVIRONMENT in config (default "sample-prod"; for platform kong use the profile's default_environment "kong-sample" - add default_environment to platforms/*.yaml). Add --environment to the CLI. When a scenario is run, its expected.json "environment" value is used as the engineer-selected environment (this is UI context, not a label). Load the topology and fill related_components with topology.related_checks for the affected component.
3. Classify also returns affected_component, chosen only from the loaded topology's component ids (validate; repair once).
4. first_steps: at most 6. Take the best incident's resolution steps first, then non-duplicate steps from that incident's own linked runbooks only. Never pull steps from other matches.
5. Overall confidence: one documented formula in code, e.g. known_fix = 0.5*top_root_cause_conf + 0.5*kb_score; similar = 0.4*rc + 0.3*kb + 0.3*vendor_evidence; new_issue = 0.7*rc; clarify = min(rc, 0.4). Add unit tests.

B. Planner Agent (flowmedic/agents/planner/: graph.py, nodes.py, prompts.py)
1. build_plan: strong model, structured output -> ResolutionPlan of 5-10 PlanSteps built from the TriageResult. Each step: kind (read/change/destructive), where (topology component id), command_or_action, expected_output, decision rule ("if X, go to step N; if Y, re-triage"), source and source_ref carried from triage (verified/cited/model). For change/destructive steps, write risk and rollback specific to that step (no generic boilerplate; add a test that rejects the old boilerplate text). For OUTAGE or new_issue routes, order checks by topology dependencies first, then callers.
2. Step loop: present the current step with interrupt({"type": "step", ...}). The engineer answers {status: done|skipped|failed, output: text}. Change and destructive steps also need confirmed: true; the agent never claims it ran anything.
3. interpret: mask the pasted output with redact, run the Step 2 parsers on it, then the fast model with structured output decides: next | insert_steps | retriage | escalate | resolved, with a one-line reason. Retriage happens when the output shows evidence for a root cause not in the TriageResult (for example a blocking DB session). Max 2 re-triage rounds.
4. close: build an IncidentRecord (symptoms, signatures, root cause ids, steps that worked with their outputs summarized, version, os, environment, components). interrupt({"type": "approve_save"}). On approval, save_incident writes knowledge/incidents/<NEXT-ID>.md in the same front-matter format (verified: true, source: "flowmedic session <date>") and upserts that single document into the vector store. On reject, keep it only in state. For escalate, also draft a vendor support case text (problem, versions, evidence, steps tried).

C. Parent graph (flowmedic/graph/main_graph.py)
- START -> triage subgraph -> planner subgraph; planner can hand back to triage with Command(goto=...) carrying the new evidence; triage then returns to planner with the updated result. -> close -> END.
- SQLite checkpointer (langgraph-checkpoint-sqlite) at runs/checkpoints.sqlite; thread_id = incident id (for scenarios: "<case_id>-<timestamp>").
- Stream custom progress events from nodes with get_stream_writer (node, short summary) for the UI later.
- One trace per incident in LangSmith (run_config with case_id, prompt versions, agent_version, run_name="incident").

D. Environment memory
- A small store (LangGraph SqliteStore if available, otherwise a JSON file under runs/) keyed by environment: platform, version, os, log roots, last updated. Triage reads it to avoid repeat questions and writes back confirmed answers.

E. Engineer simulator and CLI
- data/scenarios/<id>/step_outputs.yaml exists for SC-001, SC-008 and KONG-SC-01 (format: list of {match: [keywords], status, output} plus a default). Write flowmedic/sim/engineer.py that answers step interrupts by matching keywords against the step text (all keywords, case-insensitive, first match wins).
- New CLI "uv run python -m flowmedic.run <case_id>" runs the full parent graph. Interactive by default. Flags: --answer k=v (repeatable), --approve-logs, --auto (use answers + approve logs + engineer simulator for steps + confirm change steps), --approve-save (default is to reject the save so demos do not change the knowledge repo), --environment.
- It prints a compact transcript: triage summary, each plan step with the simulated output and the planner's decision, any re-triage, and the final incident record. Saves runs/<case_id>-full.json.

F. Tests (no network; fake models): new node order and slot inference; environment default and topology related_components; first_steps cap and runbook scope; confidence formula; plan steps carry specific risk/rollback; interpret decides retriage on a blocking-session output; re-triage cap; approve_save writes a file only when approved (use a temp knowledge dir); simulator keyword matching. One live end-to-end test marked @pytest.mark.live.

G. Update docs/progress.md and README.md.

Run and show (save the full output to docs/step-04-validation.txt):
- uv run ruff check . ; uv run pytest
- uv run python -m flowmedic.run SC-001 --auto --answer version=10.15
- uv run python -m flowmedic.run SC-008 --auto
- uv run python -m flowmedic.run KONG-SC-01 --auto
Expected: SC-001 resolves through the plan; SC-008 re-triages once after the blocking-session output and adds db_blocking_lock; KONG-SC-01 runs on the Kong profile and topology.
