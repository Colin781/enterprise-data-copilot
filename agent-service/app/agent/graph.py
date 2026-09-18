from time import monotonic_ns
from typing import Protocol

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agent.state import AgentState
from app.agent.steps import (
    AgentStepRecord,
    AgentStepSink,
    ApprovalRequestSink,
    NullApprovalRequestSink,
    state_summary,
    timed_step,
)


class AgentActions(Protocol):
    def classify(self, state: AgentState) -> AgentState: ...

    def retrieve_metrics(self, state: AgentState) -> AgentState: ...

    def select_schema(self, state: AgentState) -> AgentState: ...

    def generate_sql(self, state: AgentState) -> AgentState: ...

    def guard_sql(self, state: AgentState) -> AgentState: ...

    def execute_sql(self, state: AgentState) -> AgentState: ...

    def verify(self, state: AgentState) -> AgentState: ...

    def compose(self, state: AgentState) -> AgentState: ...


class AgentNodes:
    def __init__(
        self,
        actions: AgentActions,
        step_sink: AgentStepSink,
        approval_sink: ApprovalRequestSink,
    ) -> None:
        self._actions = actions
        self._sink = step_sink
        self._approval_sink = approval_sink

    def classify(self, state: AgentState) -> AgentState:
        return self._run("classify", state, self._actions.classify)

    def retrieve_metrics(self, state: AgentState) -> AgentState:
        return self._run("retrieve_metrics", state, self._actions.retrieve_metrics)

    def select_schema(self, state: AgentState) -> AgentState:
        return self._run("select_schema", state, self._actions.select_schema)

    def generate_sql(self, state: AgentState) -> AgentState:
        return self._run("generate_sql", state, self._actions.generate_sql)

    def guard_sql(self, state: AgentState) -> AgentState:
        return self._run("guard_sql", state, self._actions.guard_sql)

    def request_approval(self, state: AgentState) -> AgentState:
        def pause(current: AgentState) -> AgentState:
            started = monotonic_ns()
            self._approval_sink.ensure_pending(current)
            self._sink.record(
                AgentStepRecord(
                    run_id=current["run_id"],
                    step_name="request_approval",
                    status="WAITING",
                    attempt=int(current.get("attempts", 0)),
                    input_summary=state_summary(current),
                    output_summary={
                        "sql_fingerprint": current.get("sql_fingerprint"),
                        "risk_reasons": current.get("risk_reasons", [])[:5],
                    },
                    duration_ms=max(0, (monotonic_ns() - started) // 1_000_000),
                )
            )
            decision = interrupt(
                {
                    "run_id": current["run_id"],
                    "sql_fingerprint": current.get("sql_fingerprint"),
                    "reason_codes": current.get("risk_reasons", []),
                }
            )
            if not isinstance(decision, dict) or decision.get("decision") not in {
                "approved",
                "rejected",
            }:
                raise ValueError("invalid approval resume payload")
            if decision["decision"] == "rejected":
                return AgentState(approval_decision="rejected", error_code="APPROVAL_REJECTED")
            return AgentState(approval_decision="approved", error_code=None)

        return self._run("request_approval", state, pause)

    def execute_sql(self, state: AgentState) -> AgentState:
        return self._run("execute_sql", state, self._actions.execute_sql)

    def verify(self, state: AgentState) -> AgentState:
        return self._run("verify", state, self._actions.verify)

    def compose(self, state: AgentState) -> AgentState:
        return self._run("compose", state, self._actions.compose)

    def _run(self, name: str, state: AgentState, operation: object) -> AgentState:
        return timed_step(sink=self._sink, step_name=name, state=state, operation=operation)


def build_agent_graph(
    *,
    actions: AgentActions,
    step_sink: AgentStepSink,
    checkpointer: object,
    approval_sink: ApprovalRequestSink | None = None,
    max_repairs: int = 2,
):
    if not 0 <= max_repairs <= 2:
        raise ValueError("max_repairs must be between 0 and 2")
    nodes = AgentNodes(actions, step_sink, approval_sink or NullApprovalRequestSink())
    graph = StateGraph(AgentState)
    graph.add_node("classify", nodes.classify)
    graph.add_node("retrieve_metrics", nodes.retrieve_metrics)
    graph.add_node("select_schema", nodes.select_schema)
    graph.add_node("generate_sql", nodes.generate_sql)
    graph.add_node("guard_sql", nodes.guard_sql)
    graph.add_node("request_approval", nodes.request_approval)
    graph.add_node("execute_sql", nodes.execute_sql)
    graph.add_node("verify", nodes.verify)
    graph.add_node("compose", nodes.compose)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        lambda state: "blocked" if state.get("sql_risk") == "blocked" else "continue",
        {"blocked": END, "continue": "retrieve_metrics"},
    )
    graph.add_conditional_edges(
        "retrieve_metrics",
        lambda state: "knowledge" if state["intent"] == "knowledge" else "data",
        {"knowledge": "compose", "data": "select_schema"},
    )
    graph.add_edge("select_schema", "generate_sql")
    graph.add_edge("generate_sql", "guard_sql")
    graph.add_conditional_edges(
        "guard_sql",
        lambda state: (
            "retry"
            if state["sql_risk"] == "repair" and state.get("attempts", 0) < max_repairs + 1
            else state["sql_risk"]
        ),
        {
            "safe": "execute_sql",
            "approval": "request_approval",
            "blocked": END,
            "repair": END,
            "retry": "generate_sql",
        },
    )
    graph.add_conditional_edges(
        "request_approval",
        lambda state: state["approval_decision"],
        {"approved": "execute_sql", "rejected": END},
    )
    graph.add_edge("execute_sql", "verify")
    graph.add_conditional_edges(
        "verify",
        lambda state: (
            "retry"
            if state.get("error_code") and state.get("attempts", 0) < max_repairs + 1
            else "done"
        ),
        {"retry": "generate_sql", "done": "compose"},
    )
    graph.add_edge("compose", END)
    return graph.compile(checkpointer=checkpointer)
