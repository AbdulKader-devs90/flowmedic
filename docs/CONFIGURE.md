# Configure FlowMedic

How FlowMedic is configured. Everything here comes from files in the repo; change the file, restart the API, and the change shows up here.

Setup is read-only. The Knowledge page lists incidents and runbooks and opens their source documents.

## How to add a platform

1. Copy an existing file in `platforms/` (for example `kong.yaml`).
2. Set `id`, `name`, `versions` and `os`. For Kong, `id` is `kong` and `versions` includes `"3.8"`.
3. List the questions the agent must ask in `clarify_slots.required` and the extra questions in `clarify_slots.optional`.
4. List `components` with `type`, `logs` and `error_patterns`.
5. Add incidents and runbooks under `knowledge/incidents/` and `knowledge/runbooks/` with `platform: kong`, then run: `uv run python -m flowmedic.knowledge.ingest`.
6. Restart the API.

## How to add an environment

1. Create `environments/<name>/topology.yaml`. Set `environment`, `platform`, `version` and `os`. Use `components` with `id` and `type`; layers are derived from `type`. Use `links` with `from`, `to`, `kind` and `hard: true` for a hard dependency or `hard: false` for a soft dependency. See `environments/kong-sample/topology.yaml`.
2. Optionally add `architecture.png`, with no real IPs or hostnames.
3. Set `default_environment` in the platform file if this environment should be the default (for Kong: `kong-sample`).
4. Restart the API.

Ingestion explicitly approves indexing the knowledge files using the configured vector backend. It can call the configured embedding service; do not run it during offline UI checks.
