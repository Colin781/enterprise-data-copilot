import asyncio
from collections.abc import Coroutine, Sequence
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlglot import exp, parse_one

from app.agent.charting import build_chart_spec
from app.agent.state import AgentState
from app.data_sources.models import DataSourceConfig
from app.llm.models import LLMMessage
from app.llm.structured import StructuredLLMClient
from app.metadata.introspection import PostgresSchemaIntrospector
from app.metadata.models import SchemaSnapshot
from app.nl2sql.errors import NL2SQLPolicyError, SchemaSelectionError
from app.nl2sql.models import NL2SQLDraft
from app.nl2sql.prompts import generation_messages, repair_messages, selection_messages
from app.nl2sql.question_guard import QuestionGuard
from app.nl2sql.table_references import normalize_reported_tables
from app.observability import SQL_REJECTIONS
from app.query_safety.cost import QueryCostEstimator
from app.query_safety.errors import SQLPolicyViolationError
from app.query_safety.executor import QueryExecutor
from app.query_safety.guard import SQLGuard
from app.query_safety.models import GuardedQuery, QueryPolicy
from app.retrieval.service import MetricRetrievalService


class ConfidentTableSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tables: tuple[str, ...] = Field(min_length=1, max_length=6)
    confidence: float = Field(ge=0, le=1)


