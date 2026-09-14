import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.llm.errors import (
    LLMAuthenticationError,
    LLMInvalidResponseError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.llm.models import LLMMessage, LLMRequest
from app.llm.openai_compatible import OpenAICompatibleProvider


class ProviderOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)


def run(coroutine: object) -> object:
    return asyncio.run(coroutine)  # type: ignore[arg-type]


def make_request() -> LLMRequest:
    return LLMRequest(
        messages=(LLMMessage(role="user", content="A private business question"),),
        response_schema=ProviderOutput.model_json_schema(),
        schema_name="ProviderOutput",
        max_output_tokens=321,
        timeout_seconds=2,
    )


def make_provider(
    handler: httpx.MockTransport,
    *,
    api_key: str = "sk-private-test-key",
) -> OpenAICompatibleProvider:
    client = httpx.AsyncClient(transport=handler, base_url="https://llm.example/v1")
    return OpenAICompatibleProvider(
        provider_name="openai-compatible",
        base_url="https://unused.example/v1",
        api_key=SecretStr(api_key),
        model="vendor/model-v1",
        connect_timeout_seconds=1,
        client=client,
    )


def test_provider_sends_schema_token_limit_and_returns_usage() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "provider-request-1",
                "model": "vendor/model-v1",
                "choices": [{"message": {"content": '{"answer":"42"}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
            },
        )

    provider = make_provider(httpx.MockTransport(handler))
    completion = run(provider.complete(make_request()))

    payload = captured["payload"]
    assert captured["authorization"] == "Bearer sk-private-test-key"
    assert payload["model"] == "vendor/model-v1"  # type: ignore[index]
    assert payload["max_tokens"] == 321  # type: ignore[index]
    assert payload["response_format"]["type"] == "json_schema"  # type: ignore[index]
    assert payload["response_format"]["json_schema"]["strict"] is True  # type: ignore[index]
    assert completion.content == '{"answer":"42"}'  # type: ignore[union-attr]
    assert completion.request_id == "provider-request-1"  # type: ignore[union-attr]
    assert completion.usage.total_tokens == 14  # type: ignore[union-attr]
    assert "sk-private-test-key" not in repr(provider)


def test_local_compatible_provider_can_omit_authorization() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"answer":"local"}'}}]},
        )

    provider = make_provider(httpx.MockTransport(handler), api_key="")

    completion = run(provider.complete(make_request()))

    assert completion.content == '{"answer":"local"}'  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (401, LLMAuthenticationError),
        (429, LLMRateLimitError),
        (500, LLMUnavailableError),
        (504, LLMTimeoutError),
    ],
)
def test_provider_classifies_http_failures(
    status_code: int,
    error_type: type[Exception],
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text="upstream-secret-body")

    provider = make_provider(httpx.MockTransport(handler))

    with pytest.raises(error_type) as captured:
        run(provider.complete(make_request()))

    assert "upstream-secret-body" not in str(captured.value)
    assert "sk-private-test-key" not in str(captured.value)


def test_provider_classifies_transport_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private upstream details", request=request)

    provider = make_provider(httpx.MockTransport(handler))

    with pytest.raises(LLMTimeoutError) as captured:
        run(provider.complete(make_request()))

    assert captured.value.code == "LLM_TIMEOUT"
    assert "private upstream details" not in str(captured.value)


def test_provider_rejects_malformed_wire_response_without_leaking_body() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"private": "customer-row-data", "choices": []})

    provider = make_provider(httpx.MockTransport(handler))

    with pytest.raises(LLMInvalidResponseError) as captured:
        run(provider.complete(make_request()))

    assert captured.value.code == "LLM_INVALID_RESPONSE"
    assert "customer-row-data" not in str(captured.value)
