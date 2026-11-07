# Step 5c (only if time allows): design critique and polish

Paste below the line into the same Codex chat as Step 5b (or a new one), with the API and UI running and an SC-001 incident open in the planner stage.

---

**Budget (from AGENTS.md):** 45 minutes of work at most. Offline tests with fake models first; live checks at most 2 attempts each, one at a time. If a check still fails after 2 fixes, stop and report. Stay in scope.

Use $impeccable. Run a critique of the war-room screen in two states: (1) triage stage with the TopologyMap animating, (2) planner stage after the hand-off. Then:
1. Apply polish on the top issues it finds (spacing rhythm, type hierarchy, contrast, alignment of badges and tags, density of the timeline).
2. Apply animate only to these moments: triage → planner hand-off, step status change, topology check order. Remove any motion that does not carry meaning.
3. Re-run "npx impeccable detect app/web/src" and the build.
List what you changed and why in docs/progress.md under "UI polish".
