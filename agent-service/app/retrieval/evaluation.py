import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.retrieval.models import RetrievalMode
from app.retrieval.service import MetricRetrievalService


class RAGGoldCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=1, max_length=4_000)
    relevant_sections: tuple[str, ...]
    answerable: bool


class RetrievalModeReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: RetrievalMode
    total_cases: int
    answerable_cases: int
    refusal_cases: int
    recall_at_5: float
    mrr: float
    citation_hit_rate: float
    refusal_accuracy: float


class RAGEvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_version: str
    cases: int
    reports: tuple[RetrievalModeReport, ...]


def load_cases(path: Path) -> tuple[RAGGoldCase, ...]:
    return tuple(
        RAGGoldCase.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def evaluate_modes(
    *,
    service: MetricRetrievalService,
    tenant_id: UUID,
    cases: Sequence[RAGGoldCase],
    dataset_version: str,
    modes: Iterable[RetrievalMode] = ("lexical", "vector", "hybrid"),
) -> RAGEvaluationReport:
    reports = tuple(_evaluate_mode(service, tenant_id, cases, mode) for mode in modes)
    return RAGEvaluationReport(
        dataset_version=dataset_version,
        cases=len(cases),
        reports=reports,
    )


def _evaluate_mode(
    service: MetricRetrievalService,
    tenant_id: UUID,
    cases: Sequence[RAGGoldCase],
    mode: RetrievalMode,
) -> RetrievalModeReport:
    answerable = [case for case in cases if case.answerable]
    refusal = [case for case in cases if not case.answerable]
    recalled = 0
    reciprocal_rank = 0.0
    citation_hits = 0
    correct_refusals = 0
    for case in cases:
        result = service.retrieve(tenant_id=tenant_id, query=case.question, mode=mode, limit=5)
        returned = [citation.section_key for citation in result.citations]
        relevant = set(case.relevant_sections)
        if case.answerable:
            first_rank = next(
                (rank for rank, section in enumerate(returned, start=1) if section in relevant),
                None,
            )
            if first_rank is not None:
                recalled += 1
                citation_hits += 1
                reciprocal_rank += 1 / first_rank
        elif not result.should_answer:
            correct_refusals += 1
    answerable_count = len(answerable)
    refusal_count = len(refusal)
    return RetrievalModeReport(
        mode=mode,
        total_cases=len(cases),
        answerable_cases=answerable_count,
        refusal_cases=refusal_count,
        recall_at_5=_ratio(recalled, answerable_count),
        mrr=_ratio(reciprocal_rank, answerable_count),
        citation_hit_rate=_ratio(citation_hits, answerable_count),
        refusal_accuracy=_ratio(correct_refusals, refusal_count),
    )


def report_json(report: RAGEvaluationReport) -> str:
    return json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)


def _ratio(numerator: float, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 1.0
