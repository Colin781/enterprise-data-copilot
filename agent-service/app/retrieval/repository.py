import hashlib
import math
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from app.retrieval.embeddings import cosine_similarity, lexical_tokens
from app.retrieval.errors import RetrievalStoreError
from app.retrieval.models import (
    MetricChunk,
    PendingMetricChunk,
    RankedChunk,
    SourceType,
    StoredMetricDocument,
)

_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


class MetricKnowledgeRepository(Protocol):
    def replace_document(
        self,
        *,
        tenant_id: UUID,
        title: str,
        source_type: SourceType,
        source_name: str,
        content_sha256: str,
        chunks: Sequence[PendingMetricChunk],
        created_by: UUID | None = None,
    ) -> StoredMetricDocument: ...

    def lexical_search(
        self, tenant_id: UUID, query: str, limit: int
    ) -> tuple[RankedChunk, ...]: ...

    def vector_search(
        self, tenant_id: UUID, embedding: Sequence[float], limit: int
    ) -> tuple[RankedChunk, ...]: ...

    def corpus_revision(self, tenant_id: UUID) -> str: ...


@dataclass(slots=True)
class _DocumentEntry:
    document: StoredMetricDocument
    chunks: tuple[MetricChunk, ...]


class InMemoryMetricKnowledgeRepository:
    def __init__(self) -> None:
        self._entries: dict[tuple[UUID, str], _DocumentEntry] = {}
        self._revisions: Counter[UUID] = Counter()
        self.lexical_calls = 0
        self.vector_calls = 0

    def replace_document(
        self,
        *,
        tenant_id: UUID,
        title: str,
        source_type: SourceType,
        source_name: str,
        content_sha256: str,
        chunks: Sequence[PendingMetricChunk],
        created_by: UUID | None = None,
    ) -> StoredMetricDocument:
        del created_by
        if not chunks:
            raise ValueError("at least one chunk is required")
        key = (tenant_id, title)
        previous = self._entries.get(key)
        version = 1 if previous is None else previous.document.version + 1
        now = datetime.now(UTC)
        document_id = uuid4()
        document = StoredMetricDocument(
            id=document_id,
            tenant_id=tenant_id,
            title=title,
            version=version,
            status="ACTIVE",
            source_type=source_type,
            source_name=source_name,
            content_sha256=content_sha256,
            chunk_count=len(chunks),
            created_at=now,
            updated_at=now,
        )
        stored_chunks = tuple(
            MetricChunk(
                id=uuid4(),
                tenant_id=tenant_id,
                document_id=document_id,
                document_title=title,
                document_version=version,
                section_key=chunk.section_key,
                section_title=chunk.section_title,
                source_locator=chunk.source_locator,
                ordinal=chunk.ordinal,
                content=chunk.content,
                embedding=chunk.embedding,
            )
            for chunk in chunks
        )
        self._entries[key] = _DocumentEntry(document, stored_chunks)
        self._revisions[tenant_id] += 1
        return document

    def lexical_search(self, tenant_id: UUID, query: str, limit: int) -> tuple[RankedChunk, ...]:
        self.lexical_calls += 1
        query_counts = Counter(lexical_tokens(query))
        ranked = []
        for chunk in self._tenant_chunks(tenant_id):
            document_counts = Counter(
                lexical_tokens(f"{chunk.document_title} {chunk.section_title} {chunk.content}")
            )
            score = _cosine_counts(query_counts, document_counts)
            primary_label = chunk.section_title.split(maxsplit=1)[0].lower()
            if primary_label and primary_label in query.lower():
                score += 1.0
            if score > 0:
                ranked.append(RankedChunk(chunk=chunk, score=score))
        ranked.sort(key=lambda item: (-item.score, item.chunk.ordinal, str(item.chunk.id)))
        return tuple(ranked[:limit])

    def vector_search(
        self, tenant_id: UUID, embedding: Sequence[float], limit: int
    ) -> tuple[RankedChunk, ...]:
        self.vector_calls += 1
        ranked = [
            RankedChunk(chunk=chunk, score=cosine_similarity(embedding, chunk.embedding))
            for chunk in self._tenant_chunks(tenant_id)
        ]
        ranked = [item for item in ranked if item.score > 0]
        ranked.sort(key=lambda item: (-item.score, item.chunk.ordinal, str(item.chunk.id)))
        return tuple(ranked[:limit])

    def corpus_revision(self, tenant_id: UUID) -> str:
        return f"memory:{self._revisions[tenant_id]}"

    def _tenant_chunks(self, tenant_id: UUID) -> tuple[MetricChunk, ...]:
        return tuple(
            chunk
            for (entry_tenant, _), entry in self._entries.items()
            if entry_tenant == tenant_id
            for chunk in entry.chunks
        )


