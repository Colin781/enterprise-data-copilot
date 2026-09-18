import argparse
from pathlib import Path
from uuid import UUID

from app.retrieval.embeddings import HashingEmbeddingProvider
from app.retrieval.evaluation import evaluate_modes, load_cases, report_json
from app.retrieval.repository import InMemoryMetricKnowledgeRepository
from app.retrieval.service import MetricRetrievalService

_EVALUATION_TENANT = UUID("00000000-0000-0000-0000-000000000006")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deterministic P6 RAG baseline.")
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--dataset-version", default="northwind-rag-gold-v1")
    arguments = parser.parse_args()

    service = MetricRetrievalService(
        repository=InMemoryMetricKnowledgeRepository(),
        embedding_provider=HashingEmbeddingProvider(dimensions=64),
    )
    service.ingest(
        tenant_id=_EVALUATION_TENANT,
        title="Northwind 零售指标口径",
        source_name=arguments.document.name,
        source_type="MARKDOWN",
        payload=arguments.document.read_bytes(),
    )
    report = evaluate_modes(
        service=service,
        tenant_id=_EVALUATION_TENANT,
        cases=load_cases(arguments.cases),
        dataset_version=arguments.dataset_version,
    )
    print(report_json(report))


if __name__ == "__main__":
    main()
