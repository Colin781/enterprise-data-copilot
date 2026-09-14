import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.llm.errors import LLMError, LLMInvalidResponseError, LLMTimeoutError
from app.llm.models import LLMMessage, LLMRequest, StructuredLLMResult
from app.llm.provider import LLMProvider

logger = logging.getLogger(__name__)
StructuredOutputT = TypeVar("StructuredOutputT", bound=BaseModel)
Sleep = Callable[[float], Awaitable[None]]


class StructuredLLMClient:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        structured_output_mode: str = "json_schema",
        request_timeout_seconds: float = 30,
        max_output_tokens: int = 2_000,
        max_attempts: int = 3,
        invalid_response_retries: int = 1,
        initial_backoff_seconds: float = 0.25,
        max_backoff_seconds: float = 2,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if invalid_response_retries not in {0, 1}:
            raise ValueError("invalid_response_retries must be 0 or 1")
        self._provider = provider
        self._structured_output_mode = structured_output_mode
        self._request_timeout_seconds = request_timeout_seconds
        self._max_output_tokens = max_output_tokens
        self._max_attempts = max_attempts
        self._invalid_response_retries = invalid_response_retries
        self._initial_backoff_seconds = initial_backoff_seconds
        self._max_backoff_seconds = max_backoff_seconds
        self._sleep = sleep

    async def generate(
        self,
        *,
        messages: Sequence[LLMMessage],
        response_model: type[StructuredOutputT],
    ) -> StructuredLLMResult[StructuredOutputT]:
        request = LLMRequest(
            messages=tuple(messages),
            response_schema=response_model.model_json_schema(),
            schema_name=response_model.__name__[:64],
            structured_output_mode=self._structured_output_mode,
            max_output_tokens=self._max_output_tokens,
            timeout_seconds=self._request_timeout_seconds,
        )
        invalid_retries_used = 0

        for attempt in range(1, self._max_attempts + 1):
            try:
                async with asyncio.timeout(self._request_timeout_seconds):
                    completion = await self._provider.complete(request)
            except TimeoutError as exc:
                error = LLMTimeoutError()
                if not await self._retry(error, attempt):
                    raise error from exc
                continue
            except LLMError as error:
                if not await self._retry(error, attempt):
                    raise
                continue

            try:
                output = response_model.model_validate_json(completion.content)
            except ValidationError as exc:
                error = LLMInvalidResponseError(validation_issues=_safe_issues(exc))
                can_retry = (
                    invalid_retries_used < self._invalid_response_retries
                    and attempt < self._max_attempts
                )
                if not can_retry:
                    raise error from exc
                invalid_retries_used += 1
                await self._schedule_retry(error, attempt)
                continue

            return StructuredLLMResult[response_model](
                output=output,
                provider=self._provider.provider_name,
                model=completion.model,
                request_id=completion.request_id,
                attempts=attempt,
                usage=completion.usage,
            )

        raise AssertionError("The retry loop ended without a result or a classified error.")

    async def aclose(self) -> None:
        await self._provider.aclose()

    async def __aenter__(self) -> "StructuredLLMClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def _retry(self, error: LLMError, attempt: int) -> bool:
        if not error.retryable or attempt >= self._max_attempts:
            return False
        await self._schedule_retry(error, attempt)
        return True

    async def _schedule_retry(self, error: LLMError, attempt: int) -> None:
        delay = min(
            self._initial_backoff_seconds * (2 ** (attempt - 1)),
            self._max_backoff_seconds,
        )
        logger.warning(
            "Language model retry scheduled: code=%s provider=%s model=%s attempt=%d "
            "delay_seconds=%.3f",
            error.code,
            self._provider.provider_name,
            self._provider.model,
            attempt,
            delay,
        )
        await self._sleep(delay)


def _safe_issues(error: ValidationError) -> tuple[str, ...]:
    issues: list[str] = []
    for item in error.errors(include_input=False, include_url=False):
        location = ".".join(str(part) for part in item["loc"]) or "$"
        issues.append(f"{location}:{item['type']}")
    return tuple(issues)
