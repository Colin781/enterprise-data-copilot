import argparse
import asyncio
from pathlib import Path
from uuid import UUID

from app.data_sources.models import DataSourceConfig
from app.evaluation.datasets import load_dangerous_cases, load_nl2sql_cases
from app.evaluation.runner import evaluate_p10
from app.llm.factory import create_structured_llm_client
from app.metadata.models import SchemaSnapshot
from app.retrieval.embeddings import HashingEmbeddingProvider
from app.retrieval.evaluation import evaluate_modes, load_cases
from app.retrieval.repository import InMemoryMetricKnowledgeRepository
from app.retrieval.service import MetricRetrievalService
from app.settings import get_business_database_settings, get_llm_settings

_EVALUATION_TENANT = UUID("00000000-0000-0000-0000-000000000010")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the complete P10 evaluation suite.")
    parser.add_argument("--nl2sql-cases", type=Path, required=True)
    parser.add_argument("--dangerous-cases", type=Path, required=True)
    parser.add_argument("--rag-cases", type=Path, required=True)
    parser.add_argument("--metric-document", type=Path, required=True)
    parser.add_argument("--schema-snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=("scripted_gold_replay", "configured_model"),
        default="scripted_gold_replay",
    )
    parser.add_argument("--allow-external-model", action="store_true")
    parser.add_argument("--input-cost-per-million", type=float)
    parser.add_argument("--output-cost-per-million", type=float)
    arguments = parser.parse_args()

    cases = load_nl2sql_cases(arguments.nl2sql_cases)
    dangerous = load_dangerous_cases(arguments.dangerous_cases)
    if len(cases) < 50:
        parser.error("P10 requires at least 50 NL2SQL cases")
    rag_cases = load_cases(arguments.rag_cases)
    if len(rag_cases) < 20:
        parser.error("P10 requires at least 20 RAG cases")
    if arguments.mode == "configured_model" and not arguments.allow_external_model:
        parser.error("configured_model requires --allow-external-model")

    retrieval = MetricRetrievalService(
        repository=InMemoryMetricKnowledgeRepository(),
        embedding_provider=HashingEmbeddingProvider(64),
    )
    retrieval.ingest(
        tenant_id=_EVALUATION_TENANT,
        title="Northwind 零售指标口径",
        source_name=arguments.metric_document.name,
        source_type="MARKDOWN",
        payload=arguments.metric_document.read_bytes(),
    )
    rag_report = evaluate_modes(
        service=retrieval,
        tenant_id=_EVALUATION_TENANT,
        cases=rag_cases,
        dataset_version="northwind-rag-gold-v1",
    )
    snapshot = SchemaSnapshot.model_validate_json(
        arguments.schema_snapshot.read_text(encoding="utf-8")
    )
    config = DataSourceConfig.from_settings(get_business_database_settings())
    llm_client = None
    provider = None
    model = None
    if arguments.mode == "configured_model":
        llm_settings = get_llm_settings()
        llm_client = create_structured_llm_client(llm_settings)
        provider = llm_settings.provider
        model = llm_settings.model

    report = asyncio.run(
        evaluate_p10(
            cases=cases,
            dangerous_cases=dangerous,
            snapshot=snapshot,
            config=config,
            rag_report=rag_report,
            dataset_version="northwind-p10-v1",
            mode=arguments.mode,
            llm_client=llm_client,
            provider=provider,
            model=model,
            input_cost_per_million=arguments.input_cost_per_million,
            output_cost_per_million=arguments.output_cost_per_million,
        )
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
