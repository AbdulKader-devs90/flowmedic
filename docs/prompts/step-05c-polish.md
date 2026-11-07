# Step 5c: UI fixes from the live SC-001 walkthrough, then light polish

Paste below the line into a NEW Codex chat (GPT-6.1 Sol, Medium, Full access). The API and UI do not need to be running: work with the existing fake-API tests.

---

**Budget (from AGENTS.md):** 45 minutes of work at most. Offline only: no live model runs, no Playwright browser exploration beyond the existing e2e spec. If a check still fails after 2 fixes, stop and report. Stay in scope: fix only the items below.

We walked SC-001 end to end in the browser on live models. It works. Fix these issues, found in that walkthrough, in priority order. Stop after item 7 if you reach 35 minutes.

1. **Re-plan visibility.** When the planner rebuilds the plan after new evidence (re-triage), the right panel stays scrolled to an old pending step, so the engineer thinks the UI is stuck. Fix: whenever the active step changes, scroll the inspector so the step marked "Awaiting your result" is in view (respect prefers-reduced-motion). After a re-plan, show a one-line banner above the plan: "Plan revised after new evidence" plus the reason, if the state has one.
2. **Duplicate timeline rows.** Each node currently produces a "started" row and a "finished" row with the same title ("Reading incident report", "Requesting log access" x3, "Present step", "Reviewing reported output"). Collapse them: one row per node run that switches from the pulse icon to the check icon when it finishes. Keep tool rows separate.
3. **Readable labels.** Map raw node and tool names to plain labels: "Read · sample-prod" becomes "Read environment memory · sample-prod", "Kb search" becomes "Knowledge search", "Grep" becomes "Search logs". Keep acronyms upper case: render root-cause titles like "JDBC pool exhausted", not "Jdbc pool exhausted" (JDBC, IS, UM, DB, SID, API, TX).
4. **No local paths in the UI.** Timeline rows and the log-approval card show absolute paths (/Users/...). Show paths relative to the repo (for example `data/scenarios/SC-001/logs/server.log`). The API may keep absolute paths internally; convert them for display only.
5. **Skip placeholder files.** The log reader greps `.gitkeep`. Exclude dotfiles and zero-byte files from log discovery (Python side, with a unit test).
6. **Approval card copy.** Replace "(null means the full export)" with "Leave times blank to read the full export."
7. **Topology map.** Edges must start and end at node centres (bottom centre to top centre), and all node labels use the same font size ("private-consumers" is smaller).
8. If time remains: use $impeccable for a quick critique of the planner state and apply at most 3 small polish fixes (spacing, alignment, contrast). Do not add new motion.

Checks, run once at the end: `npm --prefix app/web run build ; npm --prefix app/web run lint ; npx impeccable detect app/web/src ; uv run pytest -q -m "not live"`.
Add a "Step 5c: UI fixes" section to docs/progress.md listing each item as fixed or deferred. Reply with the check results.
