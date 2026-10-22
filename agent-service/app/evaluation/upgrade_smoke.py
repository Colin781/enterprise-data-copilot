"""Read-only full-stack smoke test. Credentials stay in memory; no model calls."""

import argparse
import json
from pathlib import Path

import httpx
from dotenv import dotenv_values


def smoke(base_url, web_url, env_path):
    config = dotenv_values(env_path)
    checks = []
    with httpx.Client(timeout=15) as client:

        def check(name, response, expected=200):
            if response.status_code != expected:
                raise RuntimeError(f"{name}: expected HTTP {expected}, got {response.status_code}")
            checks.append({"name": name, "status": response.status_code})
            return response

        check("platform_health", client.get(base_url + "/health"))
        check("web_health", client.get(web_url + "/health"))
        check("anonymous_graph_denied", client.post(base_url + "/api/graph/search", json={}), 401)
        login = check(
            "admin_login",
            client.post(
                base_url + "/api/auth/login",
                json={
                    "tenant_slug": config.get("PLATFORM_BOOTSTRAP_TENANT_SLUG", "northwind"),
                    "email": config.get("PLATFORM_BOOTSTRAP_ADMIN_EMAIL", "admin@northwind.local"),
                    "password": config.get("PLATFORM_BOOTSTRAP_PASSWORD", "change-me-demo"),
                },
            ),
        ).json()
        headers = {"Authorization": "Bearer " + login["access_token"]}
        check(
            "graph_search",
            client.post(
                base_url + "/api/graph/search",
                headers=headers,
                json={"query": "", "depth": 0, "limit": 10},
            ),
        )
        check(
            "knowledge_lexical_search",
            client.post(
                base_url + "/api/knowledge/search",
                headers=headers,
                json={"query": "Revenue", "mode": "lexical", "limit": 3},
            ),
        )
        headers["Accept"] = "application/json, text/event-stream"

        def mcp(method, params, request_id):
            return check(
                "mcp_" + method,
                client.post(
                    base_url + "/api/mcp",
                    headers=headers,
                    json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
                ),
            )

        mcp(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "upgrade-smoke", "version": "1"},
            },
            1,
        )
        tools = mcp("tools/list", {}, 2).json()["result"]["tools"]
        if len(tools) != 5 or not all(t["annotations"]["readOnlyHint"] for t in tools):
            raise RuntimeError("MCP tool inventory is not the expected read-only set")
        result = mcp("tools/call", {"name": "search_catalog", "arguments": {"query": ""}}, 3).json()
        if result.get("error") or result.get("result", {}).get("isError"):
            raise RuntimeError("MCP catalog tool failed")
        mcp("resources/read", {"uri": "copilot://capabilities"}, 4)
        return {
            "mode": "read_only_full_stack_smoke",
            "model_calls": 0,
            "checks": checks,
            "mcp_tool_count": len(tools),
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--web-url", default="http://localhost:3000")
    parser.add_argument("--env", type=Path, default=Path("../.env"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = smoke(args.base_url.rstrip("/"), args.web_url.rstrip("/"), args.env)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Passed {len(result['checks'])} full-stack checks; no model calls.")


if __name__ == "__main__":
    main()
