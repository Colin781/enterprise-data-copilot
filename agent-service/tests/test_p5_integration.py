import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlglot import exp, parse_one

from app.data_sources.models import DataSourceConfig
from app.llm.fake import FakeLLMProvider
from app.llm.structured import StructuredLLMClient
from app.metadata.models import SchemaSnapshot
from app.nl2sql.evaluation import (
    ExecutionAccuracyReport,
    ExecutionCaseResult,
    execution_results_match,
)
from app.nl2sql.service import NL2SQLService
from app.query_safety.audit import InMemoryQueryAuditSink
from app.query_safety.cost import PostgresQueryCostEstimator
from app.query_safety.errors import QueryApprovalRequiredError
from app.query_safety.executor import PostgresReadOnlyExecutor
from app.query_safety.guard import SQLGuard
from app.query_safety.models import QueryContext, QueryPolicy
from app.query_safety.service import SafeQueryService
from app.settings import get_business_database_settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_P5_INTEGRATION") != "1",
        reason="set RUN_P5_INTEGRATION=1 to test NL2SQL against PostgreSQL",
    ),
]


@pytest.fixture
def config() -> DataSourceConfig:
    return DataSourceConfig.from_settings(get_business_database_settings())


@pytest.fixture
def snapshot() -> SchemaSnapshot:
    path = Path(__file__).parents[2] / "metadata/northwind-schema-v1.json"
    return SchemaSnapshot.model_validate_json(path.read_text(encoding="utf-8"))


def context(case_id: str) -> QueryContext:
    return QueryContext(
        tenant_id=uuid4(),
        user_id=uuid4(),
        job_id=uuid4(),
        data_source_id=uuid4(),
        trace_id=f"p5_{case_id}_1234567890abcdef",
    )


def selected_tables(sql: str) -> tuple[str, ...]:
    statement = parse_one(sql, read="postgres")
    cte_names = {cte.alias_or_name for cte in statement.find_all(exp.CTE)}
    return tuple(
        dict.fromkeys(
            table.name for table in statement.find_all(exp.Table) if table.name not in cte_names
        )
    )


def selection_response(tables: tuple[str, ...]) -> str:
    return json.dumps({"tables": tables})


def draft_response(case: dict[str, object], tables: tuple[str, ...]) -> str:
    return json.dumps(
        {
            "analysis_plan": {
                "summary": "Produce the requested Northwind analysis.",
                "steps": ["Read approved tables", "Calculate the requested result"],
                "expected_columns": case["expected_columns"],
            },
            "tables_used": tables,
            "sql": case["gold_sql"],
        }
    )


