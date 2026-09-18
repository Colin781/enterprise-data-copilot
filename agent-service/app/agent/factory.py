from collections.abc import Iterator
from contextlib import contextmanager

from app.agent.actions import NorthwindAgentActions
from app.agent.checkpoint import postgres_workflow_service
from app.agent.service import AgentWorkflowService
from app.agent.steps import PlatformAgentStepSink, PlatformApprovalRequestSink
from app.data_sources.models import DataSourceConfig
from app.llm.factory import create_structured_llm_client
from app.metadata.introspection import PostgresSchemaIntrospector
from app.query_safety.cost import PostgresQueryCostEstimator
from app.query_safety.executor import PostgresReadOnlyExecutor
from app.query_safety.guard import SQLGuard
from app.retrieval.factory import create_metric_retrieval_service
from app.retrieval.repository import (
    PlatformKnowledgeDatabaseConfig,
    PostgresMetricKnowledgeRepository,
)
from app.settings import (
    get_agent_workflow_settings,
    get_business_database_settings,
    get_platform_database_settings,
    get_query_safety_settings,
)


@contextmanager
def create_production_workflow_service(
    *, setup_checkpointer: bool
) -> Iterator[AgentWorkflowService]:
    workflow_settings = get_agent_workflow_settings()
    platform_settings = get_platform_database_settings()
    business_settings = get_business_database_settings()
    safety_settings = get_query_safety_settings()
    token = workflow_settings.service_token.get_secret_value()
    platform_url = str(workflow_settings.platform_api_url)
    repository = PostgresMetricKnowledgeRepository(
        PlatformKnowledgeDatabaseConfig(
            host=platform_settings.host,
            port=platform_settings.port,
            database=platform_settings.name,
            username=platform_settings.user,
            password=platform_settings.password.get_secret_value(),
        )
    )
    actions = NorthwindAgentActions(
        llm_client=create_structured_llm_client(),
        retrieval=create_metric_retrieval_service(repository),
        data_source=DataSourceConfig.from_settings(business_settings),
        introspector=PostgresSchemaIntrospector(),
        guard=SQLGuard(),
        cost_estimator=PostgresQueryCostEstimator(),
        executor=PostgresReadOnlyExecutor(),
        max_total_cost=safety_settings.max_total_cost,
        max_plan_rows=safety_settings.max_plan_rows,
        minimum_confidence=workflow_settings.minimum_confidence,
    )
    with postgres_workflow_service(
        dsn=workflow_settings.checkpoint_dsn.get_secret_value(),
        actions=actions,
        step_sink=PlatformAgentStepSink(platform_url, token),
        approval_sink=PlatformApprovalRequestSink(platform_url, token),
        setup=setup_checkpointer,
        max_repairs=workflow_settings.max_repairs,
    ) as service:
        yield service
