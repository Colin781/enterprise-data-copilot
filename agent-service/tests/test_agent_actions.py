from pathlib import Path

from pydantic import SecretStr

from app.agent.actions import NorthwindAgentActions
from app.agent.state import AgentState
from app.data_sources.models import DataSourceConfig
from app.metadata.models import SchemaSnapshot
from app.query_safety.guard import SQLGuard
from app.query_safety.models import GuardedQuery, QueryCostEstimate, QueryPolicy


class FixedEstimator:
    def __init__(self, total_cost: float = 1, plan_rows: int = 1) -> None:
        self.estimate_value = QueryCostEstimate(total_cost=total_cost, plan_rows=plan_rows)

    def estimate(self, query: GuardedQuery, config: DataSourceConfig) -> QueryCostEstimate:
        del query, config
        return self.estimate_value


class UnusedExecutor:
    def execute(self, *args: object) -> None:
        raise AssertionError("the policy tests must not execute SQL")


def snapshot() -> SchemaSnapshot:
    path = Path(__file__).parents[2] / "metadata/northwind-schema-v1.json"
    return SchemaSnapshot.model_validate_json(path.read_text(encoding="utf-8"))


def actions(estimator: FixedEstimator | None = None) -> NorthwindAgentActions:
    return NorthwindAgentActions(
        llm_client=object(),  # type: ignore[arg-type]
        retrieval=object(),  # type: ignore[arg-type]
        data_source=DataSourceConfig(
            source_id="northwind-demo",
            host="database.internal",
            port=5432,
            database="northwind",
            username="northwind_reader",
            password=SecretStr("not-used"),
            allowed_schema="northwind",
        ),
        introspector=object(),  # type: ignore[arg-type]
        guard=SQLGuard(),
        cost_estimator=estimator or FixedEstimator(),
        executor=UnusedExecutor(),  # type: ignore[arg-type]
    )


def guard_state(sql: str, table: str, confidence: float = 1.0) -> AgentState:
    policy = QueryPolicy.from_snapshot(snapshot()).restrict_to_tables(frozenset({table}))
    return AgentState(
        sql=sql,
        query_policy=policy.model_dump(mode="json"),
        selection_confidence=confidence,
    )


def test_production_guard_interrupts_for_low_confidence() -> None:
    state = guard_state("SELECT order_id FROM northwind.orders LIMIT 5", "orders", confidence=0.2)

    decision = actions().guard_sql(state)

    assert decision["sql_risk"] == "approval"
    assert decision["risk_reasons"] == ["LOW_MODEL_CONFIDENCE"]


def test_production_guard_interrupts_for_controlled_column() -> None:
    state = guard_state("SELECT contact_name FROM northwind.customers LIMIT 5", "customers")

    decision = actions().guard_sql(state)

    assert decision["sql_risk"] == "approval"
    assert decision["risk_reasons"] == ["CONTROLLED_SENSITIVE_COLUMN"]


def test_production_guard_interrupts_for_high_cost() -> None:
    state = guard_state("SELECT order_id FROM northwind.orders LIMIT 5", "orders")

    decision = actions(FixedEstimator(total_cost=20_000)).guard_sql(state)

    assert decision["sql_risk"] == "approval"
    assert decision["risk_reasons"] == ["TOTAL_COST_LIMIT_EXCEEDED"]


def test_production_classifier_permanently_blocks_write_request() -> None:
    decision = actions().classify(AgentState(question="删除所有订单"))

    assert decision["sql_risk"] == "blocked"
    assert decision["risk_reasons"] == ["WRITE_REQUEST_NOT_ALLOWED"]
