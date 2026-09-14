from pydantic import BaseModel, ConfigDict, Field

from app.query_safety.models import QueryExecutionResult


class ExecutionCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    correct: bool


class ExecutionAccuracyReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    total_cases: int = Field(ge=1)
    correct_cases: int = Field(ge=0)
    accuracy: float = Field(ge=0, le=1)
    cases: tuple[ExecutionCaseResult, ...]

    @classmethod
    def from_results(cls, cases: list[ExecutionCaseResult]) -> "ExecutionAccuracyReport":
        if not cases:
            raise ValueError("at least one evaluation case is required")
        correct = sum(case.correct for case in cases)
        return cls(
            total_cases=len(cases),
            correct_cases=correct,
            accuracy=correct / len(cases),
            cases=tuple(cases),
        )


def execution_results_match(
    candidate: QueryExecutionResult,
    expected: QueryExecutionResult,
) -> bool:
    return candidate.columns == expected.columns and candidate.rows == expected.rows
