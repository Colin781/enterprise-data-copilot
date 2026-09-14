import asyncio
import logging

import pytest
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.llm.errors import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMInvalidResponseError,
    LLMTimeoutError,
)
from app.llm.factory import create_structured_llm_client
from app.llm.fake import FakeLLMProvider
from app.llm.models import LLMMessage
from app.llm.provider import LLMProvider
from app.llm.structured import StructuredLLMClient
from app.settings import LLMSettings


class ExampleOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    score: int = Field(ge=0, le=100)


MESSAGES = [LLMMessage(role="user", content="Summarize the quarterly result.")]


def run(coroutine: object) -> object:
    return asyncio.run(coroutine)  # type: ignore[arg-type]


def test_fake_provider_satisfies_protocol_and_returns_pydantic_output() -> None:
    provider = FakeLLMProvider(['{"summary":"Sales increased.","score":92}'])
    client = StructuredLLMClient(provider, initial_backoff_seconds=0)

    result = run(client.generate(messages=MESSAGES, response_model=ExampleOutput))

    assert isinstance(provider, LLMProvider)
    assert result.output == ExampleOutput(summary="Sales increased.", score=92)  # type: ignore[union-attr]
    assert result.provider == "fake"  # type: ignore[union-attr]
    assert result.attempts == 1  # type: ignore[union-attr]
    assert provider.requests[0].response_schema["additionalProperties"] is False


def test_invalid_json_is_retried_once_then_succeeds() -> None:
    provider = FakeLLMProvider(["not-json", '{"summary":"Recovered.","score":80}'])
    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    client = StructuredLLMClient(
        provider,
        max_attempts=5,
        invalid_response_retries=1,
        initial_backoff_seconds=0.1,
        sleep=record_sleep,
    )

    result = run(client.generate(messages=MESSAGES, response_model=ExampleOutput))

    assert result.output.summary == "Recovered."  # type: ignore[union-attr]
    assert result.attempts == 2  # type: ignore[union-attr]
    assert len(provider.requests) == 2
    assert delays == [0.1]


def test_second_invalid_response_returns_safe_locatable_error_without_more_retries() -> None:
    secret_response = '{"summary":"api-key-super-secret","score":999}'
    provider = FakeLLMProvider(["not-json", secret_response, '{"summary":"unused","score":1}'])
    client = StructuredLLMClient(
        provider,
        max_attempts=5,
        invalid_response_retries=1,
        initial_backoff_seconds=0,
    )

    with pytest.raises(LLMInvalidResponseError) as captured:
        run(client.generate(messages=MESSAGES, response_model=ExampleOutput))

    assert captured.value.code == "LLM_INVALID_RESPONSE"
    assert captured.value.validation_issues == ("score:less_than_equal",)
    assert "api-key-super-secret" not in str(captured.value)
    assert len(provider.requests) == 2


def test_timeout_is_retried_with_exponential_backoff_then_classified() -> None:
    provider = FakeLLMProvider([TimeoutError(), TimeoutError(), TimeoutError()])
    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    client = StructuredLLMClient(
        provider,
        max_attempts=3,
        initial_backoff_seconds=0.1,
        max_backoff_seconds=1,
        sleep=record_sleep,
    )

    with pytest.raises(LLMTimeoutError) as captured:
        run(client.generate(messages=MESSAGES, response_model=ExampleOutput))

    assert captured.value.code == "LLM_TIMEOUT"
    assert captured.value.retryable is True
    assert delays == [0.1, 0.2]
    assert len(provider.requests) == 3


def test_non_retryable_provider_error_is_not_retried() -> None:
    provider = FakeLLMProvider([LLMAuthenticationError(), '{"summary":"unused","score":1}'])
    client = StructuredLLMClient(provider, initial_backoff_seconds=0)

    with pytest.raises(LLMAuthenticationError):
        run(client.generate(messages=MESSAGES, response_model=ExampleOutput))

    assert len(provider.requests) == 1


def test_retry_logs_do_not_include_prompt_or_model_response(
    caplog: pytest.LogCaptureFixture,
) -> None:
    prompt_secret = "postgresql://user:password@private-db/customer"
    response_secret = '{"summary":"sk-secret-value","score":999}'
    provider = FakeLLMProvider([response_secret, response_secret])
    client = StructuredLLMClient(provider, initial_backoff_seconds=0)

    with caplog.at_level(logging.WARNING), pytest.raises(LLMInvalidResponseError):
        run(
            client.generate(
                messages=[LLMMessage(role="user", content=prompt_secret)],
                response_model=ExampleOutput,
            )
        )

    rendered = caplog.text
    assert prompt_secret not in rendered
    assert "sk-secret-value" not in rendered
    assert "LLM_INVALID_RESPONSE" in rendered


def test_request_repr_hides_prompt_and_schema() -> None:
    provider = FakeLLMProvider(['{"summary":"ok","score":1}'])
    client = StructuredLLMClient(provider, initial_backoff_seconds=0)

    run(
        client.generate(
            messages=[LLMMessage(role="user", content="confidential-business-payload")],
            response_model=ExampleOutput,
        )
    )

    rendered = repr(provider.requests[0])
    assert "confidential-business-payload" not in rendered
    assert "properties" not in rendered


def test_model_can_be_switched_with_environment_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "vendor/new-model")
    settings = LLMSettings(_env_file=None, api_key=SecretStr("test-key"))

    assert settings.model == "vendor/new-model"
    assert "test-key" not in repr(settings)


def test_openrouter_requires_a_non_empty_api_key() -> None:
    settings = LLMSettings(_env_file=None, provider="openrouter", api_key=SecretStr(""))

    with pytest.raises(LLMConfigurationError) as captured:
        create_structured_llm_client(settings)

    assert captured.value.code == "LLM_CONFIGURATION_ERROR"
