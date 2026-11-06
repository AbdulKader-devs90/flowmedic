"""Platform-filtered hybrid retrieval with interchangeable vector storage."""

import re
from collections.abc import Sequence
from typing import Any, Protocol

from pydantic import BaseModel

from flowmedic.config import REPO_ROOT, ConfigurationError, Settings, get_settings
from flowmedic.graph.state import KBMatch, Route
from flowmedic.knowledge.loaders import KnowledgeDoc, load_documents
from flowmedic.tools.parsers.signatures import CODE, normalize_signature
from flowmedic.tools.redact import redact
from flowmedic.tracing import traced_tool


class VectorHit(BaseModel):
    """Raw backend cosine similarity, before calibration; larger is better."""

    doc_id: str
    score: float


class VectorStore(Protocol):
    """Only explicit ingestion writes to this store."""

    def upsert(self, documents: Sequence[KnowledgeDoc]) -> None: ...

    def query(self, text: str, platform: str, k: int) -> list[VectorHit]: ...


def _metadata(doc: KnowledgeDoc) -> dict[str, Any]:
    return {
        "doc_id": doc.doc_id,
        "doc_type": doc.doc_type,
        "platform": doc.platform,
        "category": doc.category.value,
        "versions": doc.versions,
        "components": doc.components,
    }


class ChromaStore:
    """Persistent cosine index using Chroma's default local embedding model."""

    def __init__(self, settings: Settings | None = None) -> None:
        import chromadb
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

        settings = settings or get_settings()
        path = settings.chroma_path
        if not path.is_absolute():
            path = REPO_ROOT / path
        if not path.resolve().is_relative_to(REPO_ROOT):
            raise ConfigurationError("CHROMA_PATH must be inside the repository")
        # Chroma otherwise downloads its model into a cache outside the repository.
        embedding = ONNXMiniLM_L6_V2()
        embedding.DOWNLOAD_PATH = REPO_ROOT / ".cache/chroma/onnx_models"
        self.collection = chromadb.PersistentClient(
            path=str(path), settings=chromadb.Settings(anonymized_telemetry=False)
        ).get_or_create_collection(
            "flowmedic",
            configuration={"hnsw": {"space": "cosine"}},
            embedding_function=embedding,
        )

    @traced_tool
    def upsert(self, documents: Sequence[KnowledgeDoc]) -> None:
        """Stable IDs make repeated ingestion idempotent."""
        if not documents:
            return
        # Chroma metadata does not accept empty arrays; serialize list metadata.
        import json

        self.collection.upsert(
            ids=[d.doc_id for d in documents],
            documents=[redact(d.embedding_text()).text for d in documents],
            metadatas=[
                {
                    key: json.dumps(value) if isinstance(value, list) else value
                    for key, value in _metadata(d).items()
                }
                for d in documents
            ],
        )

    @traced_tool
    def query(self, text: str, platform: str, k: int) -> list[VectorHit]:
        """Convert cosine distance to bounded similarity."""
        if not self.collection.count():
            return []
        result = self.collection.query(
            query_texts=[redact(text).text], where={"platform": platform}, n_results=k
        )
        return [
            VectorHit(doc_id=doc_id, score=max(-1.0, min(1.0, 1 - distance)))
            for doc_id, distance in zip(
                result["ids"][0], (result["distances"] or [[]])[0]
            )
        ]


class PineconeStore:
    """Serverless cosine index with explicitly hosted Pinecone embeddings."""

    def __init__(self, settings: Settings | None = None) -> None:
        from pinecone import Pinecone

        self.settings = settings or get_settings()
        key = self.settings.pinecone_api_key.get_secret_value()
        if not key:
            raise ConfigurationError(
                "Missing PINECONE_API_KEY; configure it or use VECTOR_BACKEND=chroma"
            )
        self.client = Pinecone(api_key=key)

    @traced_tool
    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        embeddings = self.client.inference.embed(
            model=self.settings.embed_model,
            inputs=[redact(t).text for t in texts],
            parameters={"input_type": input_type, "truncate": "END"},
        )
        return [item["values"] for item in embeddings]

    @traced_tool
    def upsert(self, documents: Sequence[KnowledgeDoc]) -> None:
        """Create a missing index only during explicitly requested ingestion."""
        from pinecone import ServerlessSpec

        for start in range(0, len(documents), 32):
            batch = documents[start : start + 32]
            vectors = self._embed([d.embedding_text() for d in batch], "passage")
            if not self.client.has_index(self.settings.pinecone_index):
                self.client.create_index(
                    name=self.settings.pinecone_index,
                    dimension=len(vectors[0]),
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud=self.settings.pinecone_cloud,
                        region=self.settings.pinecone_region,
                    ),
                )
            self.client.Index(self.settings.pinecone_index).upsert(
                vectors=[
                    {
                        "id": doc.doc_id,
                        "values": vector,
                        "metadata": {
                            k: v for k, v in _metadata(doc).items() if v != []
                        },
                    }
                    for doc, vector in zip(batch, vectors)
                ]
            )

    @traced_tool
    def query(self, text: str, platform: str, k: int) -> list[VectorHit]:
        """Search an existing index; querying never creates an index."""
        result = self.client.Index(self.settings.pinecone_index).query(
            vector=self._embed([text], "query")[0],
            top_k=k,
            filter={"platform": {"$eq": platform}},
        )
        return [
            VectorHit(doc_id=m["id"], score=max(-1.0, min(1.0, m["score"])))
            for m in result["matches"]
        ]


