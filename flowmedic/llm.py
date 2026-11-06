"""Model factories; constructing a model never makes a network call."""

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableWithFallbacks
from langchain_openai import ChatOpenAI

from flowmedic.config import ConfigurationError, ModelRole, get_settings


def get_llm(role: ModelRole) -> BaseChatModel:
    """Build the selected model with consistent invocation settings and metadata."""
    if role not in ("fast", "strong", "alt"):
        raise ValueError(f"Unknown model role: {role!r}; use fast, strong or alt.")
    settings = get_settings()
    key = settings.provider_key(role)
    model = settings.model_name(role)
    metadata = {
        "model_role": role,
        "model": model,
        "agent_version": settings.agent_version,
    }
    if role == "strong":
        return ChatAnthropic(
            api_key=key,
            model_name=model,
            temperature=0,
            timeout=60,
            max_retries=2,
            metadata=metadata,
        )
    if role == "fast" and not settings.nebius_base_url.strip():
        raise ConfigurationError("Missing NEBIUS_BASE_URL for model role 'fast'.")
    return ChatOpenAI(
        api_key=key,
        model=model,
        base_url=settings.nebius_base_url if role == "fast" else None,
        temperature=0,
        timeout=60,
        max_retries=2,
        metadata=metadata,
    )


def get_llm_with_fallback(role: ModelRole) -> BaseChatModel | RunnableWithFallbacks:
    """Build strong → alt or fast → strong; both providers must be configured."""
    primary = get_llm(role)
    fallback: ModelRole | None = {"strong": "alt", "fast": "strong"}.get(role)
    if fallback is None:
        return primary
    return primary.with_fallbacks([get_llm(fallback)])
