import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import app


async def get_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/health")


async def get_metrics():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/health")
        return await client.get("/metrics")


def test_health_reports_agent_service_as_up() -> None:
    response = asyncio.run(get_health())

    assert response.status_code == 200
    assert response.json()["service"] == "agent-service"
    assert response.json()["status"] == "UP"
    assert response.json()["version"] == "0.1.0"


def test_metrics_exposes_prometheus_without_sensitive_request_values() -> None:
    response = asyncio.run(get_metrics())

    assert response.status_code == 200
    assert "copilot_agent_http_requests_total" in response.text
    assert "copilot_agent_http_request_duration_seconds_bucket" in response.text
