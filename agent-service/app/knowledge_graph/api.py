from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from neo4j.exceptions import Neo4jError, ServiceUnavailable
from pydantic import Field, model_validator

from app.knowledge_graph.models import ExtractRequest, GraphAnswer, GraphQuery, Subgraph
from app.knowledge_graph.service import KnowledgeGraphService
from app.llm.errors import LLMError
from app.retrieval.api import authorize_service, get_retrieval_service
from app.retrieval.errors import RetrievalError
from app.retrieval.models import RetrievalMode
from app.retrieval.service import MetricRetrievalService

router = APIRouter(prefix="/internal/v1", dependencies=[Depends(authorize_service)])


def get_graph_service(request: Request):
    service = getattr(request.app.state, "graph_service", None)
    if service is None:
        raise HTTPException(503, "graph service is disabled")
    return service


def require_graph_admin(role: Annotated[str, Header(alias="X-User-Role")]):
    if role != "ADMIN":
        raise HTTPException(403, "administrator role required")


@router.post("/graph/extract", response_model=Subgraph, dependencies=[Depends(require_graph_admin)])
async def extract(
    body: ExtractRequest,
    tenant: Annotated[UUID, Header(alias="X-Tenant-Id")],
    service: Annotated[KnowledgeGraphService, Depends(get_graph_service)],
):
    try:
        return await service.extract(tenant, body)
    except ValueError as error:
        raise HTTPException(422, "invalid extraction or unsupported evidence") from error
    except (Neo4jError, ServiceUnavailable, LLMError) as error:
        raise HTTPException(502, "graph extraction service unavailable") from error


@router.post("/graph/search", response_model=Subgraph)
def search(
    body: GraphQuery,
    tenant: Annotated[UUID, Header(alias="X-Tenant-Id")],
    service: Annotated[KnowledgeGraphService, Depends(get_graph_service)],
):
    try:
        return service.store.subgraph(tenant, body.query, body.depth, body.limit)
    except (Neo4jError, ServiceUnavailable) as error:
        raise HTTPException(503, "graph store unavailable") from error


class PathQuery(GraphQuery):
    source: str = Field(min_length=1, max_length=80)
    target: str = Field(min_length=1, max_length=80)
    depth: int = Field(default=3, ge=1, le=3)

    @model_validator(mode="after")
    def distinct_endpoints(self):
        if self.source == self.target:
            raise ValueError("path endpoints must differ")
        return self


@router.post("/graph/path", response_model=Subgraph)
def path(
    body: PathQuery,
    tenant: Annotated[UUID, Header(alias="X-Tenant-Id")],
    service: Annotated[KnowledgeGraphService, Depends(get_graph_service)],
):
    return service.store.path(tenant, body.source, body.target, body.depth)


@router.post("/graph/answer", response_model=GraphAnswer)
async def answer(
    body: GraphQuery,
    tenant: Annotated[UUID, Header(alias="X-Tenant-Id")],
    service: Annotated[KnowledgeGraphService, Depends(get_graph_service)],
):
    if not body.query.strip():
        raise HTTPException(422, "question is required")
    try:
        return await service.answer(tenant, body.query)
    except ValueError as error:
        raise HTTPException(422, "invalid answer evidence") from error
    except (Neo4jError, ServiceUnavailable, LLMError, RetrievalError) as error:
        raise HTTPException(502, "graph answer service unavailable") from error


class SearchRequest(GraphQuery):
    mode: RetrievalMode = "hybrid"
    limit: int = Field(default=5, ge=1, le=20)


@router.post("/knowledge/search")
def knowledge_search(
    body: SearchRequest,
    tenant: Annotated[UUID, Header(alias="X-Tenant-Id")],
    service: Annotated[MetricRetrievalService, Depends(get_retrieval_service)],
):
    try:
        return service.retrieve(
            tenant_id=tenant, query=body.query, mode=body.mode, limit=body.limit
        )
    except ValueError as error:
        raise HTTPException(422, "invalid search configuration or query") from error
    except RetrievalError as error:
        return JSONResponse(
            status_code=409 if error.code == "RAG_REINDEX_REQUIRED" else 502,
            content={"code": error.code, "message": error.public_message},
        )
