from app.llm.structured import StructuredLLMClient
from app.nl2sql.service import NL2SQLService
from app.query_safety.audit import QueryAuditSink
from app.query_safety.cost import PostgresQueryCostEstimator
from app.query_safety.executor import PostgresReadOnlyExecutor
from app.query_safety.guard import SQLGuard
from app.query_safety.service import SafeQueryService
from app.settings import NL2SQLSettings, get_nl2sql_settings


def create_nl2sql_service(
    *,
    llm_client: StructuredLLMClient,
    audit_sink: QueryAuditSink,
    settings: NL2SQLSettings | None = None,
) -> NL2SQLService:
    resolved = settings or get_nl2sql_settings()
    return NL2SQLService(
        llm_client=llm_client,
        safe_query_service=SafeQueryService(
            guard=SQLGuard(),
            executor=PostgresReadOnlyExecutor(),
            audit_sink=audit_sink,
            cost_estimator=PostgresQueryCostEstimator(),
        ),
        max_selected_tables=resolved.max_selected_tables,
        max_repairs=resolved.max_repairs,
    )
