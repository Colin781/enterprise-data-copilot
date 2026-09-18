from typing import Literal
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.graph import build_agent_graph
from app.agent.models import ApprovalResume, StartRun
from app.agent.service import AgentWorkflowService, WorkflowConflictError
from app.agent.state import AgentState
from app.agent.steps import InMemoryAgentStepSink
from app.llm.errors import LLMRequestRejectedError


class ScriptedActions:
    def __init__(
        self,
        *,
        risk: Literal["safe", "approval", "blocked"] = "safe",
        verification_failures: int = 0,
        approval_reason: str = "TOTAL_COST_LIMIT_EXCEEDED",
    ) -> None:
        self.risk = risk
        self.verification_failures = verification_failures
        self.approval_reason = approval_reason
        self.executions = 0
        self.generations = 0

    def classify(self, state: AgentState) -> AgentState:
        return AgentState(intent="hybrid")

    def retrieve_metrics(self, state: AgentState) -> AgentState:
        return AgentState(
            metric_context=[
                {
                    "content": "Revenue excludes cancelled orders.",
                    "citation": {"document_id": "metric-1", "source_locator": "lines 4-8"},
                }
            ],
            citations=[{"document_id": "metric-1", "source_locator": "lines 4-8"}],
        )

    def select_schema(self, state: AgentState) -> AgentState:
        return AgentState(candidate_tables=["orders"])

    def generate_sql(self, state: AgentState) -> AgentState:
        self.generations += 1
        return AgentState(
            attempts=state.get("attempts", 0) + 1,
            sql="SELECT order_id FROM northwind.orders LIMIT 5",
            analysis_plan={"summary": "Read orders"},
            error_code=None,
        )

    def guard_sql(self, state: AgentState) -> AgentState:
        reasons = [] if self.risk == "safe" else [self.approval_reason]
        return AgentState(
            sql_risk=self.risk,
            risk_reasons=reasons,
            sql_fingerprint="sha256:" + "a" * 64,
            error_code="POLICY_BLOCKED" if self.risk == "blocked" else None,
        )

    def execute_sql(self, state: AgentState) -> AgentState:
        self.executions += 1
        return AgentState(columns=["order_id"], rows=[{"order_id": 1}], error_code=None)

    def verify(self, state: AgentState) -> AgentState:
        if state["attempts"] <= self.verification_failures:
            return AgentState(error_code="RESULT_VERIFICATION_FAILED")
        return AgentState(error_code=None)

    def compose(self, state: AgentState) -> AgentState:
        if state.get("error_code"):
            return AgentState()
        return AgentState(answer="Found one order.")


class RejectedModelActions(ScriptedActions):
    def select_schema(self, state: AgentState) -> AgentState:
        raise LLMRequestRejectedError()


def request() -> StartRun:
    return StartRun(
        run_id=str(uuid4()),
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        role="ANALYST",
        data_source_id=str(uuid4()),
        trace_id=uuid4().hex,
        question="Show orders and explain the metric.",
    )


def service(
    actions: ScriptedActions,
    sink: InMemoryAgentStepSink,
    saver: InMemorySaver | None = None,
) -> AgentWorkflowService:
    return AgentWorkflowService(
        build_agent_graph(
            actions=actions,
            step_sink=sink,
            checkpointer=saver or InMemorySaver(),
        )
    )


def test_safe_graph_runs_all_nodes_and_persists_only_redacted_step_summaries() -> None:
    actions = ScriptedActions()
    sink = InMemoryAgentStepSink()
    run = request()

    result = service(actions, sink).start(run)

    assert result.status == "COMPLETED"
    assert result.state["answer"] == "Found one order."
    assert actions.executions == 1
    assert [record.step_name for record in sink.records] == [
        "classify",
        "retrieve_metrics",
        "select_schema",
        "generate_sql",
        "guard_sql",
        "execute_sql",
        "verify",
        "compose",
    ]
    serialized = repr(sink.records)
    assert run.question not in serialized
    assert "SELECT order_id" not in serialized
    assert "Found one order" not in serialized
    assert "sql_fingerprint" in serialized


def test_replayed_start_returns_checkpoint_without_executing_twice() -> None:
    actions = ScriptedActions()
    workflow = service(actions, InMemoryAgentStepSink())
    run = request()

    first = workflow.start(run)
    replay = workflow.start(run)

    assert first.status == replay.status == "COMPLETED"
    assert actions.executions == 1


