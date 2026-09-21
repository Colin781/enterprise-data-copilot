import hashlib
from dataclasses import dataclass, field
from time import monotonic_ns
from typing import Any, Protocol

import httpx

from app.agent.state import AgentState
from app.observability import NODE_DURATION, NODE_ERRORS, agent_node_span, mark_span_error


@dataclass(frozen=True, slots=True)
class AgentStepRecord:
    run_id: str
    step_name: str
    status: str
    attempt: int
    input_summary: dict[str, Any]
    output_summary: dict[str, Any]
    duration_ms: int
    error_code: str | None = None


class AgentStepSink(Protocol):
    def record(self, step: AgentStepRecord) -> None: ...


class ApprovalRequestSink(Protocol):
    def ensure_pending(self, state: AgentState) -> None: ...


class NullApprovalRequestSink:
    def ensure_pending(self, state: AgentState) -> None:
        del state


@dataclass(slots=True)
class InMemoryAgentStepSink:
    records: list[AgentStepRecord] = field(default_factory=list)

    def record(self, step: AgentStepRecord) -> None:
        self.records.append(step)


class PlatformAgentStepSink:
    """Writes redacted node summaries to the Java-owned platform boundary."""

    def __init__(self, base_url: str, service_token: str, timeout_seconds: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {service_token}"}
        self._timeout = timeout_seconds

    def record(self, step: AgentStepRecord) -> None:
        response = httpx.post(
            f"{self._base_url}/internal/v1/analysis/jobs/{step.run_id}/steps",
            headers=self._headers,
            json={
                "step_name": step.step_name,
                "status": step.status,
                "attempt": step.attempt,
                "input_summary": step.input_summary,
                "output_summary": step.output_summary,
                "duration_ms": step.duration_ms,
                "error_code": step.error_code,
            },
            timeout=self._timeout,
        )
        response.raise_for_status()


class PlatformApprovalRequestSink:
    def __init__(self, base_url: str, service_token: str, timeout_seconds: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {service_token}"}
        self._timeout = timeout_seconds

    def ensure_pending(self, state: AgentState) -> None:
        response = httpx.post(
            f"{self._base_url}/internal/v1/analysis/jobs/{state['run_id']}/approval-requests",
            headers={**self._headers, "X-Trace-Id": state["trace_id"]},
            json={
                "reason_codes": state.get("risk_reasons", []),
                "sql_fingerprint": state.get("sql_fingerprint"),
            },
            timeout=self._timeout,
        )
        response.raise_for_status()


def state_summary(state: AgentState) -> dict[str, Any]:
    """Allowlist summaries so questions, SQL and row values never reach agent_steps."""
    summary: dict[str, Any] = {
        "intent": state.get("intent"),
        "candidate_table_count": len(state.get("candidate_tables", [])),
        "metric_context_count": len(state.get("metric_context", [])),
        "attempts": state.get("attempts", 0),
        "sql_risk": state.get("sql_risk"),
        "risk_reasons": list(state.get("risk_reasons", []))[:5],
        "row_count": len(state.get("rows", [])),
        "column_count": len(state.get("columns", [])),
        "citation_count": len(state.get("citations", [])),
        "error_code": state.get("error_code"),
    }
    sql = state.get("sql")
    if sql:
        summary["sql_fingerprint"] = f"sha256:{hashlib.sha256(sql.encode()).hexdigest()}"
    return {key: value for key, value in summary.items() if value is not None}


def timed_step(
    *,
    sink: AgentStepSink,
    step_name: str,
    state: AgentState,
    operation: Any,
) -> AgentState:
    started = monotonic_ns()
    input_summary = state_summary(state)
    attempt = int(state.get("attempts", 0))
    with agent_node_span(step_name, state["trace_id"]) as span:
        try:
            update = AgentState(operation(state))
            merged = AgentState(state)
            merged.update(update)
            sink.record(
                AgentStepRecord(
                    run_id=state["run_id"],
                    step_name=step_name,
                    status="SUCCEEDED",
                    attempt=attempt,
                    input_summary=input_summary,
                    output_summary=state_summary(merged),
                    duration_ms=max(0, (monotonic_ns() - started) // 1_000_000),
                )
            )
            NODE_DURATION.labels(step_name, "succeeded").observe(
                max(0, monotonic_ns() - started) / 1_000_000_000
            )
            return update
        except Exception as error:
            error_code = getattr(error, "code", error.__class__.__name__.upper())
            sink.record(
                AgentStepRecord(
                    run_id=state["run_id"],
                    step_name=step_name,
                    status="FAILED",
                    attempt=attempt,
                    input_summary=input_summary,
                    output_summary={},
                    duration_ms=max(0, (monotonic_ns() - started) // 1_000_000),
                    error_code=error_code,
                )
            )
            NODE_DURATION.labels(step_name, "failed").observe(
                max(0, monotonic_ns() - started) / 1_000_000_000
            )
            NODE_ERRORS.labels(step_name, error_code).inc()
            mark_span_error(span, error, error_code)
            raise
