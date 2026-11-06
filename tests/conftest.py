"""Isolate unit tests from local credentials and cached settings."""

from collections.abc import Iterator

import pytest

from flowmedic.config import Settings, get_settings


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
