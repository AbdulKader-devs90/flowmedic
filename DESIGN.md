# FlowMedic Design Specification

FlowMedic is an incident war room for integration and platform engineers. People open it while production is broken, so it must feel calm, precise and fast. It must not look like a generic AI app: no purple-blue gradients, no glassmorphism everywhere, no rows of identical gray cards, no Inter, no chat bubbles as the main layout.

## Principles
1. **Signal over decoration.** Color and motion only carry meaning: severity, state change, agent hand-off, what to check next.
2. **One place to act.** Every question or approval from the agent is a distinct action card with explicit buttons, never a line of chat text.
3. **Evidence is always one click away.** Every claim (root cause, step) links to the log lines, incident or doc behind it.
4. **Trust is visible.** Every step shows its source: Verified (knowledge repo), Cited (vendor doc), Model (lowest trust).
5. **Nothing runs by itself.** The UI never suggests the agent executed anything. The engineer runs commands and reports results.

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
- **Left rail (264px):** incident list with severity pill, title, environment, age; "New incident" at the top; ⌘K hint.
- **Centre (flexible):** the incident timeline: engineer messages, compact agent activity rows ("Reading server.log · 3 signatures found"), and action cards (clarifying question, log-access request, step result, save approval).
- **Right panel (440px), changes with the stage:**
  - Triage stage: Triage card + Topology map.
  - Planner stage: the Triage card shrinks into a compact header (shared-element transition) and the Plan stepper fills the panel.
- **Evidence drawer:** slides over the right panel; log viewer with line numbers.
- Below 1024px the right panel becomes a drawer. Mobile is out of scope.

## Key components
- **SeverityPill, CategoryTag, SourceBadge (Verified / Cited / Model), StepKindTag ([read] neutral, [change] amber, [destructive] red).**
- **ActionCard:** title, one-line reason, the structured inputs (chips for allowed values, folder + time window for log access), primary and secondary buttons. Accent left border while waiting.
- **TriageCard:** category, severity, route (Known fix / Similar / New issue), top root causes with confidence bars and evidence links, top knowledge match with "Open INC-003", related components.
- **TopologyMap:** layered SVG (consumers → gateways → integration servers → dependencies). Affected component pulses (accent ring). Dependencies to check light up in check order. Healthy nodes stay quiet.
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
