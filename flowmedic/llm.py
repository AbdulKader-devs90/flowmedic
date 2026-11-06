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
    provider = settings.provider_name(role)
    key = settings.provider_key(role)
    model = settings.model_name(role)
    metadata = {
        "model_role": role,
        "provider": provider,
        "model": model,
        "agent_version": settings.agent_version,
    }
    if provider == "anthropic":
        return ChatAnthropic(
            api_key=key,
            model_name=model,
            temperature=0,
            timeout=60,
            max_retries=2,
            metadata=metadata,
        )
    if provider == "nebius" and not settings.nebius_base_url.strip():
        raise ConfigurationError(
            f"Missing NEBIUS_BASE_URL for provider 'nebius' (role '{role}')."
        )
    return ChatOpenAI(
        api_key=key,
        model=model,
        base_url=settings.nebius_base_url if provider == "nebius" else None,
        temperature=0,
        timeout=60,
        max_retries=2,
        metadata=metadata,
    )


def get_llm_with_fallback(role: ModelRole) -> BaseChatModel | RunnableWithFallbacks:
    """Build the configured fallback only when its provider has a key."""
    primary = get_llm(role)
    fallback: ModelRole | None = {"strong": "alt", "fast": "strong"}.get(role)
    if fallback is None:
        return primary
    try:
        get_settings().provider_key(fallback)
    except ConfigurationError:
        return primary
    return primary.with_fallbacks([get_llm(fallback)])
