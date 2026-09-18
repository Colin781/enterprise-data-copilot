import asyncio
import base64
from uuid import uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.retrieval.api import router
from app.retrieval.repository import InMemoryMetricKnowledgeRepository
from app.retrieval.service import MetricRetrievalService
from app.settings import AgentWorkflowSettings, get_agent_workflow_settings


def test_knowledge_ingest_requires_service_auth_and_scopes_document() -> None:
    application = FastAPI()
    application.include_router(router)
    service_token = "test-service-token"
    application.dependency_overrides[get_agent_workflow_settings] = lambda: AgentWorkflowSettings(
        service_token=service_token
    )
    application.state.retrieval_service = MetricRetrievalService(
        repository=InMemoryMetricKnowledgeRepository()
    )
    tenant_id = str(uuid4())
    user_id = str(uuid4())
    headers = {
        "Authorization": f"Bearer {service_token}",
        "X-Tenant-Id": tenant_id,
        "X-User-Id": user_id,
        "traceparent": f"00-{uuid4().hex}-{uuid4().hex[:16]}-01",
    }
    body = {
        "title": "Revenue definition",
        "source_name": "metrics.md",
        "source_type": "MARKDOWN",
        "content_base64": base64.b64encode(b"# Revenue\nPaid order revenue.").decode(),
    }

    async def scenario() -> None:
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            unauthorized = await client.post(
                "/internal/v1/knowledge/documents",
                json=body,
                headers={**headers, "Authorization": "Bearer wrong"},
            )
            invalid = await client.post(
                "/internal/v1/knowledge/documents",
                json={**body, "content_base64": "%%%"},
                headers=headers,
            )
            created = await client.post(
                "/internal/v1/knowledge/documents", json=body, headers=headers
            )

        assert unauthorized.status_code == 401
        assert invalid.status_code == 422
        assert created.status_code == 201
        assert created.json()["tenant_id"] == tenant_id
        assert created.json()["chunk_count"] == 1

    asyncio.run(scenario())
