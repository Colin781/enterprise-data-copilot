from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.retrieval import parsing
from app.retrieval.cache import RetrievalCache
from app.retrieval.embeddings import HashingEmbeddingProvider
from app.retrieval.errors import DocumentLimitError, DocumentParseError
from app.retrieval.evaluation import evaluate_modes, load_cases
from app.retrieval.factory import create_metric_retrieval_service
from app.retrieval.parsing import chunk_sections, parse_document
from app.retrieval.repository import InMemoryMetricKnowledgeRepository
from app.retrieval.service import MetricRetrievalService
from app.settings import RetrievalSettings

ROOT = Path(__file__).parents[2]
DOCUMENT = ROOT / "knowledge/northwind/retail-metrics-v1.md"
CASES = ROOT / "evaluation/northwind/rag-gold-v1.jsonl"


def service(
    repository: InMemoryMetricKnowledgeRepository | None = None,
) -> tuple[MetricRetrievalService, InMemoryMetricKnowledgeRepository]:
    store = repository or InMemoryMetricKnowledgeRepository()
    return (
        MetricRetrievalService(
            repository=store,
            embedding_provider=HashingEmbeddingProvider(64),
            min_lexical_score=0.08,
            min_vector_score=0.26,
        ),
        store,
    )


def ingest_baseline(retrieval: MetricRetrievalService, tenant_id: UUID) -> None:
    retrieval.ingest(
        tenant_id=tenant_id,
        title="Northwind 零售指标口径",
        source_name=DOCUMENT.name,
        source_type="MARKDOWN",
        payload=DOCUMENT.read_bytes(),
    )


def test_markdown_parser_preserves_section_and_line_locator() -> None:
    sections = parse_document(
        source_name="metrics.md",
        source_type="MARKDOWN",
        payload=b"# Metrics\n\nIntro.\n\n## Revenue\n\nQuantity times price.\n",
    )

    assert [section.title for section in sections] == ["Metrics", "Revenue"]
    assert sections[1].section_key == "metrics.md#revenue"
    assert sections[1].source_locator.startswith("lines=5-")


def test_pdf_parser_preserves_page_locator(monkeypatch: pytest.MonkeyPatch) -> None:
    class Page:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class Reader:
        is_encrypted = False
        pages = [Page("Revenue is quantity times price."), Page("Discount is a percentage.")]

    monkeypatch.setattr(parsing, "PdfReader", lambda _: Reader())
    sections = parse_document(source_name="metrics.pdf", source_type="PDF", payload=b"%PDF")

    assert len(sections) == 2
    assert sections[0].section_key == "metrics.pdf#page-1"
    assert sections[1].source_locator == "page=2"


def test_pdf_parser_rejects_encrypted_and_excessive_page_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class EncryptedReader:
        is_encrypted = True
        pages: list[object] = []

    monkeypatch.setattr(parsing, "PdfReader", lambda _: EncryptedReader())
    with pytest.raises(DocumentParseError):
        parse_document(source_name="secret.pdf", source_type="PDF", payload=b"%PDF")

    class LargeReader:
        is_encrypted = False
        pages = [object(), object()]

    monkeypatch.setattr(parsing, "PdfReader", lambda _: LargeReader())
    with pytest.raises(DocumentLimitError):
        parse_document(
            source_name="large.pdf",
            source_type="PDF",
            payload=b"%PDF",
            max_pdf_pages=1,
        )


def test_parser_rejects_empty_invalid_and_oversized_documents() -> None:
    with pytest.raises(DocumentParseError):
        parse_document(source_name="empty.md", source_type="MARKDOWN", payload=b"")
    with pytest.raises(DocumentParseError):
        parse_document(source_name="bad.md", source_type="MARKDOWN", payload=b"\xff")
    with pytest.raises(DocumentLimitError):
        parse_document(
            source_name="large.md",
            source_type="MARKDOWN",
            payload=b"12345",
            max_markdown_bytes=4,
        )


def test_chunking_is_bounded_and_overlaps_long_sections() -> None:
    sections = parse_document(
        source_name="long.md",
        source_type="MARKDOWN",
        payload=("# Long\n\n" + "revenue " * 100).encode(),
    )
    chunks = chunk_sections(sections, max_characters=200, overlap_characters=20)

    assert len(chunks) > 1
    assert all(len(section.content) <= 200 for section, _ in chunks)
    assert [ordinal for _, ordinal in chunks] == list(range(len(chunks)))


def test_hashing_embeddings_are_deterministic_normalized_and_private() -> None:
    provider = HashingEmbeddingProvider(64)
    first, second = provider.embed(("销售额 revenue", "销售额 revenue"))

    assert first == second
    assert len(first) == 64
    assert sum(value * value for value in first) == pytest.approx(1.0)


