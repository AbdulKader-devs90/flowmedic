"""Settings load safely before any provider is selected."""

from pathlib import Path

import pytest

from flowmedic.config import ConfigurationError, Settings, get_settings


def test_settings_load_temporary_env(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "STRONG_PROVIDER=anthropic\n"
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
    with pytest.raises(ConfigurationError, match="NEBIUS_API_KEY.*nebius"):
        settings.provider_key("strong")


def test_settings_are_cached() -> None:
    assert get_settings() is get_settings()


def test_role_defaults_and_model_overrides() -> None:
    settings = Settings(nebius_model="shared-nebius", fast_model="role-fast")
    assert settings.provider_name("fast") == "nebius"
    assert settings.provider_name("strong") == "nebius"
    assert settings.provider_name("alt") == "anthropic"
    assert settings.model_name("fast") == "role-fast"
    assert settings.model_name("strong") == "shared-nebius"
    assert settings.model_name("alt") == settings.anthropic_model


@pytest.mark.parametrize("role", ["fast", "strong", "alt"])
@pytest.mark.parametrize("provider", ["nebius", "anthropic", "openai"])
def test_role_keys_models_and_errors(role: str, provider: str) -> None:
    settings = Settings(
        **{
            f"{role}_provider": provider,
            f"{provider}_api_key": "synthetic-key",
            f"{provider}_model": "provider-default",
        }
    )
    assert settings.provider_key(role) == "synthetic-key"
    assert settings.model_name(role) == "provider-default"
    setattr(settings, f"{role}_model", "role-override")
    assert settings.model_name(role) == "role-override"
    missing = Settings(**{f"{role}_provider": provider, f"{provider}_model": ""})
    with pytest.raises(
        ConfigurationError, match=f"{provider.upper()}_API_KEY.*{provider}"
    ):
        missing.provider_key(role)
    with pytest.raises(
        ConfigurationError, match=f"{provider.upper()}_MODEL.*{provider}"
    ):
        missing.model_name(role)
