from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Literal

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

from app.agent.api import router as agent_router
from app.agent.factory import create_production_workflow_service
from app.observability import configure_observability, observe_http, prometheus_response
from app.retrieval.api import router as knowledge_router
from app.retrieval.factory import create_production_retrieval_service
from app.settings import get_observability_settings, get_settings


class HealthResponse(BaseModel):
    service: str
    status: Literal["UP"]
    version: str
    timestamp: datetime


settings = get_settings()
observability = get_observability_settings()
configure_observability(settings, observability)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    with create_production_workflow_service(setup_checkpointer=True) as workflow:
        application.state.workflow_service = workflow
        application.state.retrieval_service = create_production_retrieval_service()
        yield


app = FastAPI(
    title="Enterprise Data Copilot Agent API",
    version=settings.version,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)
app.include_router(agent_router)
app.include_router(knowledge_router)


@app.middleware("http")
async def metrics_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if not observability.metrics_enabled:
        return await call_next(request)
    return await observe_http(request, call_next)


@app.get("/health", response_model=HealthResponse, tags=["operations"])
async def health() -> HealthResponse:
    return HealthResponse(
        service=settings.service_name,
        status="UP",
        version=settings.version,
        timestamp=datetime.now(UTC),
    )


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    if not observability.metrics_enabled:
        return Response(status_code=404)
    return prometheus_response()
