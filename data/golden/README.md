# Golden dataset v1

40 labelled cases for the Week 4 evaluation. The list is in `golden-v1.json`; each case lives in `data/scenarios/<case_id>/` (`problem.md`, `logs/`, `expected.json`).

- 12 Week 3 scenarios (`SC-001`..`SC-010`, `KONG-SC-01`, `KONG-SC-02`) and 28 new cases (`GC-01`..`GC-28`) built by `build_golden_v1.py`.
- Mix: 20 happy, 12 edge, 6 known failures, 2 adversarial.
- `engineer_answers` holds the scripted answers the eval harness gives to clarifying questions.
- All data is synthetic and anonymized. Labels were written before any evaluation run; see `docs/week4-eval-plan.md` for scoring.
