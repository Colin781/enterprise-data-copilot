import secrets
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.agent.models import ApprovalResume, StartRun, WorkflowResult
from app.agent.service import AgentWorkflowService, WorkflowConflictError, WorkflowIdentityError
from app.observability import trace_id_from_traceparent
from app.settings import AgentWorkflowSettings, get_agent_workflow_settings

router = APIRouter(prefix="/internal/v1/runs", tags=["runs"])


class StartRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1, max_length=64)
    data_source_id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1, max_length=4_000)
    requested_at: datetime


class ResumeRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str = Field(min_length=1, max_length=64)
    decision: Literal["approved", "rejected"]
    decided_by: str = Field(min_length=1, max_length=64)
    comment: str | None = Field(default=None, max_length=500)


def get_workflow_service(request: Request) -> AgentWorkflowService:
    workflow = getattr(request.app.state, "workflow_service", None)
    if workflow is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "workflow service is unavailable")
    return workflow


def authorize_service(
    authorization: Annotated[str, Header()],
    settings: Annotated[AgentWorkflowSettings, Depends(get_agent_workflow_settings)],
) -> None:
    scheme, _, token = authorization.partition(" ")
    expected = settings.service_token.get_secret_value()
    if scheme.lower() != "bearer" or not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid service credential")


def trace_id(traceparent: str) -> str:
    try:
        return trace_id_from_traceparent(traceparent)
    except ValueError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid traceparent") from error


@router.post(
    "",
    response_model=WorkflowResult,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(authorize_service)],
)
def start_run(
    body: StartRunRequest,
    workflow: Annotated[AgentWorkflowService, Depends(get_workflow_service)],
    tenant_id: Annotated[str, Header(alias="X-Tenant-Id")],
    user_id: Annotated[str, Header(alias="X-User-Id")],
    user_role: Annotated[Literal["ADMIN", "ANALYST", "VIEWER"], Header(alias="X-User-Role")],
    traceparent: Annotated[str, Header()],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=128)],
) -> WorkflowResult:
    del idempotency_key
    try:
        return workflow.start(
            StartRun(
                run_id=body.job_id,
                tenant_id=tenant_id,
                user_id=user_id,
                role=user_role,
                data_source_id=body.data_source_id,
                trace_id=trace_id(traceparent),
                question=body.question,
            )
        )
    except WorkflowConflictError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error


@router.post(
    "/{run_id}/resume",
    response_model=WorkflowResult,
    dependencies=[Depends(authorize_service)],
)
def resume_run(
    run_id: str,
    body: ResumeRunRequest,
    workflow: Annotated[AgentWorkflowService, Depends(get_workflow_service)],
    tenant_id: Annotated[str, Header(alias="X-Tenant-Id")],
    user_role: Annotated[Literal["ADMIN", "ANALYST", "VIEWER"], Header(alias="X-User-Role")],
) -> WorkflowResult:
    if user_role != "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "administrator role required")
    try:
        return workflow.resume(
            run_id=run_id,
            tenant_id=tenant_id,
            resume=ApprovalResume.model_validate(body.model_dump()),
        )
    except WorkflowConflictError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except WorkflowIdentityError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
