"""Official MCP SDK, stateless HTTP; Java remains the public JWT/audit boundary."""

import asyncio
import json
import secrets
from uuid import UUID

import httpx
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.responses import JSONResponse

from app.settings import get_agent_workflow_settings

READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)


class ServiceBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope["headers"])
            expected = (
                b"Bearer " + get_agent_workflow_settings().service_token.get_secret_value().encode()
            )
            authenticated = secrets.compare_digest(headers.get(b"authorization", b""), expected)
            try:
                UUID(headers.get(b"x-tenant-id", b"").decode())
                UUID(headers.get(b"x-user-id", b"").decode())
                valid_role = headers.get(b"x-user-role") in {b"ADMIN", b"ANALYST", b"VIEWER"}
            except ValueError:
                valid_role = False
            if not authenticated or not valid_role:
                await JSONResponse({"error": "service authentication required"}, status_code=401)(
                    scope, receive, send
                )
                return
        await self.app(scope, receive, send)


def build_mcp(get_state):
    server = FastMCP(
        "Enterprise Data Copilot",
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
        max_request_body_size=32_768,
        transport_security=TransportSecuritySettings(
            allowed_hosts=["localhost:*", "127.0.0.1:*", "agent-service:*", "testserver"],
            allowed_origins=["http://localhost:*", "http://127.0.0.1:*"],
        ),
    )

    def identity(ctx):
        request = ctx.request_context.request
        if request is None:
            raise ValueError("HTTP identity required")
        return UUID(request.headers["X-Tenant-Id"]), request.headers

    @server.tool(annotations=READ_ONLY)
    async def search_knowledge(
        query: str, ctx: Context, limit: int = Field(default=5, ge=1, le=20)
    ) -> dict:
        """Search documents in the authenticated tenant, with source citations."""
        tenant, _ = identity(ctx)
        result = await asyncio.to_thread(
            get_state().retrieval_service.retrieve, tenant_id=tenant, query=query, limit=limit
        )
        return result.model_dump(mode="json")

    @server.tool(annotations=READ_ONLY)
    async def metric_definition(name: str, ctx: Context) -> dict:
        """Find a business metric definition and its evidence."""
        tenant, _ = identity(ctx)
        result = await asyncio.to_thread(
            get_state().retrieval_service.retrieve,
            tenant_id=tenant,
            query=name,
            mode="lexical",
            limit=3,
        )
        return result.model_dump(mode="json")

    @server.tool(annotations=READ_ONLY)
    async def relationship_graph(
        query: str, ctx: Context, depth: int = Field(default=1, ge=0, le=3)
    ) -> dict:
        """Read a bounded relationship subgraph, never arbitrary Cypher."""
        tenant, _ = identity(ctx)
        graph = getattr(get_state(), "graph_service", None)
        if graph is None:
            raise ValueError("graph service is disabled")
        result = await asyncio.to_thread(graph.store.subgraph, tenant, query[:4000], depth, 60)
        return result.model_dump(mode="json")

    async def platform_get(ctx, path):
        _, headers = identity(ctx)
        caller = headers.get("X-Caller-Token", "")
        if not caller:
            raise ValueError("caller authorization required")
        settings = get_agent_workflow_settings()
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                str(settings.platform_api_url).rstrip("/") + path,
                headers={"Authorization": "Bearer " + caller},
            )
        if response.status_code != 200:
            raise ValueError("resource unavailable or access denied")
        return response.json()

    @server.tool(annotations=READ_ONLY)
    async def search_catalog(query: str, ctx: Context) -> list[dict]:
        """Search authorized data source names; credentials and hosts are never returned."""
        sources = await platform_get(ctx, "/api/data-sources")
        return [
            {key: item[key] for key in ("id", "name", "allowed_schema")}
            for item in sources
            if query.casefold() in item["name"].casefold()
        ][:20]

    @server.tool(annotations=READ_ONLY)
    async def job_status(job_id: UUID, ctx: Context) -> dict:
        """Read a job's status with the platform's tenant and owner authorization."""
        job = await platform_get(ctx, f"/api/analysis/jobs/{job_id}")
        return {key: job[key] for key in ("id", "status", "updated_at")}

    @server.resource("copilot://capabilities")
    def capabilities() -> str:
        return json.dumps(
            {
                "read_only": True,
                "tenant_identity": "verified platform JWT",
                "tools": [
                    "search_knowledge",
                    "metric_definition",
                    "relationship_graph",
                    "search_catalog",
                    "job_status",
                ],
            }
        )

    return server
