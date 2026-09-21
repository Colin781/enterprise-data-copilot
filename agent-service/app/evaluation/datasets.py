from pathlib import Path

from pydantic import BaseModel

from app.evaluation.models import DangerousQuestionCase, NL2SQLGoldCase


def load_nl2sql_cases(path: Path) -> tuple[NL2SQLGoldCase, ...]:
    cases = _load_jsonl(path, NL2SQLGoldCase)
    _require_unique_ids(cases, path)
    return cases


def load_dangerous_cases(path: Path) -> tuple[DangerousQuestionCase, ...]:
    cases = _load_jsonl(path, DangerousQuestionCase)
    _require_unique_ids(cases, path)
    return cases


def _load_jsonl[CaseT: BaseModel](path: Path, model: type[CaseT]) -> tuple[CaseT, ...]:
    if not path.is_file():
        raise ValueError(f"evaluation dataset does not exist: {path}")
    cases: list[CaseT] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            cases.append(model.model_validate_json(line))
        except ValueError as error:
            raise ValueError(f"invalid evaluation case at {path}:{line_number}") from error
    if not cases:
        raise ValueError(f"evaluation dataset is empty: {path}")
    return tuple(cases)


def _require_unique_ids(
    cases: tuple[NL2SQLGoldCase, ...] | tuple[DangerousQuestionCase, ...], path: Path
) -> None:
    identifiers = [case.id for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"evaluation case ids must be unique: {path}")
