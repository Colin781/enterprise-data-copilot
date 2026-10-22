from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.mcp_server import ServiceBoundary, build_mcp
from app.retrieval.factory import create_metric_retrieval_service
from app.retrieval.repository import InMemoryMetricKnowledgeRepository
from app.settings import get_agent_workflow_settings


def test_mcp_handshake_discovery_call_and_tenant_boundary():
    retrieval = create_metric_retrieval_service(InMemoryMetricKnowledgeRepository())
    tenant = uuid4()
    retrieval.ingest(
        tenant_id=tenant,
        title="Metrics",
        source_name="m.md",
        source_type="MARKDOWN",
        payload=b"# Revenue\nRevenue uses quantity and price.",
    )
    server = build_mcp(lambda: SimpleNamespace(retrieval_service=retrieval))

    @asynccontextmanager
    async def lifespan(app):
        async with server.session_manager.run():
            yield

    app = FastAPI(lifespan=lifespan)
    app.mount("/mcp", ServiceBoundary(server.streamable_http_app()))
    headers = {
        "Authorization": "Bearer " + get_agent_workflow_settings().service_token.get_secret_value(),
        "X-Tenant-Id": str(tenant),
        "X-User-Id": str(uuid4()),
        "X-User-Role": "ANALYST",
        "Accept": "application/json, text/event-stream",
    }
    with TestClient(app) as client:

        def call(method, params=None, auth=headers):
            return client.post(
                "/mcp/",
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
                headers=auth,
            )

        assert call("tools/list", auth={"Accept": headers["Accept"]}).status_code == 401
        init = call(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        )
        assert init.status_code == 200
        assert "serverInfo" in init.json()["result"]
        tools = call("tools/list").json()["result"]["tools"]
        assert len(tools) == 5
        assert all(t["annotations"]["readOnlyHint"] for t in tools)
        args = {"name": "search_knowledge", "arguments": {"query": "Revenue"}}
        result = call("tools/call", args).json()["result"]
        assert not result.get("isError") and "Revenue" in str(result)
        other = {**headers, "X-Tenant-Id": str(uuid4())}
        assert "Revenue uses" not in str(call("tools/call", args, other).json())
        unknown = call("tools/call", {"name": "execute_sql", "arguments": {}}).json()["result"]
        assert unknown["isError"] is True
        bad = call(
            "tools/call",
            {"name": "search_knowledge", "arguments": {"query": "Revenue", "limit": 500}},
        ).json()["result"]
        assert bad["isError"] is True