def test_all_fifteen_offline_candidates_match_gold_execution_results(
    config: DataSourceConfig,
    snapshot: SchemaSnapshot,
) -> None:
    root = Path(__file__).parents[2]
    cases = [
        json.loads(line)
        for line in (root / "evaluation/northwind/gold-v1.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    responses: list[str] = []
    for case in cases:
        tables = selected_tables(case["gold_sql"])
        responses.extend((selection_response(tables), draft_response(case, tables)))

    provider = FakeLLMProvider(responses)
    client = StructuredLLMClient(provider, initial_backoff_seconds=0)
    candidate_sink = InMemoryQueryAuditSink()
    candidate_safety = SafeQueryService(
        guard=SQLGuard(),
        executor=PostgresReadOnlyExecutor(),
        audit_sink=candidate_sink,
        cost_estimator=PostgresQueryCostEstimator(),
    )
    service = NL2SQLService(llm_client=client, safe_query_service=candidate_safety)
    expected_safety = SafeQueryService(
        guard=SQLGuard(),
        executor=PostgresReadOnlyExecutor(),
        audit_sink=InMemoryQueryAuditSink(),
    )
    policy = QueryPolicy.from_snapshot(snapshot)

    async def evaluate() -> ExecutionAccuracyReport:
        results: list[ExecutionCaseResult] = []
        for case in cases:
            candidate = await service.answer(
                question=case["question"],
                snapshot=snapshot,
                config=config,
                context=context(case["id"]),
                policy=policy,
            )
            expected = expected_safety.execute_fixed(
                sql=case["gold_sql"],
                context=context(f"gold_{case['id']}"),
                config=config,
                policy=policy,
            )
            results.append(
                ExecutionCaseResult(
                    case_id=case["id"],
                    correct=execution_results_match(candidate.outcome.result, expected.result),
                )
            )
        return ExecutionAccuracyReport.from_results(results)

    report = asyncio.run(evaluate())

    assert report.total_cases == 15
    assert report.correct_cases == 15
    assert report.accuracy == 1.0
    assert len(provider.requests) == 30
    assert len(candidate_sink.events) == 15
    assert all(event.status == "SUCCEEDED" for event in candidate_sink.events)
    assert all(event.planner_invoked for event in candidate_sink.events)
    assert all(event.estimated_total_cost is not None for event in candidate_sink.events)


def test_real_database_error_is_repaired_without_exposing_database_details(
    config: DataSourceConfig,
    snapshot: SchemaSnapshot,
) -> None:
    failing_sql = "SELECT 1 / 0 AS order_id FROM northwind.orders LIMIT 1"
    repaired_sql = "SELECT order_id FROM northwind.orders ORDER BY order_id LIMIT 1"
    tables = ("orders",)
    responses = [
        selection_response(tables),
        json.dumps(
            {
                "analysis_plan": {
                    "summary": "List an order.",
                    "steps": ["Read one order"],
                    "expected_columns": ["order_id"],
                },
                "tables_used": tables,
                "sql": failing_sql,
            }
        ),
        json.dumps(
            {
                "analysis_plan": {
                    "summary": "List an order.",
                    "steps": ["Read one order"],
                    "expected_columns": ["order_id"],
                },
                "tables_used": tables,
                "sql": repaired_sql,
            }
        ),
    ]
    provider = FakeLLMProvider(responses)
    sink = InMemoryQueryAuditSink()
    service = NL2SQLService(
        llm_client=StructuredLLMClient(provider, initial_backoff_seconds=0),
        safe_query_service=SafeQueryService(
            guard=SQLGuard(),
            executor=PostgresReadOnlyExecutor(),
            audit_sink=sink,
            cost_estimator=PostgresQueryCostEstimator(),
        ),
    )

    result = asyncio.run(
        service.answer(
            question="列出一个订单编号",
            snapshot=snapshot,
            config=config,
            context=context("repair"),
            policy=QueryPolicy.from_snapshot(snapshot),
        )
    )

    assert result.repair_count == 1
    assert [event.status for event in sink.events] == ["FAILED", "SUCCEEDED"]
    repair_payload = provider.requests[2].messages[-1].content
    assert "QUERY_EXECUTION_FAILED" in repair_payload
    assert "division by zero" not in repair_payload
    assert config.host not in repair_payload
    assert config.username not in repair_payload
    assert config.password.get_secret_value() not in repair_payload


def test_real_explain_cost_threshold_stops_query_before_execution(
    config: DataSourceConfig,
    snapshot: SchemaSnapshot,
) -> None:
    sql = "SELECT order_id FROM northwind.orders ORDER BY order_id LIMIT 5"
    tables = ("orders",)
    provider = FakeLLMProvider(
        [
            selection_response(tables),
            json.dumps(
                {
                    "analysis_plan": {
                        "summary": "List orders.",
                        "steps": ["Read orders"],
                        "expected_columns": ["order_id"],
                    },
                    "tables_used": tables,
                    "sql": sql,
                }
            ),
        ]
    )
    sink = InMemoryQueryAuditSink()
    service = NL2SQLService(
        llm_client=StructuredLLMClient(provider, initial_backoff_seconds=0),
        safe_query_service=SafeQueryService(
            guard=SQLGuard(),
            executor=PostgresReadOnlyExecutor(),
            audit_sink=sink,
            cost_estimator=PostgresQueryCostEstimator(),
        ),
    )

    with pytest.raises(QueryApprovalRequiredError):
        asyncio.run(
            service.answer(
                question="列出五个订单编号",
                snapshot=snapshot,
                config=config,
                context=context("cost"),
                policy=QueryPolicy.from_snapshot(snapshot, max_total_cost=0.0001),
            )
        )

    assert sink.events[0].status == "APPROVAL_REQUIRED"
    assert sink.events[0].planner_invoked is True
    assert sink.events[0].executor_invoked is False
    assert sink.events[0].estimated_total_cost is not None
