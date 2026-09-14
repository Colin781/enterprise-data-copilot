from datetime import UTC, datetime
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.settings import get_settings


class HealthResponse(BaseModel):
    service: str
    status: Literal["UP"]
    version: str
    timestamp: datetime


settings = get_settings()
app = FastAPI(
    title="Enterprise Data Copilot Agent API",
    version=settings.version,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/health", response_model=HealthResponse, tags=["operations"])
async def health() -> HealthResponse:
    return HealthResponse(
        service=settings.service_name,
        status="UP",
        version=settings.version,
        timestamp=datetime.now(UTC),
    )
