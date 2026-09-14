from collections import deque
from collections.abc import Iterable

from app.llm.models import LLMCompletion, LLMRequest


class FakeLLMProvider:
    def __init__(
        self,
        responses: Iterable[str | LLMCompletion | Exception],
        *,
        model: str = "fake-model",
    ) -> None:
        self._responses = deque(responses)
        self._model = model
        self.requests: list[LLMRequest] = []

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, request: LLMRequest) -> LLMCompletion:
        self.requests.append(request)
        if not self._responses:
            raise AssertionError("Fake LLM has no scripted response remaining.")

        response = self._responses.popleft()
        if isinstance(response, Exception):
            raise response
        if isinstance(response, LLMCompletion):
            return response
        return LLMCompletion(content=response, model=self.model)

    async def aclose(self) -> None:
        return None
