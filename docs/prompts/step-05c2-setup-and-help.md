# Step 5c-2: Setup and Knowledge pages, self-describing UI, walkthrough fixes

Why: the engineer could not see how FlowMedic is configured or how to add Kong (it already exists in the repo, but the UI never shows it). This step makes configuration visible and finishes the walkthrough fixes. Run it after Step 5c-1 is committed.

Paste below the line into a NEW Codex chat (GPT-6.1 Sol, Medium, Full access). No servers need to run.

---

**Budget:** 45 minutes of work at most. Offline only: fake API and the existing Playwright spec, run once at the end, no live model calls. If a check still fails after 2 fixes, stop and report. Stay in scope. Setup is READ-ONLY in the UI: nothing in this step writes configuration files.

Read DESIGN.md ("Setup page", "Knowledge page", Principles 6–7) first.

1. **Read-only API endpoints** (FastAPI, with pytest tests, reusing the existing loaders):
   - `GET /api/platforms`: per platform, return its id, name, versions, os, required/optional clarify slots, components (type, log files, number of error patterns, first 3 patterns), default environment, and source file (repo-relative, for example `platforms/kong.yaml`).
   - `GET /api/environments`: per environment, return its id, platform, node and edge counts, whether `architecture.png` exists, and source file.
   - `GET /api/knowledge`: list incidents and runbooks with id, type, title, platform, category, verified, and source file. Support `?q=` filtering on id and title.

2. **Setup page** (left rail → Setup). The page intro: "How FlowMedic is configured. Everything here comes from files in the repo; change the file, restart the API, and the change shows up here." Three sections:
   - **Platforms:** one card per platform (webMethods, Kong, Oracle, Linux, Windows). Each card shows versions, the questions the agent asks (clarify slots, in plain words), components with their log files and sample error patterns, and its knowledge count. The source file is shown as a mono chip.
   - **Environments:** one card per environment (sample-prod, kong-sample) showing platform, the topology preview (reuse the topology component), the architecture diagram if one exists, and the source file.
   - **Knowledge:** counts per platform and type, with a link to the Knowledge page.

   Add two expandable guides at the bottom, with Kong as the worked example.
   - **"How to add a platform":**
     1. Copy an existing file in `platforms/` (for example `kong.yaml`).
     2. Set the id, name, versions and os.
     3. List the clarify slots the agent must ask for.
     4. List the components with their log files and error patterns.
     5. Add incidents and runbooks under `knowledge/` with `platform: <id>`, then run the ingest command.
     6. Restart the API.
   - **"How to add an environment":**
     1. Create `environments/<name>/topology.yaml` (nodes with id, type, layer; edges with from, to, hard or soft dependency).
     2. Optionally add `architecture.png`, with no real IPs or hostnames.
     3. Set `default_environment` in the platform file if this environment should be the default.
     4. Restart the API.

   Take the exact ingest command and the YAML field names from the code; do not invent them. Put the same content in `docs/CONFIGURE.md` and link to it from README.md.

3. **Knowledge page** (left rail → Knowledge): a search box and a table (id, title, platform, category, type, Verified badge). Clicking a row opens the document in the existing evidence viewer. Page intro: "Past incidents and runbooks the Triage agent searches. New incidents are added here only after you approve saving them."

4. **New incident dialog, self-describing:**
   - Explain each field in a one-line hint.
   - The environment select shows each environment's platform ("kong-sample · Kong Gateway").
   - Group demo scenarios by platform.
   - Add the line: "FlowMedic only reads logs you approve. It never runs commands on your servers."

5. **Explain the badges and tags with tooltips:**
   - Verified: "From a reviewed incident or runbook in your knowledge base."
   - Cited: "From vendor documentation found by search; check before use."
   - Model: "From the model's own knowledge; lowest trust."
   - [read]: "Only reads or inspects; safe."
   - [change]: "Changes system state; review risk and rollback first."
   - [destructive]: "Can cause data loss or an outage."
   - Severity P1–P4: one line each.
   - Confidence: "How strongly the evidence supports this assessment."

6. **Walkthrough fixes:**
   - (a) Show repo-relative paths in the UI instead of absolute `/Users/...` paths. The API keeps absolute paths internally; convert for display only.
   - (b) Log discovery skips dotfiles (such as `.gitkeep`) and zero-byte files. This is a Python change; add a unit test.
   - (c) Approval card copy: replace "(null means the full export)" with "Leave times blank to read the full export."
   - (d) Topology edges run from the bottom centre of one node to the top centre of the next, and all node labels use the same font size.
   - (e) Skip any acronym or label fixes that Step 5c-1 already covered.

7. **First visit.** Open the "How FlowMedic works" dialog automatically the first time the app loads. Remember this in localStorage, wrapped in try/catch; the "?" button always reopens it.

Checks, run once at the end:
```
npm --prefix app/web run build ; npm --prefix app/web run lint ; npx impeccable detect app/web/src ; npx --prefix app/web playwright test ; uv run pytest -q -m "not live"
```
Add a "Step 5c-2: Setup, Knowledge and help" section to docs/progress.md. Reply with the check results.
