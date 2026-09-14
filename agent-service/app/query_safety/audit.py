import logging
from typing import Protocol, runtime_checkable

from app.query_safety.models import QueryAuditEvent

logger = logging.getLogger(__name__)


@runtime_checkable
class QueryAuditSink(Protocol):
    def record(self, event: QueryAuditEvent) -> None: ...


class InMemoryQueryAuditSink:
    def __init__(self) -> None:
        self._events: list[QueryAuditEvent] = []

    @property
    def events(self) -> tuple[QueryAuditEvent, ...]:
        return tuple(self._events)

    def record(self, event: QueryAuditEvent) -> None:
        self._events.append(event)


class LoggingQueryAuditSink:
    def record(self, event: QueryAuditEvent) -> None:
        logger.info("Safe query audit: %s", event.model_dump_json())
