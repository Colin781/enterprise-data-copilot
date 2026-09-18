import base64
import binascii
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.agent.api import trace_id
from app.retrieval.errors import RetrievalError
from app.retrieval.models import SourceType, StoredMetricDocument
from app.retrieval.service import MetricRetrievalService
from app.settings import AgentWorkflowSettings, get_agent_workflow_settings

router = APIRouter(prefix="/internal/v1/knowledge/documents", tags=["knowledge"])


class KnowledgeIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=240)
    source_name: str = Field(min_length=1, max_length=255)
    source_type: SourceType
    content_base64: str = Field(min_length=1, max_length=14_000_000, repr=False)


def get_retrieval_service(request: Request) -> MetricRetrievalService:
    service = getattr(request.app.state, "retrieval_service", None)
    if service is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "retrieval service is unavailable")
    return service


def authorize_service(
    authorization: Annotated[str, Header()],
    settings: Annotated[AgentWorkflowSettings, Depends(get_agent_workflow_settings)],
) -> None:
    scheme, _, token = authorization.partition(" ")
    expected = settings.service_token.get_secret_value()
    if scheme.lower() != "bearer" or not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid service credential")


@router.post(
    "",
    response_model=StoredMetricDocument,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(authorize_service)],
)
def ingest_document(
    body: KnowledgeIngestRequest,
    service: Annotated[MetricRetrievalService, Depends(get_retrieval_service)],
    tenant_id: Annotated[UUID, Header(alias="X-Tenant-Id")],
    user_id: Annotated[UUID, Header(alias="X-User-Id")],
    traceparent: Annotated[str, Header()],
) -> StoredMetricDocument:
    trace_id(traceparent)
    try:
        payload = base64.b64decode(body.content_base64, validate=True)
        return service.ingest(
            tenant_id=tenant_id,
            title=body.title,
            source_name=body.source_name,
            source_type=body.source_type,
            payload=payload,
            created_by=user_id,
        )
    except (binascii.Error, ValueError) as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid document payload"
        ) from error
    except RetrievalError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": error.code, "message": error.public_message},
        ) from error
