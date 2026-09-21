from pathlib import Path

import pytest

from app.evaluation.datasets import load_dangerous_cases, load_nl2sql_cases
from app.evaluation.models import DangerousQuestionCase, EvaluationCaseResult
from app.evaluation.runner import build_metrics
from app.metadata.models import SchemaSnapshot
from app.nl2sql.errors import NL2SQLPolicyError
from app.nl2sql.question_guard import QuestionGuard
from app.query_safety.guard import SQLGuard
from app.query_safety.models import QueryPolicy

ROOT = Path(__file__).parents[2]
NL2SQL_CASES = ROOT / "evaluation/northwind/nl2sql-gold-v2.jsonl"
DANGEROUS_CASES = ROOT / "evaluation/northwind/dangerous-questions-v1.jsonl"


def test_p10_datasets_meet_converged_size_and_schema_requirements() -> None:
    nl2sql = load_nl2sql_cases(NL2SQL_CASES)
    dangerous = load_dangerous_cases(DANGEROUS_CASES)

    assert len(nl2sql) == 55
    assert len(dangerous) == 20
    assert len({case.id for case in nl2sql}) == len(nl2sql)
    assert len({case.id for case in dangerous}) == len(dangerous)
    assert all(case.expected_columns for case in nl2sql)
    assert all(case.tags for case in (*nl2sql, *dangerous))


def test_all_p10_gold_sql_is_accepted_by_the_production_guard() -> None:
    snapshot = SchemaSnapshot.model_validate_json(
        (ROOT / "metadata/northwind-schema-v1.json").read_text(encoding="utf-8")
    )
    policy = QueryPolicy.from_snapshot(snapshot)

    guarded = [
        SQLGuard().inspect(case.gold_sql, policy) for case in load_nl2sql_cases(NL2SQL_CASES)
    ]

    assert len(guarded) == 55
    assert all(query.referenced_tables for query in guarded)


@pytest.mark.parametrize("case", load_dangerous_cases(DANGEROUS_CASES), ids=lambda case: case.id)
def test_dangerous_question_dataset_is_blocked_with_expected_reason(
    case: DangerousQuestionCase,
) -> None:
    with pytest.raises(NL2SQLPolicyError) as captured:
        QuestionGuard().inspect(case.question)

    assert captured.value.reason_code == case.expected_reason_code


def test_metrics_separate_accuracy_safety_repair_cost_and_failure_taxonomy() -> None:
    results = [
        EvaluationCaseResult(
            case_id="nw001",
            kind="nl2sql",
            passed=True,
            execution_correct=True,
            safe_query_passed=True,
            first_pass=True,
            repair_count=0,
            latency_ms=10,
            total_tokens=100,
            estimated_cost_usd=0.01,
        ),
        EvaluationCaseResult(
            case_id="nw002",
            kind="nl2sql",
            passed=True,
            execution_correct=True,
            safe_query_passed=True,
            first_pass=False,
            repair_count=1,
            latency_ms=20,
            total_tokens=200,
            estimated_cost_usd=0.02,
        ),
        EvaluationCaseResult(
            case_id="nw003",
            kind="nl2sql",
            passed=False,
            execution_correct=False,
            safe_query_passed=True,
            first_pass=False,
            repair_count=0,
            latency_ms=30,
            failure_category="result_mismatch",
            failure_code="EXECUTION_RESULT_MISMATCH",
        ),
        EvaluationCaseResult(
            case_id="nw004",
            kind="nl2sql",
            passed=False,
            execution_correct=False,
            safe_query_passed=False,
            first_pass=False,
            latency_ms=40,
            failure_category="model",
            failure_code="LLM_TIMEOUT",
        ),
        EvaluationCaseResult(
            case_id="nw005",
            kind="nl2sql",
            passed=False,
            execution_correct=False,
            safe_query_passed=False,
            first_pass=False,
            latency_ms=50,
            failure_category="execution",
            failure_code="QUERY_TIMEOUT",
        ),
        EvaluationCaseResult(
            case_id="dq001", kind="dangerous", passed=True, blocked=True, latency_ms=1
        ),
        EvaluationCaseResult(
            case_id="dq002", kind="dangerous", passed=True, blocked=True, latency_ms=1
        ),
        EvaluationCaseResult(
            case_id="dq003",
            kind="dangerous",
            passed=False,
            blocked=False,
            latency_ms=1,
            failure_category="safety",
            failure_code="DANGEROUS_QUESTION_NOT_BLOCKED",
        ),
    ]

    metrics = build_metrics(results)

    assert metrics.execution_accuracy == 0.4
    assert metrics.safe_query_pass_rate == 0.6
    assert metrics.dangerous_query_block_rate == pytest.approx(0.6667)
    assert metrics.end_to_end_success_rate == 0.4
    assert metrics.first_generation_success_rate == 0.2
    assert metrics.repaired_success_rate == 1.0
    assert metrics.mean_latency_ms == 30
    assert metrics.p95_latency_ms == 50
    assert metrics.average_total_tokens == 150
    assert metrics.average_estimated_cost_usd == 0.015
    assert metrics.failures_by_category == {
        "execution": 1,
        "model": 1,
        "result_mismatch": 1,
        "safety": 1,
    }


def test_duplicate_dataset_ids_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.jsonl"
    line = (
        '{"id":"nw001","question":"q","gold_sql":"SELECT 1 AS value",'
        '"expected_columns":["value"],"tags":["simple"]}'
    )
    path.write_text(f"{line}\n{line}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="ids must be unique"):
        load_nl2sql_cases(path)
