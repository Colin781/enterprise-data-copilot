from typing import Protocol, runtime_checkable

from app.llm.models import LLMCompletion, LLMRequest


@runtime_checkable
class LLMProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def model(self) -> str: ...

    async def complete(self, request: LLMRequest) -> LLMCompletion: ...

    async def aclose(self) -> None: ...
