"""Model construction is offline; all invocations are mocked except live tests."""

from unittest.mock import patch

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableWithFallbacks
from langchain_openai import ChatOpenAI

from flowmedic.config import ConfigurationError, ModelRole
from flowmedic.llm import get_llm, get_llm_with_fallback
from flowmedic.smoke import main, smoke_call
from flowmedic.tracing import run_config


@pytest.fixture
def providers(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in {
        "ANTHROPIC_API_KEY": "synthetic-anthropic-key",
        "ANTHROPIC_MODEL": "test-claude",
        "NEBIUS_API_KEY": "synthetic-nebius-key",
        "NEBIUS_BASE_URL": "https://nebius.example.invalid/v1",
        "NEBIUS_MODEL": "test-nebius",
        "OPENAI_API_KEY": "synthetic-openai-key",
        "OPENAI_MODEL": "test-openai",
    }.items():
        monkeypatch.setenv(name, value)


@pytest.mark.parametrize(
    ("role", "model_class", "name"),
    [
        ("fast", ChatOpenAI, "test-nebius"),
        ("strong", ChatAnthropic, "test-claude"),
        ("alt", ChatOpenAI, "test-openai"),
    ],
)
def test_model_selection(
    providers: None, role: ModelRole, model_class: type, name: str
) -> None:
    model = get_llm(role)
    assert isinstance(model, model_class)
    assert (
        model.model_name == name
        if isinstance(model, ChatOpenAI)
        else model.model == name
    )
    assert model.temperature == 0
    assert model.max_retries == 2
    assert model.metadata["model_role"] == role
    assert model.metadata["model"] == name
    if role == "fast":
        assert str(model.openai_api_base) == "https://nebius.example.invalid/v1"
    if isinstance(model, ChatAnthropic):
        assert model.default_request_timeout == 60
    else:
        assert model.request_timeout == 60


def test_missing_key_error_on_model_use() -> None:
    with pytest.raises(ConfigurationError, match="NEBIUS_API_KEY"):
        get_llm("fast")


@pytest.mark.parametrize("field", ["NEBIUS_MODEL", "NEBIUS_BASE_URL"])
def test_missing_nebius_configuration(
    providers: None, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    monkeypatch.delenv(field)
    with pytest.raises(ConfigurationError, match=field):
        get_llm("fast")


@pytest.mark.parametrize(("role", "fallback"), [("fast", "strong"), ("strong", "alt")])
def test_fallback_invokes_secondary(
    providers: None, role: ModelRole, fallback: str
) -> None:
    runnable = get_llm_with_fallback(role)
    assert isinstance(runnable, RunnableWithFallbacks)
    assert runnable.fallbacks[0].metadata["model_role"] == fallback
    primary_type = type(runnable.runnable)
    fallback_type = type(runnable.fallbacks[0])
    with (
        patch.object(
            primary_type, "invoke", side_effect=RuntimeError("synthetic failure")
        ),
        patch.object(fallback_type, "invoke", return_value=AIMessage(content="OK")),
    ):
        assert runnable.invoke("test").content == "OK"


def test_alt_has_no_fallback(providers: None) -> None:
    assert isinstance(get_llm_with_fallback("alt"), ChatOpenAI)


def test_run_config() -> None:
    config = run_config("SC-001", "SMOKE_USER_V1", "smoke-test")
    assert config["metadata"] == {
        "case_id": "SC-001",
        "prompt_version": "SMOKE_USER_V1",
        "agent_version": "0.1.0",
        "run_name": "smoke-test",
    }
    assert "flowmedic" in config["tags"]
    assert config["run_name"] == "smoke-test"


def test_smoke_call_is_traced(providers: None) -> None:
    with patch.object(
        ChatAnthropic, "invoke", return_value=AIMessage(content="OK")
    ) as call:
        name, reply, latency = smoke_call("strong")
    assert name == "test-claude"
    assert reply.content == "OK"
    assert latency >= 0
    assert call.call_args.kwargs["config"]["run_name"] == "smoke-test"


def test_smoke_skips_unconfigured_roles(capsys: pytest.CaptureFixture[str]) -> None:
    assert main() == 0
    output = capsys.readouterr().out
    for role, key in [("fast", "NEBIUS"), ("strong", "ANTHROPIC"), ("alt", "OPENAI")]:
        assert f"SKIP {role}: Missing {key}_API_KEY" in output


@pytest.mark.live
def test_strong_live_smoke() -> None:
    name, reply, latency = smoke_call("strong")
    assert name
    assert reply.content
    assert latency >= 0
