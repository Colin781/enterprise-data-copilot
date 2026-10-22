"""Small manually reviewable extraction dataset; gold replay is labelled explicitly."""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

from app.knowledge_graph.models import Extraction, ExtractRequest
from app.knowledge_graph.repository import MemoryGraphStore
from app.knowledge_graph.service import KnowledgeGraphService
from app.llm.factory import create_structured_llm_client


def triples(extraction):
    names = {e.id: (e.kind, e.name.casefold()) for e in extraction.entities}
    return {(names[r.source], r.kind, names[r.target]) for r in extraction.relations}


async def evaluate(path, configured=False):
    llm = create_structured_llm_client() if configured else None
    service = KnowledgeGraphService(MemoryGraphStore(), llm, None)
    records = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            case = json.loads(line)
            gold = Extraction.model_validate({key: case[key] for key in ("entities", "relations")})
            request = ExtractRequest(source_id=uuid4(), source_name=case["id"], text=case["text"])
            predicted = gold
            if configured:
                # Extract via the same service, including quote and reference validation.
                graph = await service.extract(uuid4(), request)
                predicted_triples = {
                    (
                        (
                            next(n.kind for n in graph.nodes if n.id == r.source),
                            next(n.name.casefold() for n in graph.nodes if n.id == r.source),
                        ),
                        r.kind,
                        (
                            next(n.kind for n in graph.nodes if n.id == r.target),
                            next(n.name.casefold() for n in graph.nodes if n.id == r.target),
                        ),
                    )
                    for r in graph.edges
                }
            else:
                service.persist(uuid4(), request, predicted)
                predicted_triples = triples(predicted)
            expected = triples(gold)
            correct = len(predicted_triples & expected)
            precision = correct / len(predicted_triples) if predicted_triples else 0
            recall = correct / len(expected) if expected else 0
            records.append(
                {
                    "id": case["id"],
                    "precision": precision,
                    "recall": recall,
                    "f1": 2 * precision * recall / (precision + recall)
                    if precision + recall
                    else 0,
                }
            )
    finally:
        if llm:
            await llm.aclose()
    return {
        "mode": "configured_model" if configured else "gold_replay_schema_validation",
        "real_model_evaluation": configured,
        "cases": records,
        "limitation": "3 small fixtures; expand with real documents and Chinese examples",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--configured-model", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(evaluate(args.cases, args.configured_model))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
