"""Shared LangChain run metadata and explicit LangSmith configuration."""

from langchain_core.runnables import RunnableConfig
from langchain_core.tracers.langchain import LangChainTracer
from langsmith import Client

from flowmedic.config import get_settings


def run_config(
    case_id: str | None = None,
    prompt_version: str | None = None,
    run_name: str | None = None,
) -> RunnableConfig:
    """Return trace context; model factories attach the actual model identifier."""
    settings = get_settings()
    config: RunnableConfig = {
        "tags": ["flowmedic", f"agent:{settings.agent_version}"],
        "metadata": {
            "case_id": case_id,
            "prompt_version": prompt_version,
            "agent_version": settings.agent_version,
            "run_name": run_name,
        },
    }
    if run_name is not None:
        config["run_name"] = run_name
    key = settings.langsmith_api_key.get_secret_value()
    if settings.langsmith_tracing and key.strip():
        config["callbacks"] = [
            LangChainTracer(
                project_name=settings.langsmith_project,
                client=Client(api_key=key, api_url=settings.langsmith_endpoint),
            )
        ]
    return config
