import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.api import router
from app.agent.graph import build_agent_graph
from app.agent.service import AgentWorkflowService
from app.agent.steps import InMemoryAgentStepSink
from app.settings import AgentWorkflowSettings, get_agent_workflow_settings
from tests.test_agent_workflow import ScriptedActions


def test_internal_run_boundary_requires_service_token_and_admin_resume() -> None:
    application = FastAPI()
    application.include_router(router)
    service_token = "test-service-token"
    application.dependency_overrides[get_agent_workflow_settings] = lambda: AgentWorkflowSettings(
        service_token=service_token
    )
    application.state.workflow_service = AgentWorkflowService(
        build_agent_graph(
            actions=ScriptedActions(risk="approval"),
            step_sink=InMemoryAgentStepSink(),
            checkpointer=InMemorySaver(),
        )
    )
    job_id = str(uuid4())
    tenant_id = str(uuid4())
    user_id = str(uuid4())
    common_headers = {
        "Authorization": f"Bearer {service_token}",
        "X-Tenant-Id": tenant_id,
        "X-User-Id": user_id,
        "X-User-Role": "ANALYST",
        "traceparent": f"00-{uuid4().hex}-{uuid4().hex[:16]}-01",
        "Idempotency-Key": "1234567890abcdef",
    }
    start_body = {
        "job_id": job_id,
        "data_source_id": str(uuid4()),
        "question": "sales by month",
        "requested_at": datetime.now(UTC).isoformat(),
    }

    async def scenario() -> None:
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            unauthorized = await client.post(
                "/internal/v1/runs",
                json=start_body,
                headers={**common_headers, "Authorization": "Bearer wrong"},
            )
            waiting = await client.post(
                "/internal/v1/runs", json=start_body, headers=common_headers
            )
            approval_id = str(uuid4())
            resume_body = {
                "approval_id": approval_id,
                "decision": "approved",
                "decided_by": str(uuid4()),
            }
            forbidden = await client.post(
                f"/internal/v1/runs/{job_id}/resume",
                json=resume_body,
                headers=common_headers,
            )
            approved = await client.post(
                f"/internal/v1/runs/{job_id}/resume",
                json=resume_body,
                headers={**common_headers, "X-User-Role": "ADMIN"},
            )
            duplicate = await client.post(
                f"/internal/v1/runs/{job_id}/resume",
                json=resume_body,
                headers={**common_headers, "X-User-Role": "ADMIN"},
            )

        assert unauthorized.status_code == 401
        assert waiting.status_code == 202
        assert waiting.json()["status"] == "WAITING_APPROVAL"
        assert forbidden.status_code == 403
        assert approved.status_code == 200
        assert approved.json()["status"] == "COMPLETED"
        assert duplicate.status_code == 409

    asyncio.run(scenario())
