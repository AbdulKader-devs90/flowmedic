"""Shared LangChain run metadata and explicit LangSmith configuration."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import ParamSpec, TypeVar

from langchain_core.runnables import RunnableConfig
from langchain_core.tracers.langchain import LangChainTracer
from langsmith import Client, trace

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


_case_id: ContextVar[str | None] = ContextVar("tool_case_id", default=None)


@contextmanager
def tool_context(case_id: str) -> Iterator[None]:
    """Propagate a scenario ID through nested deterministic tool spans."""
    token = _case_id.set(case_id)
    try:
        yield
    finally:
        _case_id.reset(token)


P = ParamSpec("P")
T = TypeVar("T")


def traced_tool(function: Callable[P, T]) -> Callable[P, T]:
    """Trace deterministic tools without uploading raw log arguments or outputs."""
    from functools import wraps

    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        settings = get_settings()
        key = settings.langsmith_api_key.get_secret_value()
        if not settings.langsmith_tracing or not key:
            return function(*args, **kwargs)
        with trace(
            name=function.__qualname__,
            run_type="tool",
            inputs={},
            project_name=settings.langsmith_project,
            client=Client(api_key=key, api_url=settings.langsmith_endpoint),
            metadata={
                "case_id": kwargs.get("case_id", _case_id.get()),
                "prompt_version": "deterministic-v1",
                "agent_version": settings.agent_version,
                "model": (
                    settings.embed_model
                    if settings.vector_backend == "pinecone"
                    else "all-MiniLM-L6-v2"
                )
                if function.__module__ == "flowmedic.tools.knowledge_repo"
                else "none",
            },
        ):
            return function(*args, **kwargs)

    return wrapped
