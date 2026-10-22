"""Four-way retrieval evaluation. No fabricated answer accuracy or model costs."""

import argparse
import json
import math
from pathlib import Path
from statistics import mean
from time import perf_counter
from uuid import UUID

from app.retrieval.evaluation import load_cases
from app.retrieval.factory import (
    create_metric_retrieval_service,
    create_production_retrieval_service,
)
from app.retrieval.repository import InMemoryMetricKnowledgeRepository
from app.settings import RetrievalSettings

MODES = ("lexical", "vector", "hybrid", "hybrid_rerank")


def benchmark(
    service,
    tenant_id,
    cases,
    modes=MODES,
    embedding_price_per_million=None,
    reranker_price_per_thousand=None,
) -> dict:
    reports = []
    for mode in modes:
        usage_before = service.usage_snapshot()
        latencies, recalls, ranks, failures = [], [], [], []
        refusal_correct = 0
        for case in cases:
            started = perf_counter()
            result = service.retrieve(tenant_id=tenant_id, query=case.question, mode=mode, limit=5)
            latencies.append((perf_counter() - started) * 1000)
            returned = list(dict.fromkeys(c.section_key for c in result.citations))
            relevant = set(case.relevant_sections)
            if case.answerable:
                recalls.append(len(relevant & set(returned)) / len(relevant) if relevant else 0)
                rank = next((i for i, key in enumerate(returned, 1) if key in relevant), None)
                ranks.append(0 if rank is None else 1 / rank)
                if rank is None or not result.should_answer:
                    failures.append(
                        {
                            "id": case.id,
                            "returned": returned,
                            "reason": "miss" if rank is None else "false_refusal",
                        }
                    )
            elif not result.should_answer:
                refusal_correct += 1
            else:
                failures.append({"id": case.id, "reason": "unsupported_question_answered"})
        refusal_count = sum(not c.answerable for c in cases)
        usage_after = service.usage_snapshot()
        before_tokens = usage_before["embedding_input_tokens"]
        after_tokens = usage_after["embedding_input_tokens"]
        input_tokens = (
            after_tokens - before_tokens
            if after_tokens is not None and before_tokens is not None
            else None
        )
        reranker_requests = usage_after["reranker_requests"] - usage_before["reranker_requests"]
        cost = None
        if (
            input_tokens is not None
            and embedding_price_per_million is not None
            and (reranker_requests == 0 or reranker_price_per_thousand is not None)
        ):
            cost = input_tokens * embedding_price_per_million / 1_000_000
            cost += reranker_requests * (reranker_price_per_thousand or 0) / 1000
        reports.append(
            {
                "mode": mode,
                "embedding_input_tokens": input_tokens,
                "embedding_requests": usage_after["embedding_requests"]
                - usage_before["embedding_requests"],
                "reranker_requests": reranker_requests,
                "estimated_cost_usd": cost,
                "cases": len(cases),
                "recall_at_5": mean(recalls) if recalls else 0,
                "mrr": mean(ranks) if ranks else 0,
                "refusal_accuracy": refusal_correct / refusal_count if refusal_count else None,
                "mean_latency_ms": mean(latencies) if latencies else 0,
                "p95_latency_ms": sorted(latencies)[max(0, math.ceil(len(latencies) * 0.95) - 1)]
                if latencies
                else 0,
                "failures": failures,
            }
        )
    return {
        "reports": reports,
        "answer_accuracy": None,
        "answer_accuracy_note": "retrieval-only run; requires separate human/LLM answer grading",
        "cost_usd": None,
        "cost_note": "per-mode estimates require observed usage and explicit provider pricing",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--document", type=Path)
    parser.add_argument(
        "--tenant-id", type=UUID, default=UUID("00000000-0000-0000-0000-000000000001")
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--embedding-price-per-million", type=float)
    parser.add_argument("--reranker-price-per-thousand", type=float)
    parser.add_argument(
        "--configured",
        action="store_true",
        help="Use configured PostgreSQL, embedding and reranker providers",
    )
    args = parser.parse_args()
    if args.configured:
        service = create_production_retrieval_service()
        profile = RetrievalSettings().model_dump(exclude={"embedding_api_key", "reranker_api_key"})
        profile = {key: str(value) for key, value in profile.items() if "url" not in key}
    else:
        if not args.document:
            parser.error("offline mode requires --document")
        service = create_metric_retrieval_service(
            InMemoryMetricKnowledgeRepository(),
            RetrievalSettings(
                embedding_provider="hashing", embedding_dimensions=64, reranker_provider="overlap"
            ),
        )
        service.ingest(
            tenant_id=args.tenant_id,
            title="Northwind",
            source_name=args.document.name,
            source_type="MARKDOWN",
            payload=args.document.read_bytes(),
        )
        profile = {
            "embedding": "hashing:64",
            "reranker": "overlap-test-baseline",
            "repository": "in-memory; not PostgreSQL performance evidence",
        }
    report = {
        "profile": profile,
        **benchmark(
            service,
            args.tenant_id,
            load_cases(args.cases),
            embedding_price_per_million=args.embedding_price_per_million,
            reranker_price_per_thousand=args.reranker_price_per_thousand,
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
