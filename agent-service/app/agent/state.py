from typing import Any, Literal, TypedDict

Intent = Literal["sql", "knowledge", "hybrid"]
SQLRisk = Literal["safe", "approval", "blocked", "repair"]
ApprovalDecision = Literal["approved", "rejected"]


class AgentState(TypedDict, total=False):
    run_id: str
    tenant_id: str
    user_id: str
    role: str
    data_source_id: str
    trace_id: str
    question: str
    intent: Intent
    candidate_tables: list[str]
    selection_confidence: float
    schema_snapshot: dict[str, Any]
    query_policy: dict[str, Any]
    metric_context: list[dict[str, Any]]
    analysis_plan: dict[str, Any]
    sql: str
    sql_fingerprint: str
    guarded_query: dict[str, Any]
    sql_risk: SQLRisk
    risk_reasons: list[str]
    approval_decision: ApprovalDecision
    rows: list[dict[str, Any]]
    columns: list[str]
    attempts: int
    answer: str
    citations: list[dict[str, Any]]
    chart_spec: dict[str, Any]
    error_code: str | None
