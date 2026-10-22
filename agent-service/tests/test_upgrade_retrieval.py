from uuid import uuid4

import httpx
import pytest

from app.retrieval.benchmark import benchmark
from app.retrieval.evaluation import RAGGoldCase
from app.retrieval.factory import create_metric_retrieval_service
from app.retrieval.providers import HTTPEmbeddingProvider, HTTPReranker, RetrievalProviderError
from app.retrieval.repository import InMemoryMetricKnowledgeRepository
from app.settings import RetrievalSettings


def embedding_client(payload, status=200):
    return httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(status, json=payload))
    )


def provider(payload):
    return HTTPEmbeddingProvider(
        base_url="https://example.test/v1",
        model="semantic",
        dimensions=16,
        client=embedding_client(payload),
    )


def test_embeddings_reorder_normalize_and_record_usage():
    p = provider(
        {
            "data": [
                {"index": 1, "embedding": [0, 2] + [0] * 14},
                {"index": 0, "embedding": [3] + [0] * 15},
            ],
            "usage": {"prompt_tokens": 7},
        }
    )
    a, b = p.embed(["first", "second"])
    assert a[0] == 1 and b[1] == 1
    assert p.input_tokens == 7
    assert p.profile.startswith("http:") and p.profile.endswith(":semantic:16")


@pytest.mark.parametrize(
    "data",
    [
        [],
        [{"index": 1, "embedding": [1] * 16}],
        [{"index": 0, "embedding": [1] * 15}],
        [{"index": 0, "embedding": [0] * 16}],
        [{"index": 0, "embedding": ["nan"] * 16}],
    ],
)
def test_embeddings_reject_bad_vectors(data):
    with pytest.raises(RetrievalProviderError):
        provider({"data": data}).embed(["text"])


def test_authentication_failure_is_not_retried_or_leaked():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(401, text="secret credential")

    p = HTTPEmbeddingProvider(
        base_url="https://example.test",
        model="test",
        dimensions=16,
        key="secret",
        client=httpx.Client(transport=httpx.MockTransport(handle)),
    )
    with pytest.raises(RetrievalProviderError) as error:
        p.embed(["text"])
    assert len(calls) == 1
    assert "secret" not in str(error.value)


def test_transient_failure_retries_with_limit(monkeypatch):
    monkeypatch.setattr("app.retrieval.providers.time.sleep", lambda _: None)
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(503, json={})

    p = HTTPEmbeddingProvider(
        base_url="https://example.test",
        model="test",
        dimensions=16,
        attempts=2,
        client=httpx.Client(transport=httpx.MockTransport(handle)),
    )
    with pytest.raises(RetrievalProviderError):
        p.embed(["text"])
    assert len(calls) == 2


def test_four_modes_and_true_multi_relevant_recall():
    tenant = uuid4()
    service = create_metric_retrieval_service(
        InMemoryMetricKnowledgeRepository(), RetrievalSettings(reranker_provider="overlap")
    )
    service.ingest(
        tenant_id=tenant,
        title="Metrics",
        source_name="metrics.md",
        source_type="MARKDOWN",
        payload=b"# Revenue\nRevenue uses quantity and price.",
    )
    cases = [
        RAGGoldCase(
            id="one",
            question="Revenue",
            answerable=True,
            relevant_sections=("metrics.md#revenue", "missing-section"),
        )
    ]
    report = benchmark(service, tenant, cases)
    assert len(report["reports"]) == 4
    assert all(r["recall_at_5"] == 0.5 for r in report["reports"])
    assert report["cost_usd"] is None and report["answer_accuracy"] is None


def test_reranker_reorders_and_rejects_invalid_indices():
    tenant = uuid4()
    service = create_metric_retrieval_service(InMemoryMetricKnowledgeRepository())
    service.ingest(
        tenant_id=tenant,
        title="Metrics",
        source_name="m.md",
        source_type="MARKDOWN",
        payload=b"# Revenue\nRevenue definition.\n## Units\nRevenue uses units.",
    )
    hits = service.retrieve(tenant_id=tenant, query="Revenue").hits
    payload = {"results": [{"index": i, "relevance_score": i} for i in range(len(hits))]}
    reranker = HTTPReranker(
        url="https://example.test/rerank", model="cross-encoder", client=embedding_client(payload)
    )
    assert reranker.rerank("Revenue", hits)[0].citation == hits[-1].citation
    bad = HTTPReranker(
        url="https://example.test/rerank",
        model="cross-encoder",
        client=embedding_client({"results": [{"index": 900, "relevance_score": 1}]}),
    )
    with pytest.raises(RetrievalProviderError):
        bad.rerank("Revenue", hits)