class NorthwindAgentActions:
    """Production P5/P6 adapters behind the durable P7 graph nodes."""

    def __init__(
        self,
        *,
        llm_client: StructuredLLMClient,
        retrieval: MetricRetrievalService,
        data_source: DataSourceConfig,
        introspector: PostgresSchemaIntrospector,
        guard: SQLGuard,
        cost_estimator: QueryCostEstimator,
        executor: QueryExecutor,
        max_total_cost: float = 10_000,
        max_plan_rows: int = 100_000,
        minimum_confidence: float = 0.65,
        controlled_columns: frozenset[str] = frozenset(
            {"customers.contact_name", "employees.first_name", "employees.last_name"}
        ),
    ) -> None:
        self._llm = llm_client
        self._retrieval = retrieval
        self._data_source = data_source
        self._introspector = introspector
        self._guard = guard
        self._cost_estimator = cost_estimator
        self._executor = executor
        self._max_total_cost = max_total_cost
        self._max_plan_rows = max_plan_rows
        self._minimum_confidence = minimum_confidence
        self._controlled_columns = controlled_columns
        self._question_guard = QuestionGuard()

    def classify(self, state: AgentState) -> AgentState:
        try:
            question = self._question_guard.inspect(state["question"])
        except NL2SQLPolicyError as error:
            SQL_REJECTIONS.labels(error.reason_code).inc()
            return AgentState(
                sql_risk="blocked",
                risk_reasons=[error.reason_code],
                error_code=error.reason_code,
            )
        knowledge_markers = ("定义", "口径", "什么是", "how is", "definition")
        intent = (
            "knowledge"
            if any(marker in question.lower() for marker in knowledge_markers)
            else "hybrid"
        )
        return AgentState(intent=intent, error_code=None)

    def retrieve_metrics(self, state: AgentState) -> AgentState:
        result = self._retrieval.retrieve(
            tenant_id=UUID(state["tenant_id"]), query=state["question"], mode="hybrid"
        )
        context = [
            {
                "content": hit.content,
                "citation": hit.citation.model_dump(mode="json"),
            }
            for hit in result.hits
        ]
        return AgentState(
            metric_context=context,
            citations=[citation.model_dump(mode="json") for citation in result.citations],
            error_code=(
                "RAG_INSUFFICIENT_EVIDENCE"
                if state.get("intent") == "knowledge" and not result.should_answer
                else None
            ),
        )

    def select_schema(self, state: AgentState) -> AgentState:
        snapshot = self._introspector.inspect(self._data_source)
        policy = QueryPolicy.from_snapshot(
            snapshot,
            max_total_cost=self._max_total_cost,
            max_plan_rows=self._max_plan_rows,
        )
        messages = selection_messages(state["question"], snapshot)
        messages = (
            (
                messages[0][0],
                messages[0][1]
                + " Return a confidence number from 0 to 1 alongside the selected tables.",
            ),
            messages[1],
        )
        result = _run(
            self._llm.generate(
                messages=_messages(messages),
                response_model=ConfidentTableSelection,
            )
        )
        selected = tuple(dict.fromkeys(result.output.tables))
        if (
            not selected
            or len(selected) != len(result.output.tables)
            or not set(selected).issubset(policy.allowed_tables)
        ):
            raise SchemaSelectionError()
        restricted = policy.restrict_to_tables(frozenset(selected))
        return AgentState(
            candidate_tables=list(selected),
            selection_confidence=result.output.confidence,
            schema_snapshot=snapshot.model_dump(mode="json"),
            query_policy=restricted.model_dump(mode="json"),
        )

    def generate_sql(self, state: AgentState) -> AgentState:
        snapshot = SchemaSnapshot.model_validate(state["schema_snapshot"])
        policy = QueryPolicy.model_validate(state["query_policy"])
        base = generation_messages(
            state["question"], snapshot, tuple(state["candidate_tables"]), policy
        )
        prompts = base
        if state.get("sql") and state.get("error_code"):
            prompts = repair_messages(
                base,
                previous_sql=state["sql"],
                safe_error_code=state["error_code"],
            )
        result = _run(self._llm.generate(messages=_messages(prompts), response_model=NL2SQLDraft))
        reported_tables = normalize_reported_tables(
            result.output.tables_used, allowed_schema=policy.allowed_schema
        )
        if not set(reported_tables).issubset(state["candidate_tables"]):
            raise SchemaSelectionError()
        return AgentState(
            sql=result.output.sql,
            analysis_plan=result.output.analysis_plan.model_dump(mode="json"),
            attempts=state.get("attempts", 0) + 1,
            error_code=None,
        )

    def guard_sql(self, state: AgentState) -> AgentState:
        policy = QueryPolicy.model_validate(state["query_policy"])
        try:
            guarded = self._guard.inspect(state["sql"], policy)
        except SQLPolicyViolationError as error:
            SQL_REJECTIONS.labels(error.reason_code).inc()
            return AgentState(
                sql_risk="repair",
                risk_reasons=[error.reason_code],
                error_code=error.reason_code,
            )
        controlled = self._controlled_references(guarded.normalized_sql)
        estimate = self._cost_estimator.estimate(guarded, self._data_source)
        reasons = []
        if estimate.total_cost > policy.max_total_cost:
            reasons.append("TOTAL_COST_LIMIT_EXCEEDED")
        if estimate.plan_rows > policy.max_plan_rows:
            reasons.append("PLAN_ROWS_LIMIT_EXCEEDED")
        if controlled:
            reasons.append("CONTROLLED_SENSITIVE_COLUMN")
        if state.get("selection_confidence", 1.0) < self._minimum_confidence:
            reasons.append("LOW_MODEL_CONFIDENCE")
        return AgentState(
            sql_risk="approval" if reasons else "safe",
            risk_reasons=reasons,
            sql_fingerprint=guarded.query_fingerprint,
            guarded_query=guarded.model_dump(mode="json"),
            error_code=None,
        )

    def execute_sql(self, state: AgentState) -> AgentState:
        guarded = GuardedQuery.model_validate(state["guarded_query"])
        policy = QueryPolicy.model_validate(state["query_policy"])
        result = self._executor.execute(guarded, self._data_source, policy)
        return AgentState(
            columns=list(result.columns),
            rows=list(result.rows),
            error_code=None,
        )

    def verify(self, state: AgentState) -> AgentState:
        expected = state.get("analysis_plan", {}).get("expected_columns", [])
        if expected and not set(expected).issubset(state.get("columns", [])):
            return AgentState(error_code="RESULT_COLUMNS_MISMATCH")
        return AgentState(error_code=None)

    def compose(self, state: AgentState) -> AgentState:
        if state.get("error_code") == "RAG_INSUFFICIENT_EVIDENCE":
            return AgentState(
                answer="The metric knowledge base does not contain enough evidence to answer.",
                error_code=None,
            )
        if state.get("error_code"):
            return AgentState(answer="")
        if state.get("intent") == "knowledge":
            evidence = state.get("metric_context", [])
            answer = evidence[0]["content"] if evidence else ""
        else:
            answer = f"Query completed with {len(state.get('rows', []))} row(s)."
        chart_spec = build_chart_spec(state.get("columns", []), state.get("rows", []))
        return AgentState(answer=answer, chart_spec=chart_spec.model_dump(mode="json"))

    def _controlled_references(self, sql: str) -> set[str]:
        statement = parse_one(sql, read="postgres")
        aliases = {table.alias_or_name: table.name for table in statement.find_all(exp.Table)}
        found: set[str] = set()
        for column in statement.find_all(exp.Column):
            table = aliases.get(column.table, column.table)
            qualified = f"{table}.{column.name}" if table else ""
            if qualified in self._controlled_columns:
                found.add(qualified)
        return found


def _messages(items: Sequence[tuple[str, str]]) -> tuple[LLMMessage, ...]:
    return tuple(LLMMessage(role=role, content=content) for role, content in items)  # type: ignore[arg-type]


def _run[T](coroutine: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    raise RuntimeError("synchronous workflow nodes must run outside an active event loop")
