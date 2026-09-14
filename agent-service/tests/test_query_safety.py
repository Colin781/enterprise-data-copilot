import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.data_sources.models import DataSourceConfig
from app.metadata.models import SchemaSnapshot, TableMetadata
from app.query_safety.audit import InMemoryQueryAuditSink
from app.query_safety.errors import (
    QueryAuditError,
    QueryExecutionError,
    SQLPolicyViolationError,
)
from app.query_safety.executor import QueryExecutor, _bounded_result
from app.query_safety.factory import create_query_policy
from app.query_safety.fixed import FIXED_TOP_CUSTOMERS_SQL
from app.query_safety.guard import SQLGuard
from app.query_safety.models import (
    GuardedQuery,
    QueryContext,
    QueryExecutionResult,
    QueryPolicy,
)
from app.query_safety.service import SafeQueryService
from app.settings import QuerySafetySettings


@pytest.fixture
def policy() -> QueryPolicy:
    return QueryPolicy(
        allowed_schema="northwind",
        allowed_tables=frozenset(
            {"categories", "customers", "order_details", "orders", "products"}
        ),
        max_rows=100,
        max_columns=20,
        max_result_bytes=10_000,
    )


@pytest.fixture
def config() -> DataSourceConfig:
    return DataSourceConfig(
        source_id="northwind-demo",
        host="database.internal",
        port=5432,
        database="northwind",
        username="northwind_reader",
        password=SecretStr("do-not-log"),
        allowed_schema="northwind",
    )


@pytest.fixture
def context() -> QueryContext:
    return QueryContext(
        tenant_id=uuid4(),
        user_id=uuid4(),
        job_id=uuid4(),
        data_source_id=uuid4(),
        trace_id="trace_1234567890abcdef",
    )