def get_vector_store() -> VectorStore:
    """Select the explicitly configured backend, without silent fallback."""
    return (
        ChromaStore() if get_settings().vector_backend == "chroma" else PineconeStore()
    )


def is_code_signature(signature: str) -> bool:
    """Recognize whole product/Oracle codes, including product prefix codes."""
    return bool(CODE.fullmatch(signature) or re.fullmatch(r"ORA-\d{5}", signature))


def normalize_vector(raw: float, settings: Settings) -> float:
    """Linearly calibrate compressed cosine scores to [0, 1]."""
    return max(
        0.0,
        min(1.0, (raw - settings.vec_floor) / (settings.vec_ceil - settings.vec_floor)),
    )


@traced_tool
def search(
    query_text: str,
    signatures: Sequence[str],
    platform: str,
    version: str | None = None,
    k: int = 5,
    *,
    store: VectorStore | None = None,
    documents: Sequence[KnowledgeDoc] | None = None,
    log_text: str | None = None,
    settings: Settings | None = None,
) -> list[KBMatch]:
    """Rerank all platform candidates, including exact hits outside vector top-k.

    Signature coverage is hits divided by the document's signature count.
    Codes match extracted codes exactly after normalization; phrases match masked
    log text case-insensitively. If log_text is omitted, query_text is used.
    Version, when supplied, strictly filters version-specific documents. Category
    corroboration is explicit via KBMatch for future classifiers, never inferred
    from the fixture's expected answers.
    """
    if k < 1:
        raise ValueError("k must be positive")
    settings = settings or get_settings()
    all_docs = list(documents) if documents is not None else load_documents()
    docs = [
        d
        for d in all_docs
        if d.platform == platform
        and (version is None or not d.versions or version in d.versions)
    ]
    if not docs:
        return []
    hits = (store or get_vector_store()).query(
        redact(query_text).text, platform, max(k, len(all_docs))
    )
    scores = {h.doc_id: h.score for h in hits}
    masked_logs = redact(log_text if log_text is not None else query_text).text
    requested = {normalize_signature(s) for s in signatures}
    matches: list[KBMatch] = []
    for doc in docs:
        doc_signatures = {
            normalize_signature(s) if is_code_signature(s) else s.strip()
            for s in doc.signatures
            if s.strip()
        }
        overlap = sorted(
            signature
            for signature in doc_signatures
            if (
                signature in requested
                if is_code_signature(signature)
                else signature.casefold() in masked_logs.casefold()
            )
        )
        raw_vector = scores.get(doc.doc_id)
        vector = (
            normalize_vector(raw_vector, settings) if raw_vector is not None else 0.0
        )
        if doc.doc_id not in scores and not overlap:
            continue
        coverage = len(overlap) / len(doc_signatures) if doc_signatures else 0.0
        score = (
            settings.kb_vector_weight * vector + settings.kb_signature_weight * coverage
        )
        matches.append(
            KBMatch(
                doc_id=doc.doc_id,
                doc_type=doc.doc_type,
                title=doc.title,
                score=score,
                signature_hits=overlap,
                vector_score=vector,
                raw_vector_score=raw_vector if raw_vector is not None else 0.0,
                signature_score=coverage,
            )
        )
    return sorted(matches, key=lambda m: (-m.score, m.doc_id))[:k]


@traced_tool
def route_for(matches: Sequence[KBMatch], *, settings: Settings | None = None) -> Route:
    """A high semantic score alone cannot establish a known fix."""
    if not matches:
        return Route.NEW_ISSUE
    best = max(matches, key=lambda m: m.score)
    settings = settings or get_settings()
    if best.score >= settings.kb_known_fix and (
        best.signature_hits or best.category_match
    ):
        return Route.KNOWN_FIX
    if best.score >= settings.kb_similar:
        return Route.SIMILAR
    return Route.NEW_ISSUE
