"""Settings load safely before any provider is selected."""

from pathlib import Path

import pytest

from flowmedic.config import ConfigurationError, Settings, get_settings


def test_settings_load_temporary_env(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "ANTHROPIC_API_KEY=synthetic-key\nANTHROPIC_MODEL=test-claude\n"
        "AGENT_VERSION=0.2.0\nLANGSMITH_TRACING=false\n",
        encoding="utf-8",
    )
    settings = Settings(_env_file=env)
    assert settings.provider_key("strong") == "synthetic-key"
    assert settings.model_name("strong") == "test-claude"
    assert settings.agent_version == "0.2.0"
    assert settings.langsmith_tracing is False
    assert "synthetic-key" not in repr(settings)


def test_missing_key_is_valid_until_provider_used() -> None:
    settings = Settings()
    assert settings.agent_version == "0.1.0"
    with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
        settings.provider_key("strong")


def test_settings_are_cached() -> None:
    assert get_settings() is get_settings()
