# FlowMedic Design Specification

FlowMedic is an incident war room for integration and platform engineers. People open it while production is broken, so it must feel calm, precise and fast. It must not look like a generic AI app: no purple-blue gradients, no glassmorphism everywhere, no rows of identical gray cards, no Inter, no chat bubbles as the main layout.

## Principles
1. **Signal over decoration.** Color and motion only carry meaning: severity, state change, agent hand-off, what to check next.
2. **One place to act.** Every question, approval and step result is entered in ONE pinned "Your turn" card in the centre column, with explicit buttons, never a line of chat text. Side panels never hold input controls.
3. **Evidence is always one click away.** Every claim (root cause, step) links to the log lines, incident or doc behind it.
4. **Trust is visible.** Every step shows its source: Verified (knowledge repo), Cited (vendor doc), Model (lowest trust).
5. **Nothing runs by itself.** The UI never suggests the agent executed anything. The engineer runs commands and reports results.
6. **Always say where you are and what happens next.** A stage tracker shows the stage, the agent at work and what it is doing; when the engineer must act, the UI says so in one sentence and shows the single control needed. The user should never wonder "is it stuck?".
7. **Plain language first, detail on demand.** Show the story an engineer understands ("Triage finished: P1, JDBC pool exhausted"); keep internal node and tool names behind "Show agent activity". Every panel and tab has a one-line description of what it is for.

## Theme: dark first
| Token | Value | Use |
| --- | --- | --- |
| `--canvas` | `#0B0D10` | App background |
| `--surface` | `#111418` | Panels |
| `--raised` | `#171B21` | Cards inside panels, inputs |
| `--overlay` | `#1E232B` | Popovers, menus, hover rows |
| `--border` | `#252B33` | 1px hairlines |
| `--border-strong` | `#323A45` | Focused or active outlines |
| `--text` | `#E6E8EB` | Primary text |
| `--text-muted` | `#8A94A3` | Secondary text, labels |
| `--text-faint` | `#5B6573` | Timestamps, hints |
| `--accent` | `#3DD9C1` | "Pulse": the one brand accent (active step, focus ring, Verified badge, live activity) |
| `--accent-dim` | `rgba(61,217,193,0.12)` | Accent backgrounds |

Status colors (only for meaning, never decoration):
| Meaning | Color |
| --- | --- |
| P1 / destructive / failed | `#F0524F` |
| P2 / state-changing step / warning | `#F2A93B` |
| P3 | `#D9C45C` |
| P4 / read-only / neutral | `#7C8A9A` |
| Cited source | `#7AA7FF` |
| Model-knowledge source | neutral text with a dashed `--border-strong` outline (deliberately weaker) |
| Success / resolved | `#3DD9C1` (same as accent) |

Light theme is optional and comes later; build tokens so it can be added.

## Typography
- UI: **Geist Sans** (npm `geist`). Weights 400, 500, 600 only.
- Logs, commands, error codes, IDs: **JetBrains Mono**, ligatures off.
- Scale (px): 12 labels and badges, 13 dense tables and logs, 14 body, 16 card titles, 20 panel titles, 28 empty-state title only.
- Numbers in tables and metrics use tabular figures.

## Shape and spacing
- Radius: 6px controls, 8px cards and panels. Never above 8px. Pills only for badges.
- Spacing on a 4px grid; panels padded 16px; cards 12–16px.
- Borders, not shadows. A single soft shadow is allowed only for floating overlays (menus, dialogs).

