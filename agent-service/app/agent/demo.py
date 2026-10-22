"""Offline failure/repair and approval/replay demo, not real model accuracy evidence."""

import json
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver

from app.agent.graph import build_agent_graph
from app.agent.models import ApprovalResume, StartRun
from app.agent.service import AgentWorkflowService
from app.agent.steps import InMemoryAgentStepSink


class DemoActions:
    def __init__(self, approval=False):
        self.approval = approval
        self.executions = 0

    def classify(self, state):
        return {"intent": "hybrid"}

    def retrieve_metrics(self, state):
        return {"metric_context": [], "citations": []}

    def select_schema(self, state):
        return {"candidate_tables": ["orders"]}

    def generate_sql(self, state):
        return {"attempts": state.get("attempts", 0) + 1, "sql": "SELECT 1", "error_code": None}

    def guard_sql(self, state):
        if state["attempts"] == 1 and not self.approval:
            return {"sql_risk": "repair", "error_code": "DEMO_REPAIR_REQUIRED"}
        return {"sql_risk": "approval" if self.approval else "safe", "error_code": None}

    def execute_sql(self, state):
        self.executions += 1
        return {"columns": ["value"], "rows": [{"value": 1}]}

    def verify(self, state):
        return {"error_code": None}

    def compose(self, state):
        return {"answer": "Offline demonstration completed."}


def demo():
    records = []
    for approval in (False, True):
        actions, sink, saver = DemoActions(approval), InMemoryAgentStepSink(), InMemorySaver()

        def workflow(actions=actions, sink=sink, saver=saver):
            return AgentWorkflowService(
                build_agent_graph(
                    actions=actions, step_sink=sink, checkpointer=saver, max_repairs=2
                )
            )

        request = StartRun(
            run_id=str(uuid4()),
            tenant_id=str(uuid4()),
            user_id=str(uuid4()),
            data_source_id=str(uuid4()),
            role="ANALYST",
            trace_id=uuid4().hex,
            question="Offline demo",
        )
        result = workflow().start(request)
        if approval:
            assert result.status == "WAITING_APPROVAL" and actions.executions == 0
            # Recreate the workflow wrapper; recover state from the same checkpoint store.
            result = workflow().resume(
                run_id=request.run_id,
                tenant_id=request.tenant_id,
                resume=ApprovalResume(
                    approval_id=str(uuid4()), decision="approved", decided_by=str(uuid4())
                ),
            )
        replay = workflow().start(request)
        assert result.status == replay.status == "COMPLETED" and actions.executions == 1
        assert all(record.status != "FAILED" for record in sink.records)
        records.append(
            {
                "approval": approval,
                "status": result.status,
                "sql_executions": actions.executions,
                "attempts": result.state["attempts"],
                "node_events": [
                    {"step": s.step_name, "status": s.status, "duration_ms": s.duration_ms}
                    for s in sink.records
                ],
            }
        )
    return {
        "mode": "scripted_offline_demo",
        "checkpoint": "in-memory; production uses PostgreSQL",
        "runs": records,
    }


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2))
