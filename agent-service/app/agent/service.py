from typing import Any

from langgraph.types import Command

from app.agent.models import ApprovalResume, StartRun, WorkflowResult
from app.agent.state import AgentState


class WorkflowConflictError(RuntimeError):
    code = "WORKFLOW_NOT_WAITING_APPROVAL"


class WorkflowIdentityError(RuntimeError):
    code = "WORKFLOW_IDENTITY_MISMATCH"


class AgentWorkflowService:
    def __init__(self, graph: Any) -> None:
        self._graph = graph

    def start(self, request: StartRun) -> WorkflowResult:
        snapshot = self._graph.get_state(self._config(request.run_id))
        if snapshot.values:
            existing = AgentState(snapshot.values)
            identity = (
                existing.get("tenant_id"),
                existing.get("user_id"),
                existing.get("data_source_id"),
                existing.get("question"),
            )
            requested = (
                request.tenant_id,
                request.user_id,
                request.data_source_id,
                request.question.strip(),
            )
            if identity != requested:
                raise WorkflowConflictError("the run id belongs to a different request")
            return self.inspect(request.run_id)
        try:
            result = self._graph.invoke(
                request.initial_state(), config=self._config(request.run_id)
            )
        except Exception:
            snapshot = self._graph.get_state(self._config(request.run_id))
            if self._snapshot_error_code(snapshot) is not None:
                return self._snapshot_result(request.run_id, snapshot)
            raise
        return self._result(request.run_id, result)

    def resume(
        self,
        *,
        run_id: str,
        tenant_id: str,
        resume: ApprovalResume,
    ) -> WorkflowResult:
        config = self._config(run_id)
        snapshot = self._graph.get_state(config)
        state = AgentState(snapshot.values)
        if not snapshot.tasks or not any(task.interrupts for task in snapshot.tasks):
            raise WorkflowConflictError("the workflow is not waiting for approval")
        if state.get("run_id") != run_id or state.get("tenant_id") != tenant_id:
            raise WorkflowIdentityError("the workflow identity does not match")
        result = self._graph.invoke(
            Command(resume=resume.model_dump(mode="json")),
            config=config,
        )
        return self._result(run_id, result)

    def inspect(self, run_id: str) -> WorkflowResult:
        snapshot = self._graph.get_state(self._config(run_id))
        if not snapshot.values:
            raise KeyError(run_id)
        return self._snapshot_result(run_id, snapshot)

    def _snapshot_result(self, run_id: str, snapshot: Any) -> WorkflowResult:
        state = AgentState(snapshot.values)
        error_code = self._snapshot_error_code(snapshot)
        if error_code is not None:
            state["error_code"] = error_code
        interrupts = [item for task in snapshot.tasks for item in task.interrupts]
        payload = interrupts[0].value if interrupts else None
        return WorkflowResult(
            run_id=run_id,
            status=self._status(state, bool(interrupts)),
            state=state,
            interrupt=payload if isinstance(payload, dict) else None,
        )

    @staticmethod
    def _snapshot_error_code(snapshot: Any) -> str | None:
        error_codes = {
            "LLMAuthenticationError": "LLM_AUTHENTICATION_ERROR",
            "LLMConfigurationError": "LLM_CONFIGURATION_ERROR",
            "LLMInvalidResponseError": "LLM_INVALID_RESPONSE",
            "LLMRateLimitError": "LLM_RATE_LIMITED",
            "LLMRequestRejectedError": "LLM_REQUEST_REJECTED",
            "LLMTimeoutError": "LLM_TIMEOUT",
            "LLMUnavailableError": "LLM_UNAVAILABLE",
        }
        for task in snapshot.tasks:
            if not task.error:
                continue
            error_name = str(task.error).partition("(")[0]
            return error_codes.get(error_name, "AGENT_WORKFLOW_FAILED")
        return None

    @staticmethod
    def _config(run_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": run_id}}

    def _result(self, run_id: str, raw: dict[str, Any]) -> WorkflowResult:
        state = AgentState({key: value for key, value in raw.items() if key != "__interrupt__"})
        raw_interrupts = raw.get("__interrupt__", ())
        payload = raw_interrupts[0].value if raw_interrupts else None
        return WorkflowResult(
            run_id=run_id,
            status=self._status(state, bool(raw_interrupts)),
            state=state,
            interrupt=payload if isinstance(payload, dict) else None,
        )

    @staticmethod
    def _status(state: AgentState, interrupted: bool) -> str:
        if interrupted:
            return "WAITING_APPROVAL"
        if state.get("error_code") == "APPROVAL_REJECTED" or state.get("sql_risk") == "blocked":
            return "REJECTED"
        if state.get("error_code"):
            return "FAILED"
        if state.get("answer"):
            return "COMPLETED"
        return "PLANNING"
