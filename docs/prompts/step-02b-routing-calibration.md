# Step 2b: routing calibration (follow-up in the same Codex chat as Step 2)

Why: SC-001 found INC-003 first but routed "similar" (score 0.712 < 0.80). Causes: multilingual-e5 cosine scores are compressed (unrelated docs ~0.82), and phrase signatures were not matched against log text.

---

Follow-up to Step 2: SC-001 routes "similar" but should be "known_fix". Two causes, fix both without special-casing any doc or scenario ID:

1. Signature matching: a knowledge-doc signature is a hit if its normalized error code matches an extracted code OR, for phrase signatures (not code-shaped), it appears case-insensitively in the masked log text. signature_score = hits / number of signatures on that doc (coverage of the doc's own signatures).

2. Vector calibration: multilingual-e5 cosine scores are compressed (unrelated docs score ~0.82). Rescale: vector_norm = clamp((raw - VEC_FLOOR) / (VEC_CEIL - VEC_FLOOR), 0, 1). Add VEC_FLOOR, VEC_CEIL, KB_VECTOR_WEIGHT, KB_SIGNATURE_WEIGHT to config and .env.example (defaults you choose below). Keep the raw vector score in KBMatch too.

3. Add a CLI "uv run python -m flowmedic.knowledge.route_report" that runs search + route_for on every scenario in data/scenarios that has expected_route in {known_fix, similar, new_issue}, and prints a table: case_id, expected route, predicted route, expected kb ids, top match, top score, PASS/FAIL, plus overall route accuracy and top-1 doc accuracy.

4. Pick defaults for VEC_FLOOR, VEC_CEIL, the two weights, KB_KNOWN_FIX and KB_SIMILAR by trying a small grid and choosing the simplest values that get the most scenarios right. Print the grid result. Do not hard-code scenario logic. Explain the chosen values in docs/progress.md, and note that these were tuned on 11 dev scenarios and will be checked on the larger Week 4 golden set.

5. Update tests (fake store) for phrase-signature hits and the rescaling.

Run and show: uv run ruff check . ; uv run pytest ; uv run python -m flowmedic.knowledge.route_report
