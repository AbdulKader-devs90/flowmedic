"""Explicit, idempotent ingestion of the human-approved seed knowledge."""

from flowmedic.config import ConfigurationError
from flowmedic.knowledge.loaders import load_documents
from flowmedic.tools.knowledge_repo import VectorStore, get_vector_store
from flowmedic.tracing import traced_tool


@traced_tool
def ingest(store: VectorStore | None = None) -> int:
    """Upsert each document by its controlled ID."""
    docs = load_documents()
    (store or get_vector_store()).upsert(docs)
    return len(docs)


def main() -> None:
    """Run ingestion; never silently replace the selected backend."""
    try:
        count = ingest()
    except ConfigurationError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Ingested {count} documents (upsert by doc_id).")


if __name__ == "__main__":
    main()
