"""The sole knowledge write path, guarded by explicit session approval."""

import re
import time
from datetime import date
from pathlib import Path

import yaml

from flowmedic.config import get_settings
from flowmedic.graph.state import IncidentRecord
from flowmedic.knowledge.loaders import KnowledgeDoc
from flowmedic.tools.environment_memory import local_path
from flowmedic.tools.knowledge_repo import VectorStore, get_vector_store
from flowmedic.tools.redact import redact
from flowmedic.tracing import traced_tool


class IncidentIndexError(RuntimeError):
    """Approved Markdown exists; indexing needs an explicit retry, not another save."""

    def __init__(self, path: Path) -> None:
        super().__init__("Incident saved locally; vector indexing failed twice.")
        self.path = path


@traced_tool
def save_incident(
    record: IncidentRecord,
    *,
    approved: bool,
    knowledge_dir: Path | None = None,
    store: VectorStore | None = None,
) -> Path | None:
    """Create a new id without overwrites, then upsert exactly this document.

    If upsert fails, the approved Markdown remains available for explicit reindexing.
    The error is propagated so the graph records the indexing gap.
    """
    if not approved:
        return None
    folder = local_path(knowledge_dir or get_settings().knowledge_dir) / "incidents"
    folder = local_path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    ids = [
        int(m[1])
        for p in folder.glob("INC-*.md")
        if (m := re.fullmatch(r"INC-(\d+)", p.stem))
    ]
    number = max(ids, default=0) + 1
    safe = IncidentRecord.model_validate_json(redact(record.model_dump_json()).text)
    doc = KnowledgeDoc(
        id=f"INC-{number:03d}",
        type="incident",
        title=safe.symptoms.splitlines()[0][:140],
        platform=safe.platform,
        category=safe.category,
        versions=[safe.version] if safe.version else [],
        os=[safe.os] if safe.os else [],
        components=safe.components,
        signatures=safe.signatures,
        root_causes=[c.value for c in safe.root_causes],
        source=f"flowmedic session {date.today().isoformat()}",
        verified=True,
        environment=safe.environment,
        body="## Symptoms\n"
        + safe.symptoms
        + "\n\n## Root cause\n"
        + ", ".join(safe.root_causes)
        + "\n\n## Resolution steps\n"
        + "\n".join(
            f"{n}. [{s.get('kind', 'read')}] {s.get('action', '')}\n"
            f"   Observed: {s.get('output', '')}"
            for n, s in enumerate(safe.steps_worked, 1)
        ),
    )
    # Exclusive creation also protects against concurrent sessions allocating an id.
    while True:
        target = local_path(folder / f"{doc.doc_id}.md")
        try:
            with target.open("x", encoding="utf-8") as stream:
                metadata = doc.model_dump(mode="json", by_alias=True, exclude={"body"})
                stream.write(
                    "---\n"
                    + yaml.safe_dump(metadata, sort_keys=False)
                    + "---\n"
                    + doc.body
                    + "\n"
                )
            break
        except FileExistsError:
            number += 1
            doc.doc_id = f"INC-{number:03d}"
    for attempt in range(2):
        try:
            (store or get_vector_store()).upsert([doc])
            return target
        except Exception as exc:
            if attempt:
                raise IncidentIndexError(target) from exc
            time.sleep(get_settings().retry_backoff)
    return target
