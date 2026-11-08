# Step 5c-1: guided flow (one place to act, stage tracker, plain story, tabs)

Why: in the live SC-001 walkthrough the engineer could not tell what each panel meant, where to act, or whether the app was stuck (actions were split between the centre and the right panel, the timeline showed internal node names, and the plan panel stayed on an old step after a re-plan). DESIGN.md (Principles 2, 6, 7; Layout; StageTracker, YourTurnCard) now describes the target. This step restructures the war room around it.

Paste below the line into a NEW Codex chat (GPT-6.1 Sol, Medium, Full access). No servers need to run.

---

**Budget:** 60 minutes of work at most (larger than usual; this is a restructure). Offline only: fake API and the existing Playwright spec, run once at the end, no exploratory browser sessions, no live model calls. If a check still fails after 2 fixes, stop and report. If you reach 50 minutes, stop, write status to docs/progress.md, and report. Stay in scope: no new backend features in this step.

Read DESIGN.md and PRODUCT.md first; DESIGN.md "Layout" is the spec for this step. Use $impeccable for layout decisions, but do not spend time on visual polish (that is Step 5d).

1. **Refactor first, no behaviour change.** `app/web/src/App.tsx` and the components are packed into very long single lines. Split into readable components, one per region: `AppShell`, `LeftRail`, `StageTracker`, `StoryTimeline`, `YourTurnCard`, `InspectorTabs` (with `DiagnosisTab`, `PlanTab`, `TopologyTab`, `EvidenceTab`), and keep the existing hooks and API client. Normal formatting, one JSX element per line where reasonable. Build and lint must pass before you continue.

2. **Stage model** (`lib/stage.ts`, pure functions, derived from the snapshot plus the live stream so it survives a page refresh):
   - Stages: Report → Logs → Diagnose → Fix → Close.
   - Active agent: "Triage agent" during Report/Logs/Diagnose, "Planner agent" during Fix, none when closed.
   - Status line: either "<Agent> is <doing what>" in plain words (map node names: intake → "reading the incident report", request_log_access → "asking for log access", evidence/grep → "searching the logs", kb_search → "searching the knowledge base", classify → "assessing root causes", synthesize → "writing the diagnosis", build_plan → "building the resolution plan", interpret → "reviewing your result", close → "preparing the incident record"), or "Waiting for you: <what>" when an interrupt is open.
   - Plan progress: "step N of M".

3. **StageTracker** (sticky at the top of the centre column): the five stages, done ones with a check, the current one in accent, and the status line beneath it. Each stage has a tooltip explaining it in one sentence.

4. **YourTurnCard: one place to act.** Move every interrupt UI (clarifying question, log-access approval, step result, save approval) into one card pinned at the bottom of the centre column.
   - Title says exactly what to do: "Your turn: answer one question", "Your turn: approve read-only log access", "Your turn: run step 3 of 8 and report the result", "Your turn: save this incident to the knowledge base?".
   - One sentence on why, then the inputs and buttons. For steps: where (component), command with copy button, expected result, risk and rollback for change steps (with the existing confirmation tick), paste box, Done / Skipped / Failed. Add a short helper under the buttons: "Done = it worked as expected. Failed = it did not. Skipped = not applicable here."
   - After submitting: the card shows "Sent. The Planner agent is reviewing your result…" until the next interrupt arrives. While the agent works with nothing for the user to do, the card collapses to a quiet "Agent working: <status line>" row.
   - Remove all input controls from the right panel. Remove the "The active step and result controls are in the plan panel" text.

5. **StoryTimeline: plain story, detail on demand.**
   - Show milestones in plain English, grouped under stage headings: "Incident report received", "Log access approved (folder, time window)", "Diagnosis ready: P1 · JDBC pool exhausted · known fix INC-003", "Triage agent handed over to Planner agent", "Step 2 done: Inspect thread dump" (with a one-line result excerpt), "Plan revised after new evidence" (with the reason when the state has one, for example the new root cause), "Incident closed: resolved".
   - Derive milestones from the snapshot (triage result, plan step statuses, closed state) as well as the stream, so a refresh still shows the story.
   - Put the existing technical activity rows under a collapsed "Show agent activity (N)". Collapse start/finish pairs into one row per node run (pulse icon, then check). Tool rows stay separate. Use plain labels ("Knowledge search", "Search logs", "Read environment memory"), and keep acronyms upper case (JDBC, IS, UM, DB, SID, API, TX).

6. **InspectorTabs** (right panel, reference only): tabs Diagnosis · Plan · Topology · Evidence, each starting with a one-line description:
   - Diagnosis: "What the Triage agent concluded and why."
   - Plan: "The Planner agent's step-by-step fix. You act in the Your turn card."
   - Topology: "Your environment's dependencies. Highlighted nodes are affected or next to check."
   - Evidence: "Log lines and knowledge documents behind each claim."

   Behaviour:
   - Switch to Plan automatically at the hand-off and after a re-plan, and scroll the active step into view (respect reduced motion).
   - The active step shows "Awaiting your result · act in the Your turn card ←".
   - After a re-plan, show the banner "Plan revised after new evidence" above the steps.
   - Before diagnosis exists, each tab shows a helpful empty state saying when it will fill.

7. **Left rail.** Navigation at the top: War room (active) · Setup · Knowledge. Setup and Knowledge can be placeholder pages saying "Coming in the next step" (Step 5c-2 builds them). Incident rows show a plain stage label from the stage model: "Diagnosing", "Waiting for you", "Fixing · step 3 of 8", "Closed".

8. **Empty war room.** Above the demo scenarios, add "How FlowMedic works" with 4 numbered steps, one sentence each:
   1. Describe the incident or load a demo.
   2. Approve read-only access to the logs.
   3. The Triage agent diagnoses and the Planner agent builds a step-by-step fix.
   4. You run each step and report back; FlowMedic adapts the plan and records what worked.

   Add a "?" button in the app bar that reopens this as a dialog.

Checks, run once at the end:
```
npm --prefix app/web run build ; npm --prefix app/web run lint ; npx impeccable detect app/web/src ; npx --prefix app/web playwright test ; uv run pytest -q -m "not live"
```
Update the Playwright spec to the new layout: the Your turn card holds the step controls, and the Plan tab opens at the hand-off. Add a "Step 5c-1: guided flow" section to docs/progress.md listing what was built, what was verified, and anything deferred. Reply with the check results.