## Layout (desktop, ≥1280px wide)
- **Top of the app:** app bar with the FlowMedic mark, the current page title, and a "?" button that opens "How FlowMedic works".
- **Left rail (264px):** navigation first (War room · Setup · Knowledge), then "New incident" and the incident list. Each incident row: severity pill, title, environment, and a plain stage label ("Diagnosing", "Fixing · step 3 of 8", "Waiting for you", "Closed").
- **Centre (flexible), the only place the engineer acts:**
  1. **Stage tracker** (sticky, top): Report → Logs → Diagnose → Fix → Close. Current stage highlighted; under it one line: active agent ("Triage agent" or "Planner agent") and what it is doing now, or "Waiting for you: <what>".
  2. **Story so far:** plain-English milestones grouped by stage (report received, logs approved, diagnosis, hand-off "Triage agent handed over to Planner agent", each finished step with its result, re-plans "Plan revised: new evidence (SID 1412)"). Technical rows are collapsed under "Show agent activity (N)".
  3. **Your turn card** (pinned at the bottom of the centre column, accent border): the single thing the engineer must do now (answer a question, approve log access, run step N and paste the result, approve saving). When the agent is working instead, it shows a quiet "Agent working: <what>" line.
- **Right panel (440px), reference only, as tabs:** Diagnosis · Plan · Topology · Evidence. Each tab starts with a one-line description. The panel switches to Plan automatically at the hand-off and keeps the active step in view; the Plan tab mirrors the active step read-only with "Act in the Your turn card" pointing left.
- **Setup page:** platforms, environments and knowledge loaded from the repo, each card naming its source file, plus "How to add a platform" and "How to add an environment" guides. Read-only in the UI.
- **Knowledge page:** searchable list of incidents and runbooks (id, title, platform, category, verified), opening in the evidence viewer.
- Below 1024px the right panel becomes a drawer. Mobile is out of scope.

## Key components
- **SeverityPill, CategoryTag, SourceBadge (Verified / Cited / Model), StepKindTag ([read] neutral, [change] amber, [destructive] red).**
- **ActionCard:** title, one-line reason, the structured inputs (chips for allowed values, folder + time window for log access), primary and secondary buttons. Accent left border while waiting.
- **TriageCard:** category, severity, route (Known fix / Similar / New issue), top root causes with confidence bars and evidence links, top knowledge match with "Open INC-003", related components.
- **TopologyMap:** layered SVG (consumers → gateways → integration servers → dependencies). Affected component pulses (accent ring). Dependencies to check light up in check order. Healthy nodes stay quiet.
- **StageTracker:** five steps with the active one in accent; done steps show a check; the line beneath names the agent and its current action, or what the engineer must do.
- **YourTurnCard:** pinned action area in the centre; title ("Your turn: step 3 of 8"), one sentence on what to do and why, the command with copy button, expected result, the input, and the buttons. Change steps also show risk and rollback and need the confirmation tick.
- **HelpOverlay ("How FlowMedic works"):** 4 numbered steps with one sentence each; shown on the empty war room and from the "?" button.
- **PlanStepper:** numbered steps; each shows kind tag, where (component), the command in a mono block with a copy button, expected output, risk and rollback for change steps, a "paste output" box, and Done / Skipped / Failed buttons. The active step carries an accent border beam.
- **LogViewer:** sticky file header, line numbers, matched signatures highlighted, masked secrets shown as `••••` chips, flagged injection lines in their own red strip with "Ignored: instruction-like text in log".

## Motion
- Library: Motion (Framer Motion). Respect `prefers-reduced-motion` everywhere (fall back to instant or fade).
- Springs for layout: `{ type: "spring", stiffness: 380, damping: 32 }`. Fades 160–220 ms, ease-out.
- Triage → Planner hand-off: shared `layoutId` on the Triage card; an animated beam travels from the Triage section to the Planner section once.
- Topology: dependency highlights stagger 120 ms in check order.
- Activity rows slide in 8px from below; no bouncing.
- No infinite animations except one slow pulse (2.4 s) on the affected component and the live-activity dot.

## Anti-patterns (never)
- Purple or blue-to-purple gradients, neon glows, glass blur on every surface.
- Inter or system-ui as the visible UI font.
- Nested cards inside cards inside cards.
- Gray text on colored backgrounds; text below 4.5:1 contrast.
- Emoji as icons. Use Lucide only, 1.5px stroke, 16px default.
- Spinners where a progress row with the current node name would say more.
- Plain text links for critical actions.
