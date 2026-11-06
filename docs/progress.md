# Step 2 done

Implemented small Pydantic state contracts, repository-root loaders with controlled
category/root-cause validation, platform profiles and scenario loading, ordered
topology checks, diagnostic parsers (signatures, thread dumps, memory/load/swap,
connections), secret masking and suspicious-line quarantine. Existing knowledge,
profiles, topologies and scenario content were read without changes.

Added a VectorStore protocol, Pinecone hosted inference/serverless ingestion and
local Chroma persistence with its default embedding model. Ingestion upserts one
vector per document ID. Hybrid search combines configured vector similarity and
normalized signature overlap; routing requires corroboration for a known fix.
Tool tracing carries case/version/model metadata and omits raw diagnostic payloads.
No agents, graph execution or UI were added.

Run from the repository root:

```sh
uv sync
# Configure .env: VECTOR_BACKEND=pinecone and PINECONE_API_KEY,
# or VECTOR_BACKEND=chroma for local embeddings (initial model download required).
uv run ruff check .
uv run pytest
uv run python -m flowmedic.knowledge.ingest
uv run python -m flowmedic.knowledge.try_search SC-001
uv run python -m flowmedic.knowledge.try_search SC-007
# Optional real-backend test:
uv run pytest -m live tests/test_knowledge.py
```

Validation: lint and format checks passed; 40 offline tests passed, with 2 live
tests deselected by default. Backend adapter and trace metadata tests use mocks.
The configured Pinecone backend previously ingested all 30 documents successfully.
Chroma is implemented; real Chroma model download/embedding has not been validated.

## Step 2 follow-up: signature coverage and vector calibration

Replaced query-signature coverage with coverage of each document's own signatures.
Normalized error codes must match extracted codes exactly. Phrase signatures match
case-insensitively in masked logs; quarantined injection lines cannot create hits.
The CLI passes logs separately so problem text cannot provide phrase corroboration.
`KBMatch.signature_score` records coverage, `raw_vector_score` retains the backend
cosine, and `vector_score` records the calibrated value. Empty signature lists
contribute zero coverage. No scenario or document IDs appear in scoring rules.

Vector calibration uses `clamp((raw - floor) / (ceil - floor), 0, 1)`. Configuration
validates `floor < ceil`, weights summing to one, and ordered route thresholds.
Chosen defaults:

| Setting | Value |
| --- | --- |
| VEC_FLOOR | 0.80 |
| VEC_CEIL | 0.86 |
| KB_VECTOR_WEIGHT | 0.60 |
| KB_SIGNATURE_WEIGHT | 0.40 |
| KB_KNOWN_FIX | 0.60 |
| KB_SIMILAR | 0.40 |

Tried the Cartesian grid of floors {0.80, 0.82}, ceilings {0.88, 0.86}, vector
weights {0.50, 0.60, 0.40} (signature weight is the complement), known-fix
thresholds {0.80, 0.70, 0.60}, and similar thresholds {0.60, 0.50, 0.40}:
108 configurations. Each scenario is searched once, then all candidates' raw
scores are replayed locally for each configuration without repeated embeddings.
The grid ranks by route accuracy, then expected top-1 accuracy, then the explicit
grid order to prefer round values and original thresholds when equally accurate.

The selected configuration was the sole 11/11 route winner in this run, with
9/9 expected top-1 documents correct; the next-best configurations scored 10/11
routes. It keeps the original 60/40 weights. The cosine range removes the inflated
baseline while spreading relevant similarities; thresholds were adjusted for the
new score scale. SC-001 now has all three document signatures present and scores
about 0.940, routing to known_fix. SC-006 has no heap-OOM phrase match and scores
about 0.473, routing to similar. SC-009's exact connection-refused phrase and
weaker vector similarity score about 0.616, still known_fix. The two new-issue
cases score below 0.40. These values are observations, not special-case rules.

**These defaults were tuned on 11 dev scenarios and will be checked on the larger
Week 4 golden set.** This is development-set accuracy, not held-out evidence of
generalization. The calibration is specific to the current multilingual-e5 index;
retune it for other embedding models. Seed content and expected labels were not
changed. The full grid output is saved in [retrieval-grid.txt](retrieval-grid.txt).

```sh
uv run ruff check .
uv run pytest
uv run python -m flowmedic.knowledge.route_report
uv run python -m flowmedic.knowledge.route_report --grid
```

The report searches every scenario whose expected route is known_fix, similar or
new_issue (11 cases; clarify is excluded). Expected labels are read only for
eligibility and evaluation, never passed to ranking. PASS checks route and any
expected top-1 KB ID. Overall route accuracy uses all 11 cases; top-1 doc accuracy
uses only the 9 cases with expected KB IDs. Existing .env calibration settings
override the new defaults; .env.example documents all six parameters.

Next: Step 3 triage intake, clarification, classification and evidence gathering.
Preserve the read-only operations boundary and human execution/approval flow.
