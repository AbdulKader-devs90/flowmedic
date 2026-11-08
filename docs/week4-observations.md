# Observations for Week 4 evals (from live walkthroughs, 7-8 Nov 2026)

Candidate failure categories to confirm and count on the golden dataset. Screenshots in `docs/screenshots/`.

1. **Dead-end escalation without evidence** (screenshots 06-08). Report: "CPU utilization is 95% and high in both IS nodes", no logs, evidence question skipped. Triage: P3 (correct by the rule "P3 = limited impact"; nothing says the service is down), category UNKNOWN, root cause no_fault_found at 20%, route clarify. The planner escalates immediately because clarify has no first steps (`planner/nodes.py`: no first_steps → escalate). However, the knowledge base had a relevant match (INC-007, CPU saturation from Basic auth hashing). Expected: a read-only "collect diagnostics" plan (thread dumps, top CPU threads, the INC-007 check) instead of a dead end. A good candidate for the Week 4 focused fix.
2. **Irrelevant runbook steps in the plan** (screenshot 02). SC-001 plan 1 included RB-02 steps (is-db reachability, DB password/account lock) that the pool-exhaustion evidence did not call for. After the fix, the revised plan still kept two RB-02 checks before verification.
3. **Clarifying question skipped when logs answer it.** SC-001 did not ask for the version because the logs supplied it. This is correct, but check that the golden cases expecting a clarify still get one.
4. **Re-triage works** (screenshots 03, 10): SC-001 re-planned on the DBA output (SID 1412, db_blocking_lock); KONG-SC-01 re-planned after a failed step. Keep these as passing regression cases.
5. **Severity behaves as defined:** Orders API 500 for all callers = P1 (service down); Kong partner 504s = P2; CPU high, no reported impact = P3.
