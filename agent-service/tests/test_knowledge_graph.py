import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.knowledge_graph.api import router
from app.knowledge_graph.metadata import metadata_extraction
from app.knowledge_graph.models import Extraction, ExtractRequest, GraphAnswerDraft
from app.knowledge_graph.repository import MemoryGraphStore
from app.knowledge_graph.service import KnowledgeGraphService
from app.metadata.models import SchemaSnapshot
from app.retrieval.factory import create_metric_retrieval_service
from app.retrieval.repository import InMemoryMetricKnowledgeRepository
from app.settings import get_agent_workflow_settings


def sample():
    request = ExtractRequest(
        source_id=uuid4(),
        source_name="metric.md",
        text="Revenue uses order_details.quantity. Quantity is a column.",
    )
    extracted = Extraction(
        entities=[
            {
                "id": "revenue",
                "name": "Revenue",
                "kind": "Metric",
                "evidence": "Revenue",
                "confidence": 0.9,
            },
            {
                "id": "quantity",
                "name": "order_details.quantity",
                "kind": "Column",
                "evidence": "order_details.quantity",
                "confidence": 0.9,
            },
        ],
        relations=[
            {
                "source": "revenue",
                "target": "quantity",
                "kind": "USES_COLUMN",
                "evidence": "Revenue uses order_details.quantity.",
                "confidence": 0.9,
            }
        ],
    )
    return request, extracted


class FakeLLM:
    def __init__(self, output):
        self.output = output
        self.calls = 0

    async def generate(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(output=self.output)


def service(llm=None):
    return KnowledgeGraphService(
        MemoryGraphStore(),
        llm,
        create_metric_retrieval_service(InMemoryMetricKnowledgeRepository()),
    )


def test_metadata_import_is_deterministic_and_contains_foreign_keys_without_row_data():
    snapshot = SchemaSnapshot.model_validate_json(
        (Path(__file__).parents[2] / "metadata/northwind-schema-v1.json").read_text()
    )
    tenant = uuid4()
    request, extraction = metadata_extraction(snapshot, tenant)
    svc = service()
    graph = svc.persist(tenant, request, extraction)
    assert len(graph.nodes) > 40
    assert any(edge.kind == "JOINS_WITH" for edge in graph.edges)
    assert any(node.name == "order_details.quantity" for node in graph.nodes)
    assert metadata_extraction(snapshot, tenant)[0].source_id == request.source_id


def test_extraction_preserves_evidence_and_is_idempotent_and_tenant_isolated():
    request, extraction = sample()
    tenant, other = uuid4(), uuid4()
    svc = service(FakeLLM(extraction))
    graph = asyncio.run(svc.extract(tenant, request))
    again = asyncio.run(svc.extract(tenant, request))
    assert graph.nodes[0].id == again.nodes[0].id
    assert len(svc.store.subgraph(tenant, "Revenue", 1, 60).nodes) == 2
    assert svc.store.subgraph(other, "", 3, 60).nodes == []
    assert graph.edges[0].source_id == request.source_id
    assert graph.edges[0].extracted_at.tzinfo is not None
    assert len(svc.store.path(tenant, graph.nodes[0].id, graph.nodes[1].id, 1).edges) == 1
    assert svc.store.path(other, graph.nodes[0].id, graph.nodes[1].id, 3).nodes == []


def test_hallucinated_quote_does_not_persist():
    request, extraction = sample()
    extraction.entities[0].evidence = "fabricated evidence"
    svc = service()
    with pytest.raises(ValueError, match="exact quote"):
        svc.persist(uuid4(), request, extraction)
    assert not svc.store.graphs


def test_unknown_endpoint_and_duplicate_ids_rejected():
    _, extraction = sample()
    data = extraction.model_dump()
    data["relations"][0]["target"] = "unknown"
    with pytest.raises(ValidationError):
        Extraction.model_validate(data)
    data = extraction.model_dump()
    data["entities"][1]["id"] = "revenue"
    with pytest.raises(ValidationError):
        Extraction.model_validate(data)


def test_graph_answer_requires_supported_citations_and_refuses_empty_corpus():
    request, extraction = sample()
    tenant = uuid4()
    llm = FakeLLM(GraphAnswerDraft(answer="Unsupported", citation_ids=["unknown"]))
    svc = service(llm)
    empty = asyncio.run(svc.answer(tenant, "Revenue"))
    assert not empty.should_answer and llm.calls == 0
    graph = svc.persist(tenant, request, extraction)
    with pytest.raises(ValueError, match="unknown evidence"):
        asyncio.run(svc.answer(tenant, "Revenue"))
    llm.output = GraphAnswerDraft(
        answer="Revenue uses quantity.", citation_ids=["edge:" + graph.edges[0].id]
    )
    answer = asyncio.run(svc.answer(tenant, "Revenue"))
    assert answer.should_answer and answer.citations[0]["text"] in request.text


def test_graph_api_service_auth_admin_permissions_and_bounds():
    request, extraction = sample()
    svc = service(FakeLLM(extraction))
    app = FastAPI()
    app.include_router(router)
    app.state.graph_service = svc
    client = TestClient(app)
    tenant = uuid4()
    headers = {
        "Authorization": "Bearer " + get_agent_workflow_settings().service_token.get_secret_value(),
        "X-Tenant-Id": str(tenant),
        "X-User-Role": "ANALYST",
    }
    body = request.model_dump(mode="json")
    assert client.post("/internal/v1/graph/extract", json=body).status_code in {401, 422}
    assert client.post("/internal/v1/graph/extract", headers=headers, json=body).status_code == 403
    headers["X-User-Role"] = "ADMIN"
    assert client.post("/internal/v1/graph/extract", headers=headers, json=body).status_code == 200
    assert (
        client.post("/internal/v1/graph/search", headers=headers, json={"depth": 99}).status_code
        == 422
    )
    headers["X-Tenant-Id"] = str(uuid4())
    assert client.post("/internal/v1/graph/search", headers=headers, json={}).json()["nodes"] == []
