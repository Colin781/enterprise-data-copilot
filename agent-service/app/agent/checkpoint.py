from collections.abc import Iterator
from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver

from app.agent.graph import AgentActions, build_agent_graph
from app.agent.service import AgentWorkflowService
from app.agent.steps import AgentStepSink, ApprovalRequestSink


@contextmanager
def postgres_workflow_service(
    *,
    dsn: str,
    actions: AgentActions,
    step_sink: AgentStepSink,
    approval_sink: ApprovalRequestSink | None = None,
    setup: bool = False,
    max_repairs: int = 2,
) -> Iterator[AgentWorkflowService]:
    """Create a service whose checkpoints survive process and object lifetimes."""
    with PostgresSaver.from_conn_string(dsn) as checkpointer:
        if setup:
            checkpointer.setup()
        graph = build_agent_graph(
            actions=actions,
            step_sink=step_sink,
            checkpointer=checkpointer,
            approval_sink=approval_sink,
            max_repairs=max_repairs,
        )
        yield AgentWorkflowService(graph)
