# FlowMedic — Product Context

**One line:** Diagnose the break. Guide the fix. A read-only, two-agent triage assistant for integration-platform incidents.

**Users:** integration engineers and platform/operations engineers who keep an ESB, API gateway or messaging layer running (webMethods first, Kong as a second profile). Often under pressure, during an outage, on a laptop.

**Jobs to be done:**
1. Describe a problem, attach or grant access to logs, and get a categorized diagnosis with evidence in minutes.
2. Follow a step-by-step plan, run each command themselves, paste the output, and get the next step.
3. Save a resolved incident so the next person gets the fix instantly.

**What makes it trustworthy:** read-only by design; explicit approvals for log access and saves; every step labeled Verified, Cited or Model; injection text in logs is shown as ignored.

**Primary screen:** the incident war room (left: incidents; centre: timeline with action cards; right: triage card + topology map, then the plan stepper).

**Tone:** calm, precise, engineering-grade. Short labels. No marketing copy inside the app.

<!-- impeccable:product-schema 1 -->

## Platform

web

## Operating Context

- The planned web interface runs against the local HTTP API from Step 5a; the UI is the next implementation step, in `app/web/`.
- The engineer selects an environment, supplies a problem and log exports, approves log access, answers clarification questions, and reports each manually executed step's result.
- Incident checkpoints persist locally. Environment memory retains confirmed context but does not authorize future log access.
- The current local API supports one server worker and one active event stream per incident. A paused stream is not a completed incident.

## Capabilities and Constraints

- The assistant never executes remediation commands or writes to remote servers. Knowledge saves require explicit human approval.
- Diagnostic secrets are masked; instruction-like log content is quarantined rather than treated as instructions.
- Missing reviewed topology is an evidence gap. A completed engineer check does not independently prove a component is healthy.
- Product code must support Windows and macOS; Windows runtime behavior has not yet been exercised.
- The current interface scope is desktop and laptop web use; mobile is out of scope, and a light theme is deferred, as specified in DESIGN.md.

## Evidence on Hand

- `data/scenarios/` contains synthetic, anonymized problem reports, log exports and expected labels for development demonstrations and evaluation.
- `knowledge/incidents/` and `knowledge/runbooks/` supply existing incident and runbook content. Demo results are development evidence, not held-out validation or proof of remediation efficacy.
- `docs/prompts/step-05b-ui.md` records the planned UI scope and stack. `DESIGN.md` remains the visual source of truth.

## Accessibility & Inclusion

- Respect reduced-motion preferences throughout the interface and maintain text contrast of at least 4.5:1, as required by DESIGN.md.
