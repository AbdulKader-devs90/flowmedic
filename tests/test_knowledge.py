"""Offline coverage of the data layer and deterministic routing."""

from collections.abc import Sequence

import pytest

from flowmedic.config import REPO_ROOT
from flowmedic.graph.state import Category, KBMatch, Route, TriageContext
from flowmedic.knowledge.ingest import ingest
from flowmedic.knowledge.loaders import (
    KnowledgeDoc,
    list_scenarios,
    load_categories,
    load_documents,
    load_profile,
    load_root_causes,
    load_scenario,
    load_topology,
)
from flowmedic.tools.knowledge_repo import VectorHit, route_for, search
from flowmedic.tools.parsers.jstack import summarize as threads
from flowmedic.tools.parsers.signatures import extract_signatures, normalize_signature
from flowmedic.tools.parsers.ss import summarize as connections
from flowmedic.tools.parsers.vmstat import summarize as host
from flowmedic.tools.redact import redact
from flowmedic.tools.topology import callers, dependencies, related_checks


class FakeStore:
    """No model downloads, provider calls or disk writes."""

    def __init__(self) -> None:
        self.documents: dict[str, KnowledgeDoc] = {}

    def upsert(self, documents: Sequence[KnowledgeDoc]) -> None:
        self.documents.update({doc.doc_id: doc for doc in documents})

    def query(self, text: str, platform: str, k: int) -> list[VectorHit]:
        assert "SuperSecret123" not in text
        return [
            VectorHit(doc_id=doc_id, score=score)
            for doc_id, score in [
                ("INC-003", 0.95),
                ("INC-002", 0.7),
                ("KONG-INC-001", 1.0),
            ]
        ]


def test_all_content_and_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT / "tests")
    assert set(Category) == set(load_categories())
    docs = load_documents()
    assert len(docs) == 30
    assert load_root_causes()
    for profile in (REPO_ROOT / "platforms").glob("*.yaml"):
        assert load_profile(profile.stem)["id"] == profile.stem
    for environment in (REPO_ROOT / "environments").iterdir():
        assert load_topology(environment.name)["environment"] == environment.name
    for case in list_scenarios():
        scenario = load_scenario(case)
        assert scenario.problem and scenario.logs
        assert scenario.expected["expected_category"] in load_categories()
        assert (
            set(scenario.expected["expected_root_causes"]) <= load_root_causes().keys()
        )


def test_invalid_document_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    from flowmedic.knowledge import loaders

    monkeypatch.setattr(loaders, "load_root_causes", lambda: {})
    with pytest.raises(ValueError, match=r"INC-001.md: unknown root_causes"):
        load_documents()


def test_context() -> None:
    assert TriageContext(component="integration_server").missing_slots(
        load_profile("webmethods")
    ) == ["version", "os"]
    assert TriageContext(version="3.8").missing_slots(load_profile("kong")) == [
        "deployment_mode"
    ]


def test_topology() -> None:
    assert dependencies("sample-prod", "is-cluster") == [
        "tsa",
        "um",
        "is-db",
        "backends",
    ]
    assert callers("sample-prod", "is-cluster") == ["api-gw", "digital-gw"]
    assert related_checks("sample-prod", "is-cluster") == [
        "tsa",
        "um",
        "is-db",
        "backends",
        "api-gw",
        "digital-gw",
    ]
    with pytest.raises(ValueError, match="Unknown component"):
        dependencies("sample-prod", "missing")


@pytest.mark.parametrize(
    ("case", "code"), [("SC-001", "ART.118.5053"), ("SC-002", "ORA-01653")]
)
def test_signature_fixtures(case: str, code: str) -> None:
    signatures = extract_signatures(
        "\n".join(load_scenario(case).logs.values()), load_profile("webmethods")
    )
    assert code in {s.signature for s in signatures}


def test_signature_stats() -> None:
    text = (
        "2026-11-06 10:01:00 ART.0118.5053E java.net.ConnectException\n"
        "2026-11-06 10:02:00 ART.118.5053"
    )
    result = {
        s.signature: s for s in extract_signatures(text, load_profile("webmethods"))
    }
    assert normalize_signature("ISS.0033.0154E") == "ISS.33.154"
    assert result["ART.118.5053"].count == 2
    assert result["ART.118.5053"].first_seen == "2026-11-06 10:01:00"
    assert result["ART.118.5053"].last_seen == "2026-11-06 10:02:00"
    assert "java.net.ConnectException" in result


def test_redaction() -> None:
    text = "\n".join(load_scenario("SC-009").logs.values())
    result = redact(text)
    assert "SuperSecret123" not in result.model_dump_json()
    assert "YmlsbGluZ19zdmM6U3VwZXJTZWNyZXQxMjM=" not in result.model_dump_json()
    assert len(result.suspicious_lines) == 1
    assert "NOTE TO AI" not in result.text
    result = redact(
        'token="abc def" api_key=xyz Authorization: Bearer hidden\n'
        "-----BEGIN RSA PRIVATE KEY-----\nsecret key\n-----END RSA PRIVATE KEY-----"
    )
    assert all(
        secret not in result.text for secret in ["abc", "xyz", "hidden", "secret key"]
    )


