"""Optional provider connectivity check: uv run python -m flowmedic.smoke."""

from time import perf_counter

from langchain_core.messages import BaseMessage

from flowmedic.config import ConfigurationError, ModelRole, get_settings
from flowmedic.llm import get_llm
from flowmedic.prompts import SMOKE_USER_V1
from flowmedic.tracing import run_config


def smoke_call(role: ModelRole) -> tuple[str, BaseMessage, float]:
    """Invoke one provider and return its model, displayed reply and latency."""
    llm = get_llm(role)
    started = perf_counter()
    reply = llm.invoke(
        SMOKE_USER_V1,
        config=run_config(prompt_version="SMOKE_USER_V1", run_name="smoke-test"),
    )
    return get_settings().model_name(role), reply, perf_counter() - started


def main() -> int:
    """Check every configured role; report failures and return a nonzero exit code."""
    settings = get_settings()
    if not (
        settings.langsmith_tracing and settings.langsmith_api_key.get_secret_value()
    ):
        print(
            "LangSmith tracing inactive: set LANGSMITH_TRACING=true "
            "and LANGSMITH_API_KEY."
        )
    print("role | provider | model | reply | latency")
    failed = False
    roles: tuple[ModelRole, ...] = ("fast", "strong", "alt")
    for role in roles:
        try:
            settings.provider_key(role)
        except ConfigurationError as exc:
            print(f"SKIP {role}: {exc}")
            continue
        try:
            model, reply, latency = smoke_call(role)
            print(
                f"{role} | {settings.provider_name(role)} | {model} | "
                f"{reply.content} | {latency:.2f}s"
            )
        except ConfigurationError as exc:
            print(f"FAIL {role}: {exc}")
            failed = True
        except Exception as exc:
            # Provider errors may embed credentials; display only the error type.
            print(f"FAIL {role}: {type(exc).__name__}; check provider configuration.")
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
