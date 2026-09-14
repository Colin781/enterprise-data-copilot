import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import app


async def get_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/health")


def test_health_reports_agent_service_as_up() -> None:
    response = asyncio.run(get_health())

    assert response.status_code == 200
    assert response.json()["service"] == "agent-service"
    assert response.json()["status"] == "UP"
    assert response.json()["version"] == "0.1.0"
