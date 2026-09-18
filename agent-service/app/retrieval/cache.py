from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from uuid import UUID

from app.retrieval.models import RetrievalMode, RetrievalResult


@dataclass(frozen=True, slots=True)
class _Entry:
    result: RetrievalResult
    expires_at: float


class RetrievalCache:
    def __init__(self, ttl_seconds: int = 300, clock: Callable[[], float] = monotonic) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: dict[tuple[UUID, str, str, RetrievalMode, int], _Entry] = {}

    def get(
        self, tenant_id: UUID, query: str, revision: str, mode: RetrievalMode, limit: int
    ) -> RetrievalResult | None:
        key = (tenant_id, query, revision, mode, limit)
        entry = self._entries.get(key)
        if entry is None:
            return None
        if self._clock() >= entry.expires_at:
            self._entries.pop(key, None)
            return None
        return entry.result

    def put(self, tenant_id: UUID, result: RetrievalResult, limit: int) -> None:
        key = (tenant_id, result.query, result.corpus_revision, result.mode, limit)
        self._entries[key] = _Entry(result, self._clock() + self._ttl_seconds)

    def invalidate_tenant(self, tenant_id: UUID) -> None:
        self._entries = {key: value for key, value in self._entries.items() if key[0] != tenant_id}