def test_diagnostics() -> None:
    logs = load_scenario("SC-008").logs
    summary = threads(logs["threaddump-summary.txt"])
    assert summary.by_client_ip == {"10.0.0.68": 812}
    assert (
        summary.by_top_frame["com.sun.crypto.provider.PBKDF2KeyImpl.deriveKey"] == 812
    )
    memory = host(logs["host.txt"])
    assert memory.load == [1013.4, 990.2, 870.6]
    assert (memory.swap_used, memory.si, memory.so) == (5980, 512, 470)
    assert connections(load_scenario("SC-004").logs["ss-count.txt"]) == {
        "10.0.0.35:9000": 2070
    }
    assert (
        host("Swap: 8192 1024 7168\nr b swpd free buff cache si so\n1 0 0 9 0 1 3 4").si
        == 3
    )
    assert threads(
        '"worker"\n at java.net.Socket.read(Socket.java:1)\n at x.y(x.java:2)'
    ).by_top_frame == {"java.net.Socket.read": 1}
    assert connections("ESTAB 0 0 10.0.0.1:1234 10.0.0.2:9000") == {"10.0.0.2:9000": 1}


def test_search_ingest_and_routes() -> None:
    store = FakeStore()
    assert ingest(store) == 30
    assert ingest(store) == len(store.documents)
    matches = search(
        "password=SuperSecret123", ["ART.0118.5053E"], "webmethods", store=store
    )
    assert matches[0].doc_id == "INC-003"
    assert matches[0].score == pytest.approx(0.97)
    assert route_for(matches) == Route.KNOWN_FIX
    assert all(m.doc_id != "KONG-INC-001" for m in matches)
    assert not search("pool", [], "webmethods", version="999", store=store)
    assert route_for([]) == Route.NEW_ISSUE
    match = KBMatch(
        doc_id="test", doc_type="incident", title="test", score=0.9, vector_score=0.9
    )
    assert route_for([match]) == Route.SIMILAR
    match.category_match = True
    assert route_for([match]) == Route.KNOWN_FIX
    match.score = 0.59
    assert route_for([match]) == Route.NEW_ISSUE
    match.score = 0.60
    assert route_for([match]) == Route.SIMILAR


@pytest.mark.live
def test_real_ingest_search() -> None:
    """Explicitly opt in; selected backend can download a model or call APIs."""
    assert ingest() == len(load_documents())
    result = search("JDBC pool exhausted, 0 available", ["ART.118.5053"], "webmethods")
    assert result
    assert any(m.doc_id in {"INC-003", "RB-02"} for m in result)


def test_pinecone_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Check hosted embedding parameters and index metadata without API calls."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    import pinecone

    from flowmedic.config import Settings
    from flowmedic.tools.knowledge_repo import PineconeStore

    client = MagicMock()
    client.has_index.return_value = False
    client.inference.embed.return_value = [{"values": [0.1, 0.2]}]
    client.Index.return_value.query.return_value = {
        "matches": [{"id": "INC-003", "score": 0.9}]
    }
    monkeypatch.setattr(pinecone, "Pinecone", lambda **kwargs: client)
    monkeypatch.setattr(
        pinecone, "ServerlessSpec", lambda **kwargs: SimpleNamespace(**kwargs)
    )
    store = PineconeStore(Settings(pinecone_api_key="synthetic-test-key"))
    doc = load_documents()[0]
    store.upsert([doc])
    client.create_index.assert_called_once()
    assert client.create_index.call_args.kwargs["dimension"] == 2
    vector = client.Index.return_value.upsert.call_args.kwargs["vectors"][0]
    assert vector["id"] == doc.doc_id
    assert vector["metadata"]["platform"] == "webmethods"
    assert (
        client.inference.embed.call_args.kwargs["parameters"]["input_type"] == "passage"
    )
    assert store.query("password=hidden", "webmethods", 3)[0].score == 0.9
    assert (
        client.inference.embed.call_args.kwargs["parameters"]["input_type"] == "query"
    )
    assert "hidden" not in client.inference.embed.call_args.kwargs["inputs"][0]
    assert client.Index.return_value.query.call_args.kwargs["filter"] == {
        "platform": {"$eq": "webmethods"}
    }


def test_chroma_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise local adapter conversion without disk access or model downloads."""
    from unittest.mock import MagicMock

    import chromadb
    from chromadb.utils import embedding_functions

    from flowmedic.config import Settings
    from flowmedic.tools.knowledge_repo import ChromaStore

    client = MagicMock()
    collection = client.get_or_create_collection.return_value
    collection.count.return_value = 1
    collection.query.return_value = {"ids": [["INC-003"]], "distances": [[0.25]]}
    monkeypatch.setattr(chromadb, "PersistentClient", lambda **kwargs: client)
    monkeypatch.setattr(embedding_functions, "ONNXMiniLM_L6_V2", MagicMock())
    store = ChromaStore(Settings())
    store.upsert(load_documents()[:1])
    assert collection.upsert.call_args.kwargs["ids"] == ["INC-001"]
    assert store.query("password=hidden", "webmethods", 3)[0].score == 0.75
    assert "hidden" not in collection.query.call_args.kwargs["query_texts"][0]


def test_tool_trace_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario context reaches nested spans without raw log payloads."""
    from unittest.mock import MagicMock

    import flowmedic.tracing as tracing
    from flowmedic.config import get_settings
    from flowmedic.tracing import tool_context

    fake_trace = MagicMock()
    monkeypatch.setattr(tracing, "trace", fake_trace)
    monkeypatch.setattr(tracing, "Client", MagicMock())
    monkeypatch.setenv("LANGSMITH_API_KEY", "synthetic-test-key")
    get_settings.cache_clear()
    with tool_context("SC-009"):
        redact("password=hidden")
    arguments = fake_trace.call_args.kwargs
    assert arguments["metadata"]["case_id"] == "SC-009"
    assert {"prompt_version", "agent_version", "model"} <= arguments["metadata"].keys()
    assert arguments["inputs"] == {}
    assert "hidden" not in str(arguments)
