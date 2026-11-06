"""Central configuration; provider credentials are validated only on use."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[1]

ModelRole = Literal["fast", "strong", "alt"]


class ConfigurationError(ValueError):
    """A selected provider is missing required configuration."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
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
    embed_model: str = "multilingual-e5-large"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"
    chroma_path: Path = REPO_ROOT / "chroma_data"
    vec_floor: float = Field(default=0.80, ge=-1, le=1)
    vec_ceil: float = Field(default=0.86, ge=-1, le=1)
    kb_known_fix: float = Field(default=0.60, ge=0, le=1)
    kb_similar: float = Field(default=0.40, ge=0, le=1)
    kb_vector_weight: float = Field(default=0.6, ge=0, le=1)
    kb_signature_weight: float = Field(default=0.4, ge=0, le=1)
    langsmith_tracing: bool = True
    langsmith_api_key: SecretStr = SecretStr("")
    langsmith_project: str = "flowmedic-dev"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    agent_version: str = "0.1.0"

    @model_validator(mode="after")
    def validate_retrieval(self) -> "Settings":
        """Keep hybrid scores bounded and routing thresholds ordered."""
        if abs(self.kb_vector_weight + self.kb_signature_weight - 1) > 1e-9:
            raise ValueError("KB vector and signature weights must sum to 1")
        if self.vec_floor >= self.vec_ceil:
            raise ValueError("VEC_FLOOR must be less than VEC_CEIL")
        if self.kb_similar > self.kb_known_fix:
            raise ValueError("KB_SIMILAR must not exceed KB_KNOWN_FIX")
        return self

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


# Small development calibration grid; ordering breaks accuracy ties in favor of
# round values and the original routing thresholds, before more aggressive choices.
RETRIEVAL_GRID: dict[str, tuple[float, ...]] = {
    "vec_floor": (0.80, 0.82),
    "vec_ceil": (0.88, 0.86),
    "kb_vector_weight": (0.5, 0.6, 0.4),
    "kb_known_fix": (0.80, 0.70, 0.60),
    "kb_similar": (0.60, 0.50, 0.40),
}
