import os
from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest

from app.retrieval.embeddings import HashingEmbeddingProvider
from app.retrieval.repository import (
    PlatformKnowledgeDatabaseConfig,
    PostgresMetricKnowledgeRepository,
)
from app.retrieval.service import MetricRetrievalService

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_P6_INTEGRATION") != "1",
        reason="set RUN_P6_INTEGRATION=1 to test RAG against PostgreSQL and pgvector",
    ),
]


@pytest.fixture
def repository() -> Iterator[PostgresMetricKnowledgeRepository]:
    config = PlatformKnowledgeDatabaseConfig(
        host=os.getenv("PLATFORM_DB_HOST", "localhost"),
        port=int(os.getenv("PLATFORM_DB_PORT", "5432")),
        database=os.getenv("PLATFORM_DB_NAME", "copilot_platform"),
        username=os.getenv("PLATFORM_DB_USER", "copilot"),
        password=os.getenv("PLATFORM_DB_PASSWORD", "change-me-platform"),
        schema="p6_test",
    )
    with psycopg.connect(**config.connection_parameters(), autocommit=True) as connection:
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        connection.execute("DROP SCHEMA IF EXISTS p6_test CASCADE")
        connection.execute("CREATE SCHEMA p6_test")
        connection.execute(
            """
            CREATE TABLE p6_test.metric_documents (
                id uuid PRIMARY KEY, tenant_id uuid NOT NULL, title varchar(240) NOT NULL,
                version integer NOT NULL, status varchar(32) NOT NULL,
                source_type varchar(16) NOT NULL, source_name varchar(255) NOT NULL,
                content_sha256 varchar(64) NOT NULL, created_by uuid,
                created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE p6_test.metric_chunks (
                id uuid PRIMARY KEY, tenant_id uuid NOT NULL, document_id uuid NOT NULL
                    REFERENCES p6_test.metric_documents(id) ON DELETE CASCADE,
                document_version integer NOT NULL, section_key varchar(500) NOT NULL,
                section_title varchar(500) NOT NULL, source_locator varchar(120) NOT NULL,
                ordinal integer NOT NULL, content text NOT NULL,
                search_vector tsvector GENERATED ALWAYS AS (
                    to_tsvector(
                        'simple', coalesce(section_title, '') || ' ' || coalesce(content, '')
                    )
                ) STORED,
                embedding vector(64) NOT NULL, created_at timestamptz NOT NULL
            )
            """
        )
    yield PostgresMetricKnowledgeRepository(config)
    with psycopg.connect(**config.connection_parameters(), autocommit=True) as connection:
        connection.execute("DROP SCHEMA IF EXISTS p6_test CASCADE")


def test_postgres_full_text_pgvector_tenant_scope_and_version_invalidation(
    repository: PostgresMetricKnowledgeRepository,
) -> None:
    retrieval = MetricRetrievalService(
        repository=repository,
        embedding_provider=HashingEmbeddingProvider(64),
    )
    tenant_id, other_tenant = uuid4(), uuid4()
    first = retrieval.ingest(
        tenant_id=tenant_id,
        title="指标口径",
        source_name="metrics.md",
        source_type="MARKDOWN",
        payload=b"# Revenue\n\nrevenue equals quantity times unit price after discount.",
    )

    lexical = retrieval.retrieve(tenant_id=tenant_id, query="revenue", mode="lexical")
    vector = retrieval.retrieve(tenant_id=tenant_id, query="quantity price", mode="vector")
    hybrid = retrieval.retrieve(tenant_id=tenant_id, query="revenue price", mode="hybrid")
    isolated = retrieval.retrieve(tenant_id=other_tenant, query="revenue", mode="hybrid")

    assert lexical.hits and vector.hits and hybrid.hits
    assert isolated.hits == ()
    assert lexical.citations[0].document_version == 1

    second = retrieval.ingest(
        tenant_id=tenant_id,
        title="指标口径",
        source_name="metrics.md",
        source_type="MARKDOWN",
        payload=b"# Margin\n\nmargin equals revenue minus product cost.",
    )

    assert second.version == first.version + 1
    assert retrieval.retrieve(tenant_id=tenant_id, query="margin", mode="hybrid").hits
    assert retrieval.retrieve(tenant_id=tenant_id, query="quantity", mode="lexical").hits == ()
