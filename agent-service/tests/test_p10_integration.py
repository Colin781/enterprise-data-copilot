import asyncio
import os
from pathlib import Path
from uuid import UUID

import pytest

from app.data_sources.models import DataSourceConfig
from app.evaluation.datasets import load_dangerous_cases, load_nl2sql_cases
from app.evaluation.runner import evaluate_p10
from app.metadata.models import SchemaSnapshot
from app.retrieval.embeddings import HashingEmbeddingProvider
from app.retrieval.evaluation import evaluate_modes, load_cases
from app.retrieval.repository import InMemoryMetricKnowledgeRepository
from app.retrieval.service import MetricRetrievalService
from app.settings import get_business_database_settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_P10_INTEGRATION") != "1",
        reason="set RUN_P10_INTEGRATION=1 to run the complete P10 baseline",
    ),
]

ROOT = Path(__file__).parents[2]


def test_complete_scripted_baseline_executes_55_queries_and_blocks_20_dangerous_prompts() -> None:
    tenant_id = UUID("00000000-0000-0000-0000-000000000010")
    retrieval = MetricRetrievalService(
        repository=InMemoryMetricKnowledgeRepository(),
        embedding_provider=HashingEmbeddingProvider(64),
    )
    document = ROOT / "knowledge/northwind/retail-metrics-v1.md"
    retrieval.ingest(
        tenant_id=tenant_id,
        title="Northwind 零售指标口径",
        source_name=document.name,
        source_type="MARKDOWN",
        payload=document.read_bytes(),
    )
    rag_report = evaluate_modes(
        service=retrieval,
        tenant_id=tenant_id,
        cases=load_cases(ROOT / "evaluation/northwind/rag-gold-v1.jsonl"),
        dataset_version="northwind-rag-gold-v1",
    )
    report = asyncio.run(
        evaluate_p10(
            cases=load_nl2sql_cases(ROOT / "evaluation/northwind/nl2sql-gold-v2.jsonl"),
            dangerous_cases=load_dangerous_cases(
                ROOT / "evaluation/northwind/dangerous-questions-v1.jsonl"
            ),
            snapshot=SchemaSnapshot.model_validate_json(
                (ROOT / "metadata/northwind-schema-v1.json").read_text(encoding="utf-8")
            ),
            config=DataSourceConfig.from_settings(get_business_database_settings()),
            rag_report=rag_report,
            dataset_version="northwind-p10-v1",
            mode="scripted_gold_replay",
        )
    )

    assert report.real_model_evaluation is False
    assert report.metrics.nl2sql_cases == 55
    assert report.metrics.dangerous_cases == 20
    assert report.metrics.execution_accuracy == 1.0
    assert report.metrics.safe_query_pass_rate == 1.0
    assert report.metrics.dangerous_query_block_rate == 1.0
    assert report.metrics.end_to_end_success_rate == 1.0
    assert report.metrics.first_generation_success_rate == 1.0
    assert report.metrics.repaired_success_rate is None
    assert report.metrics.average_total_tokens is None
    assert report.metrics.average_estimated_cost_usd is None
    assert report.metrics.failures_by_category == {}
    assert len(report.cases) == 75
    assert report.rag.cases == 24
    assert {item.mode for item in report.rag.reports} == {"lexical", "vector", "hybrid"}
    assert "gold SQL" in report.limitations[0]
    assert "gold_sql" not in report.model_dump_json()
