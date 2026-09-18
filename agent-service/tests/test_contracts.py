import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"
JAVA_STATUS_PATH = (
    Path(__file__).resolve().parents[2]
    / "platform-api"
    / "src"
    / "main"
    / "java"
    / "com"
    / "example"
    / "copilot"
    / "analysis"
    / "domain"
    / "AnalysisJobStatus.java"
)
EXPECTED_JOB_STATUSES = {
    "CREATED",
    "PLANNING",
    "VALIDATING",
    "WAITING_APPROVAL",
    "RUNNING",
    "COMPLETED",
    "REJECTED",
    "FAILED",
    "CANCELLED",
}


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        return yaml.safe_load(source)


@pytest.mark.parametrize("filename", ["openapi-platform.yaml", "openapi-agent.yaml"])
def test_openapi_contract_is_valid(filename: str) -> None:
    validate(load_yaml(CONTRACTS_DIR / filename))


def test_event_contract_is_valid_json_schema() -> None:
    with (CONTRACTS_DIR / "events" / "analysis-job.schema.json").open(encoding="utf-8") as source:
        schema = json.load(source)

    Draft202012Validator.check_schema(schema)


def test_job_statuses_are_consistent_across_contracts() -> None:
    platform = load_yaml(CONTRACTS_DIR / "openapi-platform.yaml")
    agent = load_yaml(CONTRACTS_DIR / "openapi-agent.yaml")
    with (CONTRACTS_DIR / "events" / "analysis-job.schema.json").open(encoding="utf-8") as source:
        event = json.load(source)

    platform_statuses = set(platform["components"]["schemas"]["AnalysisJobStatus"]["enum"])
    agent_statuses = set(agent["components"]["schemas"]["AnalysisJobStatus"]["enum"])
    event_statuses = set(event["properties"]["status"]["enum"])

    assert platform_statuses == EXPECTED_JOB_STATUSES
    assert agent_statuses == EXPECTED_JOB_STATUSES
    assert event_statuses == EXPECTED_JOB_STATUSES


def test_java_job_statuses_match_contracts() -> None:
    java_source = JAVA_STATUS_PATH.read_text(encoding="utf-8")
    java_statuses = set(re.findall(r"^\s{4}([A-Z_]+),?$", java_source, flags=re.MULTILINE))

    assert java_statuses == EXPECTED_JOB_STATUSES


def test_browser_create_contract_does_not_accept_tenant_identity() -> None:
    platform = load_yaml(CONTRACTS_DIR / "openapi-platform.yaml")
    request_schema = platform["components"]["schemas"]["CreateAnalysisJobRequest"]

    assert request_schema["additionalProperties"] is False
    assert "tenant_id" not in request_schema["properties"]
    assert "user_id" not in request_schema["properties"]


def test_p3_data_source_contract_uses_secret_references_and_server_tenant_scope() -> None:
    platform = load_yaml(CONTRACTS_DIR / "openapi-platform.yaml")
    request_schema = platform["components"]["schemas"]["CreateDataSourceRequest"]
    response_schema = platform["components"]["schemas"]["DataSourceResource"]

    assert request_schema["additionalProperties"] is False
    assert request_schema["properties"]["secret_ref"]["writeOnly"] is True
    assert "password" not in request_schema["properties"]
    assert "tenant_id" not in request_schema["properties"]
    assert "host" not in response_schema["properties"]
    assert "secret_ref" not in response_schema["properties"]


def test_p1_api_boundaries_require_identity_idempotency_and_trace_context() -> None:
    platform = load_yaml(CONTRACTS_DIR / "openapi-platform.yaml")
    agent = load_yaml(CONTRACTS_DIR / "openapi-agent.yaml")

    platform_create = platform["paths"]["/api/analysis/jobs"]["post"]
    platform_parameters = {parameter["$ref"] for parameter in platform_create["parameters"]}
    assert platform_create["security"] == [{"bearerAuth": []}]
    assert "#/components/parameters/IdempotencyKey" in platform_parameters

    agent_run = agent["paths"]["/internal/v1/runs"]["post"]
    agent_parameters = {parameter["$ref"] for parameter in agent_run["parameters"]}
    assert agent_run["security"] == [{"serviceToken": []}]
    assert {
        "#/components/parameters/IdempotencyKey",
        "#/components/parameters/Traceparent",
        "#/components/parameters/TenantId",
        "#/components/parameters/UserId",
        "#/components/parameters/UserRole",
    } <= agent_parameters


