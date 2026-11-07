"""Isolate unit tests from local credentials and cached settings."""

import os

# Offline tests must never send traces: LangSmith caches these env reads, so set
# them before anything imports langsmith. Live tests opt back in explicitly.
if os.environ.get("FLOWMEDIC_TEST_TRACING") != "1":
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402

from flowmedic.config import Settings, get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_settings(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Iterator[None]:
    get_settings.cache_clear()
    if request.node.get_closest_marker("live") is None:
        for field in Settings.model_fields:
            monkeypatch.delenv(field.upper(), raising=False)
        monkeypatch.setattr(
            Settings,
            "model_config",
            {
                **Settings.model_config,
                "env_file": None,
            },
        )
    yield
    get_settings.cache_clear()