class CountingExecutor:
    def __init__(
        self,
        result: QueryExecutionResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.calls = 0
        self.last_query: GuardedQuery | None = None
        self._result = result or QueryExecutionResult(
            columns=("customer", "revenue"),
            rows=({"customer": "Acme", "revenue": "100.00"},),
            returned_row_count=1,
            serialized_bytes=64,
            truncated=False,
        )
        self._error = error

    def execute(
        self,
        query: GuardedQuery,
        config: DataSourceConfig,
        policy: QueryPolicy,
    ) -> QueryExecutionResult:
        self.calls += 1
        self.last_query = query
        if self._error:
            raise self._error
        return self._result


def make_service(
    executor: QueryExecutor,
    audit_sink: InMemoryQueryAuditSink,
) -> SafeQueryService:
    return SafeQueryService(guard=SQLGuard(), executor=executor, audit_sink=audit_sink)


def test_fixed_select_is_normalized_bounded_executed_and_audited(
    policy: QueryPolicy,
    config: DataSourceConfig,
    context: QueryContext,
) -> None:
    executor = CountingExecutor()
    audit_sink = InMemoryQueryAuditSink()
    service = make_service(executor, audit_sink)

    outcome = service.execute_fixed(
        sql=FIXED_TOP_CUSTOMERS_SQL,
        context=context,
        config=config,
        policy=policy,
    )

    assert isinstance(executor, QueryExecutor)
    assert executor.calls == 1
    assert executor.last_query is not None
    assert executor.last_query.bounded_sql.endswith("LIMIT 101")
    assert executor.last_query.referenced_tables == (
        "northwind.customers",
        "northwind.order_details",
        "northwind.orders",
    )
    assert outcome.result.returned_row_count == 1
    assert outcome.audit.status == "SUCCEEDED"
    assert outcome.audit.executor_invoked is True
    assert audit_sink.events == (outcome.audit,)
    assert FIXED_TOP_CUSTOMERS_SQL not in outcome.audit.model_dump_json()
    assert "Acme" not in outcome.audit.model_dump_json()


@pytest.mark.parametrize(
    ("sql", "reason_code"),
    [
        ("", "EMPTY_QUERY"),
        ("SELECT 'unterminated", "SQL_PARSE_ERROR"),
        ("DELETE FROM northwind.orders", "NON_READ_ONLY_STATEMENT"),
        ("SELECT 1; DROP TABLE northwind.orders", "MULTIPLE_STATEMENTS"),
        ("SELECT * INTO TEMP copied FROM northwind.orders", "FORBIDDEN_SQL_OPERATION"),
        ("SELECT * FROM northwind.orders FOR UPDATE", "FORBIDDEN_SQL_OPERATION"),
        ("SELECT * FROM restricted.private_notes", "CROSS_SCHEMA_REFERENCE"),
        ("SELECT * FROM northwind.unknown_table", "TABLE_NOT_ALLOWED"),
        ("SELECT pg_sleep(3)", "FORBIDDEN_FUNCTION"),
        ("SELECT private_business_function()", "FUNCTION_NOT_ALLOWED"),
    ],
)
def test_dangerous_sql_never_reaches_executor_and_is_audited(
    sql: str,
    reason_code: str,
    policy: QueryPolicy,
    config: DataSourceConfig,
    context: QueryContext,
) -> None:
    executor = CountingExecutor()
    audit_sink = InMemoryQueryAuditSink()
    service = make_service(executor, audit_sink)

    with pytest.raises(SQLPolicyViolationError) as captured:
        service.execute_fixed(sql=sql, context=context, config=config, policy=policy)

    assert captured.value.reason_code == reason_code
    assert executor.calls == 0
    assert len(audit_sink.events) == 1
    assert audit_sink.events[0].status == "REJECTED"
    assert audit_sink.events[0].reason_code == reason_code
    assert audit_sink.events[0].executor_invoked is False
    if sql:
        assert sql not in audit_sink.events[0].model_dump_json()


def test_cte_can_only_reference_allowed_physical_tables(policy: QueryPolicy) -> None:
    guarded = SQLGuard().inspect(
        "WITH recent AS (SELECT order_id FROM northwind.orders) SELECT * FROM recent",
        policy,
    )

    assert guarded.referenced_tables == ("northwind.orders",)


def test_executor_failure_is_audited_with_safe_error_code(
    policy: QueryPolicy,
    config: DataSourceConfig,
    context: QueryContext,
) -> None:
    executor = CountingExecutor(error=QueryExecutionError())
    audit_sink = InMemoryQueryAuditSink()
    service = make_service(executor, audit_sink)

    with pytest.raises(QueryExecutionError):
        service.execute_fixed(
            sql=FIXED_TOP_CUSTOMERS_SQL,
            context=context,
            config=config,
            policy=policy,
        )

    assert executor.calls == 1
    assert audit_sink.events[0].status == "FAILED"
    assert audit_sink.events[0].reason_code == "QUERY_EXECUTION_FAILED"
    assert audit_sink.events[0].executor_invoked is True


def test_audit_failure_prevents_a_successful_result_from_being_returned(
    policy: QueryPolicy,
    config: DataSourceConfig,
    context: QueryContext,
) -> None:
    class BrokenAuditSink:
        def record(self, _: object) -> None:
            raise OSError("private audit destination")

    service = SafeQueryService(
        guard=SQLGuard(),
        executor=CountingExecutor(),
        audit_sink=BrokenAuditSink(),  # type: ignore[arg-type]
    )

    with pytest.raises(QueryAuditError) as captured:
        service.execute_fixed(
            sql=FIXED_TOP_CUSTOMERS_SQL,
            context=context,
            config=config,
            policy=policy,
        )

    assert "private audit destination" not in str(captured.value)


def test_result_builder_enforces_row_and_byte_limits() -> None:
    policy = QueryPolicy(
        allowed_schema="northwind",
        allowed_tables=frozenset({"customers"}),
        max_rows=2,
        max_columns=5,
        max_result_bytes=80,
    )
    raw_rows: list[tuple[Any, ...]] = [
        ("first customer with a long name",),
        ("second customer with a long name",),
        ("third customer",),
    ]

    result = _bounded_result(("customer",), raw_rows, policy)

    assert result.returned_row_count < len(raw_rows)
    assert result.serialized_bytes <= policy.max_result_bytes
    assert result.truncated is True
    assert "first customer" not in repr(result)


def test_policy_limits_are_centralized_in_environment_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUERY_SAFETY_MAX_ROWS", "7")
    settings = QuerySafetySettings(_env_file=None)
    snapshot = SchemaSnapshot(
        source_id="northwind-demo",
        schema_name="northwind",
        schema_version="sha256:test",
        dataset_version="test",
        tables=[TableMetadata(name="orders", columns=[])],
    )

    policy = create_query_policy(snapshot, settings)

    assert policy.max_rows == 7
    assert policy.max_columns == 50


def test_existing_gold_sql_baseline_is_accepted_by_guard() -> None:
    project_root = Path(__file__).parents[2]
    snapshot = SchemaSnapshot.model_validate_json(
        (project_root / "metadata/northwind-schema-v1.json").read_text(encoding="utf-8")
    )
    cases = [
        json.loads(line)
        for line in (project_root / "evaluation/northwind/gold-v1.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    policy = QueryPolicy.from_snapshot(snapshot)

    guarded = [SQLGuard().inspect(case["gold_sql"], policy) for case in cases]

    assert len(guarded) == 15
    assert all(query.query_fingerprint.startswith("sha256:") for query in guarded)