@dataclass(frozen=True, slots=True)
class PlatformKnowledgeDatabaseConfig:
    host: str
    port: int
    database: str
    username: str
    password: str
    schema: str = "copilot"
    connect_timeout_seconds: int = 3

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.schema):
            raise ValueError("schema must be a simple PostgreSQL identifier")

    def connection_parameters(self) -> dict[str, object]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.username,
            "password": self.password,
            "connect_timeout": self.connect_timeout_seconds,
        }


class PostgresMetricKnowledgeRepository:
    def __init__(
        self,
        config: PlatformKnowledgeDatabaseConfig,
        *,
        connection_factory: Callable[..., psycopg.Connection] = psycopg.connect,
    ) -> None:
        self._config = config
        self._connect = connection_factory
        self._documents = f"{config.schema}.metric_documents"
        self._chunks = f"{config.schema}.metric_chunks"

    def replace_document(
        self,
        *,
        tenant_id: UUID,
        title: str,
        source_type: SourceType,
        source_name: str,
        content_sha256: str,
        chunks: Sequence[PendingMetricChunk],
        created_by: UUID | None = None,
    ) -> StoredMetricDocument:
        if not chunks:
            raise ValueError("at least one chunk is required")
        document_id = uuid4()
        now = datetime.now(UTC)
        try:
            with (
                self._connect(
                    **self._config.connection_parameters(), row_factory=dict_row
                ) as connection,
                connection.transaction(),
            ):
                current = connection.execute(
                    f"SELECT id, version FROM {self._documents} "
                    "WHERE tenant_id = %s AND title = %s AND status = 'ACTIVE' FOR UPDATE",
                    (tenant_id, title),
                ).fetchone()
                version = 1 if current is None else int(current["version"]) + 1
                if current is not None:
                    connection.execute(
                        f"UPDATE {self._documents} SET status = 'SUPERSEDED', updated_at = %s "
                        "WHERE id = %s",
                        (now, current["id"]),
                    )
                    connection.execute(
                        f"DELETE FROM {self._chunks} WHERE document_id = %s",
                        (current["id"],),
                    )
                connection.execute(
                    f"INSERT INTO {self._documents} "
                    "(id, tenant_id, title, version, status, source_type, source_name, "
                    "content_sha256, created_by, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, 'ACTIVE', %s, %s, %s, %s, %s, %s)",
                    (
                        document_id,
                        tenant_id,
                        title,
                        version,
                        source_type,
                        source_name,
                        content_sha256,
                        created_by,
                        now,
                        now,
                    ),
                )
                with connection.cursor() as cursor:
                    cursor.executemany(
                        f"INSERT INTO {self._chunks} "
                        "(id, tenant_id, document_id, document_version, section_key, "
                        "section_title, source_locator, ordinal, content, embedding, created_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s)",
                        [
                            (
                                uuid4(),
                                tenant_id,
                                document_id,
                                version,
                                chunk.section_key,
                                chunk.section_title,
                                chunk.source_locator,
                                chunk.ordinal,
                                chunk.content,
                                _vector_literal(chunk.embedding),
                                now,
                            )
                            for chunk in chunks
                        ],
                    )
        except psycopg.Error as error:
            raise RetrievalStoreError() from error
        return StoredMetricDocument(
            id=document_id,
            tenant_id=tenant_id,
            title=title,
            version=version,
            status="ACTIVE",
            source_type=source_type,
            source_name=source_name,
            content_sha256=content_sha256,
            chunk_count=len(chunks),
            created_at=now,
            updated_at=now,
        )

    def lexical_search(self, tenant_id: UUID, query: str, limit: int) -> tuple[RankedChunk, ...]:
        sql = (
            f"SELECT c.*, d.title AS document_title, "
            "ts_rank_cd(c.search_vector, websearch_to_tsquery('simple', %s)) AS score "
            f"FROM {self._chunks} c JOIN {self._documents} d ON d.id = c.document_id "
            "WHERE c.tenant_id = %s AND d.status = 'ACTIVE' "
            "AND c.search_vector @@ websearch_to_tsquery('simple', %s) "
            "ORDER BY score DESC, c.ordinal ASC LIMIT %s"
        )
        return self._search(sql, (query, tenant_id, query, limit))

    def vector_search(
        self, tenant_id: UUID, embedding: Sequence[float], limit: int
    ) -> tuple[RankedChunk, ...]:
        literal = _vector_literal(embedding)
        sql = (
            f"SELECT c.*, d.title AS document_title, "
            "1 - (c.embedding <=> %s::vector) AS score "
            f"FROM {self._chunks} c JOIN {self._documents} d ON d.id = c.document_id "
            "WHERE c.tenant_id = %s AND d.status = 'ACTIVE' "
            "ORDER BY c.embedding <=> %s::vector, c.ordinal ASC LIMIT %s"
        )
        return self._search(sql, (literal, tenant_id, literal, limit))

    def corpus_revision(self, tenant_id: UUID) -> str:
        try:
            with self._connect(
                **self._config.connection_parameters(), row_factory=dict_row
            ) as connection:
                row = connection.execute(
                    f"SELECT count(*) AS count, COALESCE(sum(version), 0) AS versions, "
                    "COALESCE(max(updated_at)::text, '') AS updated "
                    f"FROM {self._documents} WHERE tenant_id = %s AND status = 'ACTIVE'",
                    (tenant_id,),
                ).fetchone()
        except psycopg.Error as error:
            raise RetrievalStoreError() from error
        material = f"{row['count']}:{row['versions']}:{row['updated']}"
        return f"sha256:{hashlib.sha256(material.encode()).hexdigest()}"

    def _search(self, sql: str, parameters: tuple[object, ...]) -> tuple[RankedChunk, ...]:
        try:
            with self._connect(
                **self._config.connection_parameters(), row_factory=dict_row
            ) as connection:
                rows = connection.execute(sql, parameters).fetchall()
        except psycopg.Error as error:
            raise RetrievalStoreError() from error
        return tuple(
            RankedChunk(
                chunk=MetricChunk(
                    id=row["id"],
                    tenant_id=row["tenant_id"],
                    document_id=row["document_id"],
                    document_title=row["document_title"],
                    document_version=row["document_version"],
                    section_key=row["section_key"],
                    section_title=row["section_title"],
                    source_locator=row["source_locator"],
                    ordinal=row["ordinal"],
                    content=row["content"],
                    embedding=_parse_vector(row["embedding"]),
                ),
                score=float(row["score"]),
            )
            for row in rows
        )


def _cosine_counts(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    numerator = sum(count * right[token] for token, count in left.items())
    left_norm = math.sqrt(sum(count * count for count in left.values()))
    right_norm = math.sqrt(sum(count * count for count in right.values()))
    return numerator / (left_norm * right_norm) if numerator else 0.0


def _vector_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(f"{value:.10g}" for value in values) + "]"


def _parse_vector(value: object) -> tuple[float, ...]:
    if isinstance(value, str):
        return tuple(float(item) for item in value.strip("[]").split(",") if item)
    return tuple(float(item) for item in value)  # type: ignore[arg-type]
