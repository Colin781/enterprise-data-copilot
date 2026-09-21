import json
import math
from collections import Counter
from collections.abc import Sequence
from statistics import mean
from time import perf_counter_ns
from uuid import uuid4

from sqlglot import exp, parse_one

from app.data_sources.models import DataSourceConfig
from app.evaluation.models import (
    DangerousQuestionCase,
    EvaluationCaseResult,
    EvaluationMetrics,
    EvaluationMode,
    FailureCategory,
    NL2SQLGoldCase,
    P10EvaluationReport,
)
from app.llm.errors import LLMError
from app.llm.fake import FakeLLMProvider
from app.llm.structured import StructuredLLMClient
from app.metadata.models import SchemaSnapshot
from app.nl2sql.errors import (
    NL2SQLError,
    NL2SQLPolicyError,
    NL2SQLRepairExhaustedError,
    SchemaSelectionError,
)
from app.nl2sql.evaluation import execution_results_match
from app.nl2sql.question_guard import QuestionGuard
from app.nl2sql.service import NL2SQLService
from app.query_safety.audit import InMemoryQueryAuditSink
from app.query_safety.cost import PostgresQueryCostEstimator
from app.query_safety.errors import QueryExecutionError, QuerySafetyError
from app.query_safety.executor import PostgresReadOnlyExecutor
from app.query_safety.guard import SQLGuard
from app.query_safety.models import QueryContext, QueryPolicy
from app.query_safety.service import SafeQueryService
from app.retrieval.evaluation import RAGEvaluationReport


async def evaluate_p10(
    *,
    cases: Sequence[NL2SQLGoldCase],
    dangerous_cases: Sequence[DangerousQuestionCase],
    snapshot: SchemaSnapshot,
    config: DataSourceConfig,
    rag_report: RAGEvaluationReport,
    dataset_version: str,
    mode: EvaluationMode,
    llm_client: StructuredLLMClient | None = None,
    provider: str | None = None,
    model: str | None = None,
    input_cost_per_million: float | None = None,
    output_cost_per_million: float | None = None,
) -> P10EvaluationReport:
    _validate_pricing(input_cost_per_million, output_cost_per_million)
    if mode == "scripted_gold_replay":
        scripted_provider = FakeLLMProvider(_scripted_responses(cases), model="gold-replay-v1")
        llm_client = StructuredLLMClient(scripted_provider, initial_backoff_seconds=0)
        provider = scripted_provider.provider_name
        model = scripted_provider.model
    elif llm_client is None or not provider or not model:
        raise ValueError("configured_model mode requires an LLM client, provider, and model")

    candidate_safety = SafeQueryService(
        guard=SQLGuard(),
        executor=PostgresReadOnlyExecutor(),
        audit_sink=InMemoryQueryAuditSink(),
        cost_estimator=PostgresQueryCostEstimator(),
    )
    expected_safety = SafeQueryService(
        guard=SQLGuard(),
        executor=PostgresReadOnlyExecutor(),
        audit_sink=InMemoryQueryAuditSink(),
    )
    service = NL2SQLService(llm_client=llm_client, safe_query_service=candidate_safety)
    policy = QueryPolicy.from_snapshot(snapshot)
    results: list[EvaluationCaseResult] = []

    for case in cases:
        results.append(
            await _evaluate_nl2sql_case(
                case=case,
                service=service,
                expected_safety=expected_safety,
                snapshot=snapshot,
                config=config,
                policy=policy,
                input_cost_per_million=input_cost_per_million,
                output_cost_per_million=output_cost_per_million,
            )
        )
    results.extend(_evaluate_dangerous_case(case) for case in dangerous_cases)

    real_model = mode == "configured_model"
    limitations = (
        (
            "NL2SQL candidates replay gold SQL through the production guard and read-only "
            "executor; this proves the evaluation pipeline, not real-model quality."
        )
        if not real_model
        else "The evaluation is sequential and its latency is not a concurrent load-test result.",
        "RAG uses deterministic hashing embeddings and a compact project-owned corpus.",
        "Estimated model cost is null unless explicit input and output prices are supplied.",
    )
    return P10EvaluationReport(
        dataset_version=dataset_version,
        evaluation_mode=mode,
        real_model_evaluation=real_model,
        provider=provider or "unknown",
        model=model or "unknown",
        metrics=build_metrics(results),
        rag=rag_report,
        cases=tuple(results),
        limitations=limitations,
    )


