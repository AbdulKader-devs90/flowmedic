# Week 3 video script (5 minutes max)

Record with Loom or QuickTime (screen + voice). Before recording: API and UI running, browser at 125% zoom, notifications off (Focus mode), a LangSmith tab open on the flowmedic-dev project, VS Code open on the repo.

| Time | Screen | What to say (short, in your own words) |
| --- | --- | --- |
| 0:00-0:25 | FlowMedic empty war room | "When an integration platform breaks, the on-call engineer loses the first hours to SSH, grep, thread dumps and DB checks, then searching old emails and vendor sites. FlowMedic is a read-only, two-agent triage assistant that cuts that down." |
| 0:25-1:05 | docs/architecture.png, then topology.png | "A Triage Agent classifies the problem, reads only the logs I approve, and searches a knowledge repo of solved incidents and runbooks. A strong match gives the known fix; otherwise it researches IBM or Kong docs with citations. A Planner Agent then walks me through the fix step by step. It never runs anything and has no tool that can write to a server. The topology tells it which dependencies to check before suggesting a restart." |
| 1:05-1:45 | VS Code: docs/prompts/, AGENTS.md, docs/vibe_coding_log.md | "I split the AI tools. Claude planned the project, wrote the knowledge content and test scenarios, wrote one prompt per step and reviewed each result. Codex wrote the code from those prompts. AGENTS.md gives Codex fixed rules on every task, including a 45-minute budget after one step ran for two hours. Every prompt and iteration is in the repo." |
| 1:45-4:05 | UI: load demo scenario SC-008 | Main demo, see below. |
| 4:05-4:30 | UI: SC-007 result, then SC-009 flags | "A new issue: no repo match, so it researched IBM Community and every step is cited. And a log line telling the AI to kill all nodes is quarantined, with the password masked." |
| 4:30-4:50 | LangSmith trace of the SC-008 run | "Every incident is one trace in LangSmith, with each node, model call and tool call. That's the base for Week 4 evals." |
| 4:50-5:00 | War room | "It runs entirely on the cohort's free credits: Nebius models, Pinecone, Tavily and LangSmith. Thanks." |

## Main demo (SC-008, about 2 min 20 s)
1. **New incident → Load demo scenario → SC-008** ("is-node-b not responding, load very high"). Say: "a real multi-cause outage pattern."
2. **Log-access card:** point at folder and time window, click **Approve**. Say: "nothing is read without my approval."
3. **Activity rows** stream in; **Triage card** appears: OUTAGE, P1, root causes (auth-hashing thread pile-up, DB login timeouts), evidence links. Click one evidence link to show the log line in the drawer.
4. **Topology map:** the affected IS node pulses; Terracotta, messaging and the internal DB light up in check order. Say: "dependencies first, then callers."
5. **Hand-off** animation to the Planner. Step 1 shows [read], the command, expected output, Verified badge. Paste the output (or let the simulator answer) and click **Done**.
6. At the **DB step**, the output shows a session from a forced restart holding a lock for 127 minutes. The Planner **re-triages**: the Triage card updates with the DB-lock cause. Say: "it changed its mind because the evidence changed."
7. Show one **[change]** step with its specific risk and rollback; confirm it.
8. **Resolved** → the **save approval** card shows the incident record. Say: "approved saves become the next engineer's known fix." Click **Discard** to keep the demo repo clean (or Save if you want to show it).

## Tips
- Rehearse once; keep each sentence short. If a model call is slow, keep talking over the activity rows.
- If the UI is not ready, record the same flow with the CLI: `uv run python -m flowmedic.run SC-008 --auto`.
