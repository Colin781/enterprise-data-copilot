from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from app.llm.errors import (
    LLMAuthenticationError,
    LLMInvalidResponseError,
    LLMRateLimitError,
    LLMRequestRejectedError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.llm.models import LLMCompletion, LLMRequest, LLMTokenUsage


class _WireMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str = Field(min_length=1)


class _WireChoice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: _WireMessage


class _WireUsage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class _WireCompletion(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    model: str | None = None
    choices: list[_WireChoice] = Field(min_length=1)
    usage: _WireUsage = Field(default_factory=_WireUsage)


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        provider_name: str,
        base_url: str,
        api_key: SecretStr,
        model: str,
        connect_timeout_seconds: float,
        app_name: str | None = None,
        site_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._provider_name = provider_name
        self._api_key = api_key
        self._model = model
        self._connect_timeout_seconds = connect_timeout_seconds
        self._app_name = app_name
        self._site_url = site_url
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(base_url=base_url.rstrip("/"))

    def __repr__(self) -> str:
        return f"{type(self).__name__}(provider_name={self.provider_name!r}, model={self.model!r})"

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, request: LLMRequest) -> LLMCompletion:
        headers = {"Content-Type": "application/json"}
        api_key = self._api_key.get_secret_value().strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if self._app_name:
            headers["X-Title"] = self._app_name
        if self._site_url:
            headers["HTTP-Referer"] = self._site_url

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [message.model_dump() for message in request.messages],
            "max_tokens": request.max_output_tokens,
            "response_format": self._response_format(request),
        }
        timeout = httpx.Timeout(
            request.timeout_seconds,
            connect=min(self._connect_timeout_seconds, request.timeout_seconds),
        )

        try:
            response = await self._client.post(
                "/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError() from exc
        except httpx.NetworkError as exc:
            raise LLMUnavailableError() from exc

        self._raise_for_status(response.status_code)
        try:
            wire = _WireCompletion.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise LLMInvalidResponseError() from exc

        usage = LLMTokenUsage(
            input_tokens=wire.usage.prompt_tokens,
            output_tokens=wire.usage.completion_tokens,
            total_tokens=wire.usage.total_tokens,
        )
        return LLMCompletion(
            content=wire.choices[0].message.content,
            model=wire.model or self.model,
            request_id=wire.id or response.headers.get("x-request-id"),
            usage=usage,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    def _response_format(request: LLMRequest) -> dict[str, Any]:
        if request.structured_output_mode == "json_object":
            return {"type": "json_object"}
        return {
            "type": "json_schema",
            "json_schema": {
                "name": request.schema_name,
                "strict": True,
                "schema": request.response_schema,
            },
        }

    @staticmethod
    def _raise_for_status(status_code: int) -> None:
        if 200 <= status_code < 300:
            return
        if status_code in {401, 403}:
            raise LLMAuthenticationError()
        if status_code in {408, 504}:
            raise LLMTimeoutError()
        if status_code == 429:
            raise LLMRateLimitError()
        if status_code >= 500:
            raise LLMUnavailableError()
        raise LLMRequestRejectedError()