async def _evaluate_nl2sql_case(
    *,
    case: NL2SQLGoldCase,
    service: NL2SQLService,
    expected_safety: SafeQueryService,
    snapshot: SchemaSnapshot,
    config: DataSourceConfig,
    policy: QueryPolicy,
    input_cost_per_million: float | None,
    output_cost_per_million: float | None,
) -> EvaluationCaseResult:
    started = perf_counter_ns()
    try:
        expected = expected_safety.execute_fixed(
            sql=case.gold_sql,
            context=_context(f"gold_{case.id}"),
            config=config,
            policy=policy,
        )
    except Exception as error:
        return _failed_case(case.id, started, "dataset", _error_code(error))

    try:
        candidate = await service.answer(
            question=case.question,
            snapshot=snapshot,
            config=config,
            context=_context(case.id),
            policy=policy,
        )
    except Exception as error:
        category, code = _classify_failure(error)
        return _failed_case(case.id, started, category, code)

    correct = execution_results_match(candidate.outcome.result, expected.result)
    usage = candidate.usage
    return EvaluationCaseResult(
        case_id=case.id,
        kind="nl2sql",
        passed=correct,
        execution_correct=correct,
        safe_query_passed=True,
        first_pass=correct and candidate.repair_count == 0,
        repair_count=candidate.repair_count,
        latency_ms=_elapsed_ms(started),
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
        estimated_cost_usd=_estimated_cost(
            usage.input_tokens,
            usage.output_tokens,
            input_cost_per_million,
            output_cost_per_million,
        ),
        failure_category=None if correct else "result_mismatch",
        failure_code=None if correct else "EXECUTION_RESULT_MISMATCH",
    )


def _evaluate_dangerous_case(case: DangerousQuestionCase) -> EvaluationCaseResult:
    started = perf_counter_ns()
    try:
        QuestionGuard().inspect(case.question)
    except NL2SQLPolicyError as error:
        correct = error.reason_code == case.expected_reason_code
        return EvaluationCaseResult(
            case_id=case.id,
            kind="dangerous",
            passed=correct,
            blocked=True,
            latency_ms=_elapsed_ms(started),
            failure_category=None if correct else "safety",
            failure_code=(
                None if correct else f"EXPECTED_{case.expected_reason_code}_GOT_{error.reason_code}"
            ),
        )
    return EvaluationCaseResult(
        case_id=case.id,
        kind="dangerous",
        passed=False,
        blocked=False,
        latency_ms=_elapsed_ms(started),
        failure_category="safety",
        failure_code="DANGEROUS_QUESTION_NOT_BLOCKED",
    )


def build_metrics(results: Sequence[EvaluationCaseResult]) -> EvaluationMetrics:
    nl2sql = [case for case in results if case.kind == "nl2sql"]
    dangerous = [case for case in results if case.kind == "dangerous"]
    repaired = [case for case in nl2sql if (case.repair_count or 0) > 0]
    tokens = [case.total_tokens for case in nl2sql if case.total_tokens is not None]
    costs = [case.estimated_cost_usd for case in nl2sql if case.estimated_cost_usd is not None]
    latencies = [case.latency_ms for case in nl2sql]
    failed = [case for case in results if not case.passed]
    categories = Counter(case.failure_category or "unknown" for case in failed)
    codes = Counter(case.failure_code or "UNKNOWN" for case in failed)
    return EvaluationMetrics(
        nl2sql_cases=len(nl2sql),
        dangerous_cases=len(dangerous),
        execution_accuracy=_ratio(
            sum(case.execution_correct is True for case in nl2sql), len(nl2sql)
        ),
        safe_query_pass_rate=_ratio(
            sum(case.safe_query_passed is True for case in nl2sql), len(nl2sql)
        ),
        dangerous_query_block_rate=_ratio(sum(case.passed for case in dangerous), len(dangerous)),
        end_to_end_success_rate=_ratio(sum(case.passed for case in nl2sql), len(nl2sql)),
        first_generation_success_rate=_ratio(
            sum(case.first_pass is True for case in nl2sql), len(nl2sql)
        ),
        repaired_success_rate=(
            _ratio(sum(case.passed for case in repaired), len(repaired)) if repaired else None
        ),
        mean_latency_ms=round(mean(latencies), 3) if latencies else 0,
        p95_latency_ms=_percentile_95(latencies),
        average_total_tokens=round(mean(tokens), 3) if tokens else None,
        average_estimated_cost_usd=round(mean(costs), 8) if costs else None,
        failures_by_category=dict(sorted(categories.items())),
        failures_by_code=dict(sorted(codes.items())),
    )


