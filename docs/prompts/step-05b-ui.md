# Step 5b: React war-room UI (shadcn/ui + Motion + Lucide), guided by Impeccable

## Before pasting (you, about 10 minutes)
1. Node: `node -v` must print v20 or newer. If not: `brew install node`.
2. Install the Impeccable design skill for Codex, from the repo root:
   `npx impeccable install` → choose Codex. Then in Codex open `/hooks` and approve the project hook, and check that `$impeccable` appears (restart the Codex panel if not). Review what it added before committing.
3. In Codex run `/impeccable init`. When it asks, tell it: "PRODUCT.md and DESIGN.md already exist at the repo root. Keep them as the source of truth and only add what is missing."
4. Commit: `git add -A && git commit -m "Add Impeccable design skill and design spec" && git push`

Then paste below the line into a NEW Codex chat (GPT-6.1 Sol, Medium, Full access).

---

Use $impeccable for this task. Read AGENTS.md, PRODUCT.md, DESIGN.md (the design source of truth: tokens, fonts, layout, components, motion, anti-patterns) and docs/progress.md. The API from Step 5a is running at http://localhost:8000 (see flowmedic/api/app.py for the exact contracts).

Build the FlowMedic war-room UI in app/web/.

1. Stack: Vite + React + TypeScript (strict), Tailwind CSS, shadcn/ui (Radix) for primitives, Motion (framer-motion) for all animation, lucide-react icons, @tanstack/react-query for fetching, a small typed SSE hook for /events. Fonts: Geist Sans (npm "geist") and JetBrains Mono. From Magic UI add only Animated Beam, Border Beam and Number Ticker (via the shadcn registry). No other UI kits. Map every DESIGN.md token to CSS variables and the Tailwind theme; no raw hex values in components.
2. Screens and components exactly as DESIGN.md describes:
   - App shell: left IncidentRail, centre Timeline, right panel that switches between Triage stage (TriageCard + TopologyMap) and Planner stage (compact Triage header + PlanStepper), EvidenceDrawer over the right panel.
   - New incident dialog: paste the problem, pick environment, attach log files, or "Load demo scenario" (from /api/scenarios). Also opened with ⌘K via a shadcn Command menu (New incident, Load scenario, Open knowledge doc).
   - ActionCards for every interrupt type: clarifying question (chips for allowed values + free text), log access (folder, time window, Approve / Deny), step result (pasted output + Done / Skipped / Failed), save approval (incident record preview + Save / Discard). Answers POST to /resume and the timeline continues from /events.
   - Agent activity rows from SSE events, compact and readable (node name in plain words, short summary, tool target). No spinners; show the current node with a small live dot.
   - TriageCard with SeverityPill, CategoryTag, route badge, root causes with confidence bars and evidence links that open the EvidenceDrawer at the right line, top knowledge match ("Open INC-003" opens the doc in the drawer), related components.
   - TopologyMap: layered SVG built from /api/environments/{env}/topology. Affected node pulses; check_next nodes light up in order with a 120 ms stagger; Animated Beam along the edge currently being checked; statuses update as the plan advances.
   - PlanStepper: steps with StepKindTag, where, command in a mono block with copy button, expected output, risk + rollback on change steps, SourceBadge, paste-output box, status buttons; Border Beam on the active step.
   - LogViewer in the EvidenceDrawer: sticky header, line numbers, highlighted signatures, masked secrets as chips, flagged lines in a separate red strip labelled "Ignored: instruction-like text in log".
   - Hand-off: when the stage changes to planner, the TriageCard morphs into the compact header via a shared layoutId, and one Animated Beam runs from the triage area to the plan.
3. Motion rules from DESIGN.md (springs, durations, stagger, the single slow pulse). Respect prefers-reduced-motion.
4. Empty state: no hero banner. A quiet panel: "No active incident", the ⌘K hint, and the demo scenarios as a short list.
5. Dev proxy /api -> http://localhost:8000. "npm run build" outputs to app/web/dist, which the API already serves.
6. Quality gates: TypeScript strict with no errors, eslint clean, "npm run build" succeeds, and "npx impeccable detect app/web/src" reports no high-severity findings (fix what it reports, or explain any you leave).
7. Update README.md (how to run UI + API) and docs/progress.md.

Run and show: npm --prefix app/web run build ; npm --prefix app/web run lint ; npx impeccable detect app/web/src
Then tell me the two commands to run it (API and UI dev server) so I can walk through SC-001 in the browser.
