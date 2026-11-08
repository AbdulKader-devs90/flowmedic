# Week 3 video script (5 minutes max)

Main demo: **SC-001** (Orders API down, JDBC pool exhausted), because it shows the strongest moment: the agent changes its plan when the DBA output reveals a blocking session (SID 1412). It has run end to end twice on live models.

## Before recording (10 minutes)
1. Clean demo state, so the sidebar is empty and the help dialog shows:
   ```
   lsof -ti :8000 | xargs kill -9 2>/dev/null
   mv runs/checkpoints.sqlite runs/checkpoints-rehearsal.sqlite 2>/dev/null; rm -f runs/checkpoints.sqlite-wal runs/checkpoints.sqlite-shm
   uv run flowmedic-api            # tab 1 (LANGSMITH_TRACING=false in .env)
   npm --prefix app/web run dev    # tab 2
   ```
   In Chrome, open localhost:5173 in a **guest or new profile window** (no profile photo, no tabs bar clutter), zoom 110-125%. In DevTools → Application → Local storage, clear it so "How FlowMedic works" opens on first load.
2. Have open, in this order: the FlowMedic window, `docs/architecture.png`, VS Code on the repo (AGENTS.md, docs/prompts/, docs/vibe_coding_log.md), a LangSmith tab on an existing SC-001 trace in `flowmedic-dev` (traces from 7-8 Nov are kept 14 days).
3. Focus mode on (no notifications). Keep the paste sheet below open in a text editor on a second screen or to the side.
4. Recording tool: Loom (screen + camera bubble) or QuickTime. **Use Pause** while a model call runs longer than a few seconds, so the video stays under 5 minutes; or record in segments and trim.

## Script

| Time | Screen | What to say (your own words) |
| --- | --- | --- |
| 0:00-0:25 | FlowMedic, "How FlowMedic works" dialog | "When an integration platform breaks, the on-call engineer loses the first hours to SSH, grep, thread dumps, DB checks and searching old incidents and vendor docs. FlowMedic is a read-only, two-agent triage assistant. It never runs anything on a server; the engineer stays in control." Read the 4 steps briefly, close the dialog. |
| 0:25-0:55 | `docs/architecture.png` | "LangGraph parent graph with two subgraphs. The Triage agent reads only approved logs through a read-only MCP log server, searches a Pinecone knowledge base of past incidents and runbooks, falls back to cited vendor research, and uses the environment topology to check dependencies first. It hands off to the Planner agent, which builds a step-by-step fix, waits for my result at every step, and re-triages when the evidence changes. State is checkpointed in SQLite." |
| 0:55-1:20 | Setup page (scroll Platforms → Kong card → Environments) | "Everything is configured from files: platforms like webMethods and Kong with the questions the agent asks and the log patterns, environments with their topology, and the knowledge base. Adding Kong was just these files." |
| 1:20-3:50 | War room, SC-001 | Main demo, below. |
| 3:50-4:20 | VS Code: docs/prompts/, AGENTS.md, docs/vibe_coding_log.md | "How AI coding tools helped: Claude planned the project, wrote the knowledge content and test scenarios, wrote one prompt per step and reviewed every result. Codex wrote the code. AGENTS.md gives Codex fixed rules, including a time budget after one step ran for two hours. When I tested the first UI myself it was confusing, so we redesigned it around one place to act. Every prompt and iteration is in the repo." |
| 4:20-4:45 | LangSmith trace | "Each incident is one LangSmith trace: every node, model call and tool call, tagged with case, prompt and agent version. That is the base for next week's evals." |
| 4:45-5:00 | War room home | "It runs entirely on the cohort credits: Nebius models, Pinecone, Tavily and LangSmith. Thanks." |

## Main demo: SC-001 (about 2 min 30 s with pauses)
1. Home → **SC-001**. Point at the **stage tracker**: "Report, Logs, Diagnose, Fix, Close, and it always tells me who is working and what it needs."
2. **Your turn: approve read-only log access.** "Nothing is read without my approval." Approve.
3. Pause while triage runs. Resume on **Diagnosis**: P1 · POOL · known fix INC-003, root cause with cited `server.log` lines. Click one citation to show the log line. "Every claim links to evidence."
4. **Topology** tab: "dependencies first, then callers."
5. Hand-off: the story shows "Triage agent handed over to Planner agent", the **Plan** tab opens. "Steps are verified from INC-003, read steps first."
6. **Your turn: step 1.** Paste the pool output, Done. Step 2: thread dump, Done.
7. Step 3 (DB check): paste the **DBA / SID 1412** output, Done. Pause. Resume on **"Plan revised after new evidence"**: "It changed its mind because the evidence changed: a blocking session, so the new plan targets SID 1412 exactly."
8. Show the **cancel SID 1412** step: [change], specific risk and rollback, the confirmation tick. Paste, Done. Then reset pool and verify.
9. **Your turn: save this incident?** Show the readable summary. "Approved saves become the next engineer's known fix." Click **Discard** (keeps the demo knowledge base clean), then **Back to war room**.

## Paste sheet (SC-001, synthetic data)
Match by the step title; anything else → **Skipped**.
- **Pool usage:** `Admin UI > Adapters > JDBC Adapter > Connections > OrdersApi.connections:OrdersDB_Pool  Min 0 | Max 15 | In use 15 | Available 0 | Block timeout 10000 ms | Waiting requests 37`
- **Thread dump:** `is-node-a thread dump 10:44: 37 HTTP Handler threads waiting in JDBCConnectionPool.getConnection, 15 in T4CPreparedStatement.executeForRows (OrdersApi.db:insertOrder)`
- **DB / blocking sessions / is-db:** `DBA: SID 1412 ACTIVE elapsed 00:07:41, SELECT ... FROM ORDER_REPORT_V (ad-hoc report). 14 other sessions waiting on SID 1412 (enq: TX - row lock contention)`
- **Inspect SID 1412 / owner:** `SID 1412 belongs to is-node-a, program JDBC Thin Client, user ORDERS_SVC. It is a manual ad-hoc ORDER_REPORT_V report, not a business-critical OrdersApi thread. 14 sessions are waiting on it.`
- **Cancel SID 1412:** `Report owner confirmed manual ad-hoc run. DBA killed SID 1412 at 10:49.`
- **Pool after clearance / reset pool:** `Connection disabled and enabled at 10:51. Pool now: In use 3 | Available 12 | Waiting 0.`
- **DB password / account lock:** `Password unchanged, account ORDERS_SVC open and unlocked.`
- **is-db reachability:** `Listener responds; JDBC test connection from is-node-a and is-node-b succeeds.`
- **Verify:** `Orders API returning 200 since 10:52. No ART.118.5053 in server.log since 10:50.`

## Tips
- Rehearse once with the paste sheet, then clean state again (step 1) before the real take.
- If a live call fails during recording, show the CLI instead: `uv run python -m flowmedic.run SC-001 --auto` and the screenshots in `docs/screenshots/`.
