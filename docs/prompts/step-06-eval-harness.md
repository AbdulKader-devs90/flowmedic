# Step 6 (Week 4): evaluation harness for the Triage agent

Paste below the line into a NEW Codex chat (GPT-6.1 Sol, Medium, Full access).

---

**Budget:** 60 minutes of work at most. Build and test offline with fake models first. Live checks: at most 2 golden cases, one at a time, at most 2 attempts. Do NOT run the full 40-case evaluation; the engineer runs the baseline. If a check still fails after 2 fixes, stop and report. Stay in scope: no changes to agent prompts, routing thresholds or graph behaviour in this step (that would invalidate the baseline).

Read `docs/week4-eval-plan.md` (the spec for metrics and scoring) and `data/golden/README.md` first.

1. **Dataset loader.** Read `data/golden/golden-v1.json` (40 case IDs) and each case's `data/scenarios/<ID>/` with the existing loaders. Case inputs given to the agent: `problem.md`, logs (after the normal approval path) and `environment` only. Expected labels must never reach the agent.

2. **Non-interactive triage runner** (`flowmedic/evals/runner.py`): run the existing Triage graph for one case, reusing the code path of `flowmedic.agents.triage.run`:
   - approve log access for the scenario's own log folder (full window);
   - answer clarifying questions from `expected.json` → `engineer_answers` (slot → value; unknown slots get "unknown"), and record which slots were asked;
   - capture: triage result (category, secondary, severity, root causes with confidence, route, KB matches with ids and scores, first steps with kind/where/source/risk/rollback), notes, quarantined flags, all text shown to the engineer, number of model calls, wall-clock seconds, and token usage per model where the response metadata provides it;
   - never execute anything; use an in-memory checkpointer; a per-case timeout (default 300 s) records a timeout result instead of hanging.

3. **Scorers** (`flowmedic/evals/scorers.py`, pure functions, unit-tested): exactly the rules in the plan: `category_match`, `route_match`, `root_cause_recall` (None when the expected list is empty), `kb_hit_at_3` (None when no expected ids), `clarify_ok` (None when not needed), `mention_coverage`, `safety` (pass/fail plus the list of reasons; secrets = credential values present in that case's raw logs, e.g. password=, Authorization headers, JDBC passwords), and `latency_s`. Make matching for mentions case-insensitive and tolerant of plurals/hyphens.

4. **LLM judge** (`flowmedic/evals/judge.py`): first-step quality PASS/FAIL with a one-sentence reason per rubric item, using structured output. Model is a setting `JUDGE_PROVIDER`/`JUDGE_MODEL` (default: the alt role, GLM-5.3). Judge prompt versioned like the other prompts (`JUDGE_V1`). Inputs: problem, masked evidence summary, expected labels, agent first steps.

5. **Human calibration helper:** `uv run python -m flowmedic.evals.calibrate export` writes `evals/human_labels.csv` for 10 fixed cases (mix of types) with the agent's first steps, the judge verdict and an empty `human_verdict` column; `... calibrate score` reports judge-human agreement and lists disagreements.

6. **LangSmith integration** (`flowmedic/evals/run.py`, CLI):
   - `uv run python -m flowmedic.evals.run --upload-dataset` creates or updates dataset `flowmedic-golden-v1` (inputs: case_id, problem, environment, scenario_type; outputs: the expected labels) and tags it `golden-v1`.
   - `uv run python -m flowmedic.evals.run --experiment baseline-v1 [--cases GC-01,SC-001] [--concurrency 1] [--no-judge] [--local]` runs the target over the dataset with the scorers and judge as evaluators via the LangSmith evaluate API, project `flowmedic-eval`, experiment metadata: prompt_version, agent_version, models per role, dataset version, git commit. Each case trace carries case_id and scenario_type. Tracing is switched on only for this process; if LangSmith is unreachable, `--local` (or an automatic fallback with a warning) still runs and writes results.
   - Always write `evals/results/<experiment>.csv` (one row per case: id, type, inputs summary, expected vs predicted labels, every score, judge verdict and reasons, latency, model calls, tokens, estimated cost, error) and `evals/results/<experiment>-summary.md` (each metric vs its pass bar, by scenario type, p50/p95 latency, total cost).
   - Cost: tokens × price per million from settings `PRICE_<ROLE>_INPUT` / `PRICE_<ROLE>_OUTPUT` (default 0, documented in `.env.example`; do not invent prices).
   - `uv run python -m flowmedic.evals.compare baseline-v1 fix1-...` prints a per-metric delta table and lists per-case wins and regressions.

7. **Small UI fix:** the demo scenario lists (home and New incident dialog) show only scenarios whose `expected.json` has `"demo": true`; golden cases stay hidden from the UI.

8. **Tests and docs:** offline pytest for loader, scorers (including safety edge cases from SC-009 and GC-28), runner with fake models, CSV/summary writing and compare. Add an "Evaluation" section to `docs/REFERENCE.md` and a short line in README "More documentation". Live check at the end: `--cases GC-01 --no-judge --local`, then `--cases GC-01` with the judge (2 cases max in total).

Checks, once at the end: `uv run ruff check . ; uv run pytest -q -m "not live" ; npm --prefix app/web run build`. Add a "Step 6: evaluation harness" section to docs/progress.md. Reply with the commands the engineer should run for the baseline and the check results.
