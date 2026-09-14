import os
from pathlib import Path
from uuid import uuid4

import pytest

from app.data_sources.models import DataSourceConfig
from app.metadata.models import SchemaSnapshot
from app.query_safety.audit import InMemoryQueryAuditSink
from app.query_safety.errors import QueryResultLimitError, SQLPolicyViolationError
from app.query_safety.executor import PostgresReadOnlyExecutor, QueryExecutor
from app.query_safety.fixed import FIXED_TOP_CUSTOMERS_SQL
from app.query_safety.guard import SQLGuard
from app.query_safety.models import GuardedQuery, QueryContext, QueryExecutionResult, QueryPolicy
from app.query_safety.service import SafeQueryService
from app.settings import get_business_database_settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_SAFETY_INTEGRATION") != "1",
        reason="set RUN_SAFETY_INTEGRATION=1 to test the safe query slice",
    ),
]


class CountingExecutor:
    def __init__(self, inner: QueryExecutor) -> None:
        self.inner = inner
        self.calls = 0

    def execute(
        self,
        query: GuardedQuery,
        config: DataSourceConfig,
        policy: QueryPolicy,
    ) -> QueryExecutionResult:
        self.calls += 1
        return self.inner.execute(query, config, policy)


@pytest.fixture
def config() -> DataSourceConfig:
    return DataSourceConfig.from_settings(get_business_database_settings())


@pytest.fixture
def snapshot() -> SchemaSnapshot:
    snapshot_path = Path(__file__).parents[2] / "metadata/northwind-schema-v1.json"
    return SchemaSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))


@pytest.fixture
def context() -> QueryContext:
    return QueryContext(
        tenant_id=uuid4(),
        user_id=uuid4(),
        job_id=uuid4(),
        data_source_id=uuid4(),
        trace_id="safety_1234567890abcdef",
    )


def make_service(executor: QueryExecutor, sink: InMemoryQueryAuditSink) -> SafeQueryService:
    return SafeQueryService(guard=SQLGuard(), executor=executor, audit_sink=sink)


def test_fixed_sql_completes_guard_readonly_execution_limits_and_audit(
    config: DataSourceConfig,
    snapshot: SchemaSnapshot,
    context: QueryContext,
) -> None:
    policy = QueryPolicy.from_snapshot(snapshot, max_rows=100, max_columns=20)
    executor = CountingExecutor(PostgresReadOnlyExecutor())
    sink = InMemoryQueryAuditSink()

    outcome = make_service(executor, sink).execute_fixed(
        sql=FIXED_TOP_CUSTOMERS_SQL,
        context=context,
        config=config,
        policy=policy,
    )

    assert executor.calls == 1
    assert outcome.result.columns == ("customer", "revenue")
    assert outcome.result.returned_row_count == 5
    assert outcome.result.truncated is False
    assert outcome.audit.status == "SUCCEEDED"
    assert outcome.audit.returned_rows == 5
    assert sink.events == (outcome.audit,)


def test_real_query_result_is_truncated_to_row_and_byte_limits(
    config: DataSourceConfig,
    snapshot: SchemaSnapshot,
    context: QueryContext,
) -> None:
    policy = QueryPolicy.from_snapshot(
        snapshot,
        max_rows=2,
        max_columns=20,
        max_result_bytes=80,
    )
    sink = InMemoryQueryAuditSink()

    outcome = make_service(PostgresReadOnlyExecutor(), sink).execute_fixed(
        sql=FIXED_TOP_CUSTOMERS_SQL,
        context=context,
        config=config,
        policy=policy,
    )

    assert outcome.result.returned_row_count <= 2
    assert outcome.result.serialized_bytes <= 80
    assert outcome.result.truncated is True
    assert outcome.audit.result_truncated is True


def test_too_many_result_columns_fails_and_is_audited(
    config: DataSourceConfig,
    snapshot: SchemaSnapshot,
    context: QueryContext,
) -> None:
    policy = QueryPolicy.from_snapshot(snapshot, max_columns=1)
    sink = InMemoryQueryAuditSink()

    with pytest.raises(QueryResultLimitError):
        make_service(PostgresReadOnlyExecutor(), sink).execute_fixed(
            sql=FIXED_TOP_CUSTOMERS_SQL,
            context=context,
            config=config,
            policy=policy,
        )

    assert sink.events[0].status == "FAILED"
    assert sink.events[0].reason_code == "QUERY_RESULT_LIMIT_EXCEEDED"


@pytest.mark.parametrize(
    "dangerous_sql",
    [
        "DELETE FROM northwind.orders",
        "SELECT * FROM restricted.private_notes",
        "SELECT pg_sleep(3)",
    ],
)
def test_dangerous_sql_reaches_real_executor_zero_times(
    dangerous_sql: str,
    config: DataSourceConfig,
    snapshot: SchemaSnapshot,
    context: QueryContext,
) -> None:
    policy = QueryPolicy.from_snapshot(snapshot)
    executor = CountingExecutor(PostgresReadOnlyExecutor())
    sink = InMemoryQueryAuditSink()

    with pytest.raises(SQLPolicyViolationError):
        make_service(executor, sink).execute_fixed(
            sql=dangerous_sql,
            context=context,
            config=config,
            policy=policy,
        )

    assert executor.calls == 0
    assert sink.events[0].status == "REJECTED"
    assert sink.events[0].executor_invoked is False