def test_factory_applies_central_retrieval_settings() -> None:
    tenant_id = uuid4()
    retrieval = create_metric_retrieval_service(
        InMemoryMetricKnowledgeRepository(),
        RetrievalSettings(result_limit=3, cache_ttl_seconds=60),
    )
    ingest_baseline(retrieval, tenant_id)

    assert len(retrieval.retrieve(tenant_id=tenant_id, query="销售额").hits) == 3


def test_hybrid_retrieval_returns_ranked_citations() -> None:
    tenant_id = uuid4()
    retrieval, _ = service()
    ingest_baseline(retrieval, tenant_id)

    result = retrieval.retrieve(
        tenant_id=tenant_id,
        query="销售额的计算公式是什么？",
        mode="hybrid",
    )

    assert result.should_answer is True
    assert result.citations[0].section_key == "retail-metrics-v1.md#销售额-revenue"
    assert result.citations[0].document_version == 1
    assert result.hits[0].content not in repr(result)
    assert result.hits[0].lexical_score is not None
    assert result.hits[0].vector_score is not None


def test_queries_are_tenant_isolated() -> None:
    tenant_a, tenant_b = uuid4(), uuid4()
    retrieval, _ = service()
    ingest_baseline(retrieval, tenant_a)

    assert retrieval.retrieve(tenant_id=tenant_a, query="销售额").hits
    assert retrieval.retrieve(tenant_id=tenant_b, query="销售额").hits == ()


def test_document_update_increments_version_and_invalidates_old_chunks_and_cache() -> None:
    tenant_id = uuid4()
    retrieval, store = service()
    first = retrieval.ingest(
        tenant_id=tenant_id,
        title="Metric policy",
        source_name="policy.md",
        source_type="MARKDOWN",
        payload="# Legacy\n\n旧指标口径只使用旧值。".encode(),
    )
    assert retrieval.retrieve(tenant_id=tenant_id, query="旧指标", mode="lexical").hits
    first_call_count = store.lexical_calls
    retrieval.retrieve(tenant_id=tenant_id, query="旧指标", mode="lexical")
    assert store.lexical_calls == first_call_count

    second = retrieval.ingest(
        tenant_id=tenant_id,
        title="Metric policy",
        source_name="policy.md",
        source_type="MARKDOWN",
        payload="# Current\n\n新口径只使用当前有效值。".encode(),
    )

    assert second.version == first.version + 1
    old = retrieval.retrieve(tenant_id=tenant_id, query="旧指标", mode="lexical")
    assert old.hits == ()
    assert store.lexical_calls == first_call_count + 1
    assert retrieval.retrieve(tenant_id=tenant_id, query="新口径", mode="lexical").should_answer


def test_cache_key_includes_mode_limit_and_corpus_revision() -> None:
    tenant_id = uuid4()
    store = InMemoryMetricKnowledgeRepository()
    retrieval = MetricRetrievalService(repository=store, cache=RetrievalCache(300))
    ingest_baseline(retrieval, tenant_id)

    retrieval.retrieve(tenant_id=tenant_id, query="订单数", mode="lexical", limit=3)
    retrieval.retrieve(tenant_id=tenant_id, query="订单数", mode="lexical", limit=3)
    retrieval.retrieve(tenant_id=tenant_id, query="订单数", mode="lexical", limit=4)

    assert store.lexical_calls == 2


def test_unrelated_question_is_marked_for_refusal() -> None:
    tenant_id = uuid4()
    retrieval, _ = service()
    ingest_baseline(retrieval, tenant_id)

    result = retrieval.retrieve(tenant_id=tenant_id, query="广告点击归因窗口", mode="hybrid")

    assert result.should_answer is False


def test_rag_gold_dataset_has_20_to_30_cases_and_all_three_baselines() -> None:
    tenant_id = UUID("00000000-0000-0000-0000-000000000006")
    retrieval, _ = service()
    ingest_baseline(retrieval, tenant_id)
    cases = load_cases(CASES)
    report = evaluate_modes(
        service=retrieval,
        tenant_id=tenant_id,
        cases=cases,
        dataset_version="northwind-rag-gold-v1",
    )

    assert 20 <= len(cases) <= 30
    assert len({case.id for case in cases}) == len(cases)
    assert {item.mode for item in report.reports} == {"lexical", "vector", "hybrid"}
    hybrid = next(item for item in report.reports if item.mode == "hybrid")
    assert hybrid.recall_at_5 >= 0.90
    assert hybrid.mrr >= 0.75
    assert hybrid.citation_hit_rate >= 0.90
    assert hybrid.refusal_accuracy >= 0.75