def test_failed_node_returns_stable_terminal_error_instead_of_staying_planning() -> None:
    actions = RejectedModelActions()
    workflow = service(actions, InMemoryAgentStepSink())
    run = request()

    failed = workflow.start(run)
    replay = workflow.start(run)

    assert failed.status == replay.status == "FAILED"
    assert failed.state["error_code"] == "LLM_REQUEST_REJECTED"


def test_interrupted_graph_resumes_with_same_thread_after_service_recreation() -> None:
    actions = ScriptedActions(risk="approval")
    sink = InMemoryAgentStepSink()
    saver = InMemorySaver()
    run = request()

    waiting = service(actions, sink, saver).start(run)
    restarted_service = service(actions, sink, saver)
    completed = restarted_service.resume(
        run_id=run.run_id,
        tenant_id=run.tenant_id,
        resume=ApprovalResume(
            approval_id=str(uuid4()),
            decision="approved",
            decided_by=str(uuid4()),
        ),
    )

    assert waiting.status == "WAITING_APPROVAL"
    assert waiting.interrupt == {
        "run_id": run.run_id,
        "sql_fingerprint": "sha256:" + "a" * 64,
        "reason_codes": ["TOTAL_COST_LIMIT_EXCEEDED"],
    }
    assert completed.status == "COMPLETED"
    assert actions.executions == 1


def test_same_checkpoint_cannot_be_approved_twice() -> None:
    actions = ScriptedActions(risk="approval")
    workflow = service(actions, InMemoryAgentStepSink())
    run = request()
    workflow.start(run)
    decision = ApprovalResume(
        approval_id=str(uuid4()), decision="approved", decided_by=str(uuid4())
    )

    assert workflow.resume(run_id=run.run_id, tenant_id=run.tenant_id, resume=decision).status == (
        "COMPLETED"
    )
    with pytest.raises(WorkflowConflictError):
        workflow.resume(run_id=run.run_id, tenant_id=run.tenant_id, resume=decision)
    assert actions.executions == 1


def test_low_confidence_uses_the_same_durable_approval_gate() -> None:
    actions = ScriptedActions(risk="approval", approval_reason="LOW_MODEL_CONFIDENCE")
    run = request()

    waiting = service(actions, InMemoryAgentStepSink()).start(run)

    assert waiting.status == "WAITING_APPROVAL"
    assert waiting.interrupt is not None
    assert waiting.interrupt["reason_codes"] == ["LOW_MODEL_CONFIDENCE"]
    assert actions.executions == 0


def test_controlled_sensitive_column_uses_the_same_durable_approval_gate() -> None:
    actions = ScriptedActions(risk="approval", approval_reason="CONTROLLED_SENSITIVE_COLUMN")

    waiting = service(actions, InMemoryAgentStepSink()).start(request())

    assert waiting.status == "WAITING_APPROVAL"
    assert waiting.interrupt is not None
    assert waiting.interrupt["reason_codes"] == ["CONTROLLED_SENSITIVE_COLUMN"]
    assert actions.executions == 0


def test_rejected_approval_never_executes() -> None:
    actions = ScriptedActions(risk="approval")
    workflow = service(actions, InMemoryAgentStepSink())
    run = request()
    workflow.start(run)

    result = workflow.resume(
        run_id=run.run_id,
        tenant_id=run.tenant_id,
        resume=ApprovalResume(
            approval_id=str(uuid4()), decision="rejected", decided_by=str(uuid4())
        ),
    )

    assert result.status == "REJECTED"
    assert actions.executions == 0


def test_blocked_policy_never_reaches_approval_or_executor() -> None:
    actions = ScriptedActions(risk="blocked")
    result = service(actions, InMemoryAgentStepSink()).start(request())

    assert result.status == "REJECTED"
    assert result.interrupt is None
    assert actions.executions == 0


def test_verification_loop_stops_after_three_total_generation_attempts() -> None:
    actions = ScriptedActions(verification_failures=99)
    result = service(actions, InMemoryAgentStepSink()).start(request())

    assert result.status == "FAILED"
    assert result.state["attempts"] == 3
    assert actions.generations == 3
    assert actions.executions == 3
