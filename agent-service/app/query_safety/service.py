from datetime import UTC, datetime
from time import monotonic_ns
from uuid import uuid4

from app.data_sources.models import DataSourceConfig
from app.query_safety.audit import QueryAuditSink
from app.query_safety.cost import QueryCostEstimator
from app.query_safety.errors import (
    QueryApprovalRequiredError,
    QueryAuditError,
    QueryExecutionError,
    QuerySafetyError,
    SQLPolicyViolationError,
)
from app.query_safety.executor import QueryExecutor
from app.query_safety.guard import SQLGuard, fingerprint_query
from app.query_safety.models import (
    GuardedQuery,
    QueryAuditEvent,
    QueryContext,
    QueryCostEstimate,
    QueryExecutionResult,
    QueryPolicy,
    SafeQueryOutcome,
)


class SafeQueryService:
    def __init__(
        self,
        *,
        guard: SQLGuard,
        executor: QueryExecutor,
        audit_sink: QueryAuditSink,
        cost_estimator: QueryCostEstimator | None = None,
    ) -> None:
        self._guard = guard
        self._executor = executor
        self._audit_sink = audit_sink
        self._cost_estimator = cost_estimator

    def execute_fixed(
        self,
        *,
        sql: str,
        context: QueryContext,
        config: DataSourceConfig,
        policy: QueryPolicy,
    ) -> SafeQueryOutcome:
        started_at = datetime.now(UTC)
        started_ns = monotonic_ns()
        guarded: GuardedQuery | None = None
        estimate: QueryCostEstimate | None = None

        try:
            guarded = self._guard.inspect(sql, policy)
        except SQLPolicyViolationError as error:
            event = self._event(
                context=context,
                occurred_at=started_at,
                started_ns=started_ns,
                status="REJECTED",
                reason_code=error.reason_code,
                query_fingerprint=fingerprint_query(sql),
                executor_invoked=False,
            )
            self._record(event)
            raise

        if self._cost_estimator is not None:
            try:
                estimate = self._cost_estimator.estimate(guarded, config)
            except QuerySafetyError as error:
                event = self._event(
                    context=context,
                    occurred_at=started_at,
                    started_ns=started_ns,
                    status="FAILED",
                    reason_code=error.code,
                    query_fingerprint=guarded.query_fingerprint,
                    referenced_tables=guarded.referenced_tables,
                    planner_invoked=True,
                    executor_invoked=False,
                )
                self._record(event)
                raise
            except Exception as exc:
                error = QueryExecutionError()
                event = self._event(
                    context=context,
                    occurred_at=started_at,
                    started_ns=started_ns,
                    status="FAILED",
                    reason_code=error.code,
                    query_fingerprint=guarded.query_fingerprint,
                    referenced_tables=guarded.referenced_tables,
                    planner_invoked=True,
                    executor_invoked=False,
                )
                self._record(event)
                raise error from exc

            approval_reason = self._approval_reason(estimate, policy)
            if approval_reason is not None:
                event = self._event(
                    context=context,
                    occurred_at=started_at,
                    started_ns=started_ns,
                    status="APPROVAL_REQUIRED",
                    reason_code=approval_reason,
                    query_fingerprint=guarded.query_fingerprint,
                    referenced_tables=guarded.referenced_tables,
                    planner_invoked=True,
                    executor_invoked=False,
                    estimate=estimate,
                )
                self._record(event)
                raise QueryApprovalRequiredError(
                    approval_reason,
                    estimated_total_cost=estimate.total_cost,
                    estimated_plan_rows=estimate.plan_rows,
                )

        try:
            result = self._executor.execute(guarded, config, policy)
        except QuerySafetyError as error:
            event = self._event(
                context=context,
                occurred_at=started_at,
                started_ns=started_ns,
                status="FAILED",
                reason_code=error.code,
                query_fingerprint=guarded.query_fingerprint,
                referenced_tables=guarded.referenced_tables,
                planner_invoked=estimate is not None,
                executor_invoked=True,
                estimate=estimate,
            )
            self._record(event)
            raise
        except Exception as exc:
            error = QueryExecutionError()
            event = self._event(
                context=context,
                occurred_at=started_at,
                started_ns=started_ns,
                status="FAILED",
                reason_code=error.code,
                query_fingerprint=guarded.query_fingerprint,
                referenced_tables=guarded.referenced_tables,
                planner_invoked=estimate is not None,
                executor_invoked=True,
                estimate=estimate,
            )
            self._record(event)
            raise error from exc

        event = self._event(
            context=context,
            occurred_at=started_at,
            started_ns=started_ns,
            status="SUCCEEDED",
            reason_code="QUERY_EXECUTED",
            query_fingerprint=guarded.query_fingerprint,
            referenced_tables=guarded.referenced_tables,
            planner_invoked=estimate is not None,
            executor_invoked=True,
            estimate=estimate,
            result=result,
        )
        self._record(event)
        return SafeQueryOutcome(result=result, audit=event)

    def execute_generated(
        self,
        *,
        sql: str,
        context: QueryContext,
        config: DataSourceConfig,
        policy: QueryPolicy,
    ) -> SafeQueryOutcome:
        return self.execute_fixed(sql=sql, context=context, config=config, policy=policy)

    @staticmethod
    def _approval_reason(estimate: QueryCostEstimate, policy: QueryPolicy) -> str | None:
        if estimate.total_cost > policy.max_total_cost:
            return "TOTAL_COST_LIMIT_EXCEEDED"
        if estimate.plan_rows > policy.max_plan_rows:
            return "PLAN_ROWS_LIMIT_EXCEEDED"
        return None

    def _record(self, event: QueryAuditEvent) -> None:
        try:
            self._audit_sink.record(event)
        except Exception as exc:
            raise QueryAuditError() from exc

    @staticmethod
    def _event(
        *,
        context: QueryContext,
        occurred_at: datetime,
        started_ns: int,
        status: str,
        reason_code: str,
        query_fingerprint: str,
        executor_invoked: bool,
        planner_invoked: bool = False,
        referenced_tables: tuple[str, ...] = (),
        estimate: QueryCostEstimate | None = None,
        result: QueryExecutionResult | None = None,
    ) -> QueryAuditEvent:
        return QueryAuditEvent(
            event_id=uuid4(),
            occurred_at=occurred_at,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            job_id=context.job_id,
            data_source_id=context.data_source_id,
            trace_id=context.trace_id,
            status=status,
            reason_code=reason_code,
            query_fingerprint=query_fingerprint,
            referenced_tables=referenced_tables,
            planner_invoked=planner_invoked,
            executor_invoked=executor_invoked,
            estimated_total_cost=estimate.total_cost if estimate else None,
            estimated_plan_rows=estimate.plan_rows if estimate else None,
            returned_rows=result.returned_row_count if result else 0,
            returned_columns=len(result.columns) if result else 0,
            serialized_bytes=result.serialized_bytes if result else 0,
            result_truncated=result.truncated if result else False,
            duration_ms=max(0, (monotonic_ns() - started_ns) // 1_000_000),
        )
