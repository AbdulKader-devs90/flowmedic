"""Central configuration; provider credentials are validated only on use."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ModelRole = Literal["fast", "strong", "alt"]


class ConfigurationError(ValueError):
    """A selected provider is missing required configuration."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(".env"), env_file_encoding="utf-8", extra="ignore"
    )

    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = "claude-opus-5-5"
    nebius_api_key: SecretStr = SecretStr("")
    nebius_base_url: str = ""
    nebius_model: str = ""
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = ""
    tavily_api_key: SecretStr = SecretStr("")
    pinecone_api_key: SecretStr = SecretStr("")
    pinecone_index: str = "flowmedic-kb"
    vector_backend: Literal["pinecone", "chroma"] = "pinecone"
    langsmith_tracing: bool = True
    langsmith_api_key: SecretStr = SecretStr("")
    langsmith_project: str = "flowmedic-dev"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    agent_version: str = "0.1.0"

    def provider_key(self, role: ModelRole) -> str:
        """Return a selected role's key, or name its missing environment variable."""
        field = {
            "fast": "nebius_api_key",
            "strong": "anthropic_api_key",
            "alt": "openai_api_key",
        }[role]
        value: SecretStr = getattr(self, field)
        if not value.get_secret_value().strip():
            raise ConfigurationError(
                f"Missing {field.upper()} for model role '{role}'."
            )
        return value.get_secret_value()

    def model_name(self, role: ModelRole) -> str:
        """Validate and return the configured model identifier."""
        field = {
            "fast": "nebius_model",
            "strong": "anthropic_model",
            "alt": "openai_model",
        }[role]
        value: str = getattr(self, field)
        if not value.strip():
            raise ConfigurationError(
                f"Missing {field.upper()} for model role '{role}'."
            )
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once; call cache_clear() after changing configuration."""
    return Settings()
