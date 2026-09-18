from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agent.state import AgentState

RunStatus = Literal["PLANNING", "WAITING_APPROVAL", "COMPLETED", "REJECTED", "FAILED"]


class StartRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1, max_length=64)
    tenant_id: str = Field(min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=64)
    role: Literal["ADMIN", "ANALYST", "VIEWER"]
    data_source_id: str = Field(min_length=1, max_length=64)
    trace_id: str = Field(min_length=16, max_length=64)
    question: str = Field(min_length=1, max_length=4_000)

    def initial_state(self) -> AgentState:
        return AgentState(
            run_id=self.run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            role=self.role,
            data_source_id=self.data_source_id,
            trace_id=self.trace_id,
            question=self.question.strip(),
            attempts=0,
            risk_reasons=[],
            metric_context=[],
            candidate_tables=[],
            citations=[],
            rows=[],
            columns=[],
            error_code=None,
        )


class ApprovalResume(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_id: str = Field(min_length=1, max_length=64)
    decision: Literal["approved", "rejected"]
    decided_by: str = Field(min_length=1, max_length=64)
    comment: str | None = Field(default=None, max_length=500)


class WorkflowResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    status: RunStatus
    state: AgentState
    interrupt: dict[str, Any] | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