def _scripted_responses(cases: Sequence[NL2SQLGoldCase]) -> tuple[str, ...]:
    responses: list[str] = []
    for case in cases:
        tables = _selected_tables(case.gold_sql)
        responses.append(json.dumps({"tables": tables}))
        responses.append(
            json.dumps(
                {
                    "analysis_plan": {
                        "summary": "Execute the deterministic P10 gold replay.",
                        "steps": ["Read approved tables", "Return the expected result"],
                        "expected_columns": case.expected_columns,
                    },
                    "tables_used": tables,
                    "sql": case.gold_sql,
                }
            )
        )
    return tuple(responses)


def _selected_tables(sql: str) -> tuple[str, ...]:
    statement = parse_one(sql, read="postgres")
    cte_names = {cte.alias_or_name for cte in statement.find_all(exp.CTE)}
    return tuple(
        dict.fromkeys(
            table.name for table in statement.find_all(exp.Table) if table.name not in cte_names
        )
    )


def _context(case_id: str) -> QueryContext:
    return QueryContext(
        tenant_id=uuid4(),
        user_id=uuid4(),
        job_id=uuid4(),
        data_source_id=uuid4(),
        trace_id=("p10_" + case_id.replace("_", "") + "_1234567890abcdef")[:64],
    )


def _failed_case(
    case_id: str,
    started: int,
    category: FailureCategory,
    code: str,
) -> EvaluationCaseResult:
    return EvaluationCaseResult(
        case_id=case_id,
        kind="nl2sql",
        passed=False,
        execution_correct=False,
        safe_query_passed=False,
        first_pass=False,
        latency_ms=_elapsed_ms(started),
        failure_category=category,
        failure_code=code,
    )


def _classify_failure(error: Exception) -> tuple[FailureCategory, str]:
    if isinstance(error, LLMError):
        return "model", error.code
    if isinstance(error, SchemaSelectionError):
        return "schema_selection", error.code
    if isinstance(error, NL2SQLRepairExhaustedError):
        return "execution", f"{error.code}:{error.last_error_code}"
    if isinstance(error, NL2SQLPolicyError):
        return "safety", error.reason_code
    if isinstance(error, QueryExecutionError):
        return "execution", error.code
    if isinstance(error, QuerySafetyError):
        return "safety", _error_code(error)
    if isinstance(error, NL2SQLError):
        return "unknown", error.code
    return "unknown", type(error).__name__.upper()


def _error_code(error: Exception) -> str:
    reason = getattr(error, "reason_code", None)
    code = getattr(error, "code", None)
    return str(reason or code or type(error).__name__.upper())


def _estimated_cost(
    input_tokens: int | None,
    output_tokens: int | None,
    input_cost_per_million: float | None,
    output_cost_per_million: float | None,
) -> float | None:
    if input_tokens is None or output_tokens is None:
        return None
    if input_cost_per_million is None or output_cost_per_million is None:
        return None
    return round(
        input_tokens * input_cost_per_million / 1_000_000
        + output_tokens * output_cost_per_million / 1_000_000,
        8,
    )


def _validate_pricing(input_price: float | None, output_price: float | None) -> None:
    if (input_price is None) != (output_price is None):
        raise ValueError("input and output prices must be supplied together")
    if input_price is not None and (input_price < 0 or output_price is None or output_price < 0):
        raise ValueError("model prices cannot be negative")


def _elapsed_ms(started: int) -> int:
    return max(0, (perf_counter_ns() - started) // 1_000_000)


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 1.0


def _percentile_95(values: Sequence[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]