def test_p1_trace_and_timing_fields_are_reserved() -> None:
    platform = load_yaml(CONTRACTS_DIR / "openapi-platform.yaml")
    agent = load_yaml(CONTRACTS_DIR / "openapi-agent.yaml")
    with (CONTRACTS_DIR / "events" / "analysis-job.schema.json").open(encoding="utf-8") as source:
        event = json.load(source)

    job_required = set(platform["components"]["schemas"]["AnalysisJobResource"]["required"])
    run_required = set(agent["components"]["schemas"]["StartRunResponse"]["required"])
    event_required = set(event["required"])

    assert {"trace_id", "created_at", "updated_at"} <= job_required
    assert {"trace_id", "accepted_at"} <= run_required
    assert {"event_version", "sequence", "trace_id", "occurred_at"} <= event_required


def test_p7_contract_exposes_durable_resume_approval_and_redacted_steps() -> None:
    platform = load_yaml(CONTRACTS_DIR / "openapi-platform.yaml")
    agent = load_yaml(CONTRACTS_DIR / "openapi-agent.yaml")

    resume = agent["paths"]["/internal/v1/runs/{runId}/resume"]["post"]
    assert resume["security"] == [{"serviceToken": []}]
    assert (
        resume["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/ResumeRunRequest"
    )
    assert "/api/approvals/{approvalId}/approve" in platform["paths"]
    assert "/api/approvals/{approvalId}/reject" in platform["paths"]
    assert "/api/analysis/jobs/{jobId}/steps" in platform["paths"]
    step = platform["components"]["schemas"]["AgentStepResource"]
    assert "input_summary" in step["properties"]
    assert "sql" not in step["properties"]
    assert "rows" not in step["properties"]


def test_p8_contract_exposes_ordered_sse_replay_without_making_redis_authoritative() -> None:
    platform = load_yaml(CONTRACTS_DIR / "openapi-platform.yaml")
    with (CONTRACTS_DIR / "events" / "analysis-job.schema.json").open(encoding="utf-8") as source:
        event = json.load(source)

    stream = platform["paths"]["/api/analysis/jobs/{jobId}/events"]["get"]
    headers = {parameter["name"] for parameter in stream["parameters"]}
    assert stream["security"] == [{"bearerAuth": []}]
    assert "Last-Event-ID" in headers
    assert "text/event-stream" in stream["responses"]["200"]["content"]
    assert {"event_version", "event_id", "sequence", "job_id", "tenant_id", "type"} <= set(
        event["required"]
    )
    assert event["properties"]["event_version"]["const"] == "1.0"
    assert "redis" not in platform["components"]["schemas"]["AnalysisJobResource"]["properties"]


def test_p9_contract_supports_closed_chart_results_and_managed_knowledge() -> None:
    platform = load_yaml(CONTRACTS_DIR / "openapi-platform.yaml")
    agent = load_yaml(CONTRACTS_DIR / "openapi-agent.yaml")

    job = platform["components"]["schemas"]["AnalysisJobResource"]
    chart = platform["components"]["schemas"]["ChartSpec"]
    assert {"columns", "rows", "chart", "citations"} <= set(job["required"])
    assert chart["additionalProperties"] is False
    assert set(chart["properties"]["type"]["enum"]) == {"bar", "line", "pie", "table"}
    assert "code" not in chart["properties"]
    assert "/api/metric-documents" in platform["paths"]
    assert "/api/approvals" in platform["paths"]
    assert "/internal/v1/knowledge/documents" in agent["paths"]
