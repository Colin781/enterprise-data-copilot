from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic

from app.metadata.models import SchemaSnapshot


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    snapshot: SchemaSnapshot
    expires_at: float


class SchemaMetadataCache:
    def __init__(self, ttl_seconds: int, clock: Callable[[], float] = monotonic) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: dict[tuple[str, str], _CacheEntry] = {}

    def get_or_load(
        self,
        source_id: str,
        schema_name: str,
        loader: Callable[[], SchemaSnapshot],
    ) -> SchemaSnapshot:
        key = (source_id, schema_name)
        now = self._clock()
        entry = self._entries.get(key)
        if entry is not None and now < entry.expires_at:
            return entry.snapshot

        snapshot = loader()
        self._entries[key] = _CacheEntry(snapshot, now + self._ttl_seconds)
        return snapshot

    def invalidate(self, source_id: str, schema_name: str) -> None:
        self._entries.pop((source_id, schema_name), None)
