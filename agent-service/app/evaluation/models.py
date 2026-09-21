from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.retrieval.evaluation import RAGEvaluationReport

FailureCategory = Literal[
    "dataset",
    "model",
    "schema_selection",
    "safety",
    "execution",
    "result_mismatch",
    "unknown",
]
EvaluationMode = Literal["scripted_gold_replay", "configured_model"]
CaseKind = Literal["nl2sql", "dangerous"]


class NL2SQLGoldCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^nw[0-9]{3}$")
    question: str = Field(min_length=1, max_length=4_000)
    gold_sql: str = Field(min_length=1, max_length=50_000, repr=False)
    expected_columns: tuple[str, ...] = Field(min_length=1, max_length=50)
    tags: tuple[str, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_case(self) -> "NL2SQLGoldCase":
        if not self.gold_sql.lstrip().upper().startswith(("SELECT", "WITH")):
            raise ValueError("gold_sql must be a read-only SELECT or WITH statement")
        if len(self.expected_columns) != len(set(self.expected_columns)):
            raise ValueError("expected_columns must be unique")
        if len(self.tags) != len(set(self.tags)):
            raise ValueError("tags must be unique")
        return self


class DangerousQuestionCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^dq[0-9]{3}$")
    question: str = Field(min_length=1, max_length=4_000)
    expected_reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    tags: tuple[str, ...] = Field(min_length=1, max_length=20)


class EvaluationCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    kind: CaseKind
    passed: bool
    execution_correct: bool | None = None
    safe_query_passed: bool | None = None
    blocked: bool | None = None
    first_pass: bool | None = None
    repair_count: int | None = Field(default=None, ge=0, le=2)
    latency_ms: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    failure_category: FailureCategory | None = None
    failure_code: str | None = None


class EvaluationMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    nl2sql_cases: int = Field(ge=0)
    dangerous_cases: int = Field(ge=0)
    execution_accuracy: float = Field(ge=0, le=1)
    safe_query_pass_rate: float = Field(ge=0, le=1)
    dangerous_query_block_rate: float = Field(ge=0, le=1)
    end_to_end_success_rate: float = Field(ge=0, le=1)
    first_generation_success_rate: float = Field(ge=0, le=1)
    repaired_success_rate: float | None = Field(default=None, ge=0, le=1)
    mean_latency_ms: float = Field(ge=0)
    p95_latency_ms: int = Field(ge=0)
    average_total_tokens: float | None = Field(default=None, ge=0)
    average_estimated_cost_usd: float | None = Field(default=None, ge=0)
    failures_by_category: dict[str, int]
    failures_by_code: dict[str, int]


class P10EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    report_version: Literal["1.0"] = "1.0"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    dataset_version: str
    evaluation_mode: EvaluationMode
    real_model_evaluation: bool
    provider: str
    model: str
    metrics: EvaluationMetrics
    rag: RAGEvaluationReport
    cases: tuple[EvaluationCaseResult, ...]
    limitations: tuple[str, ...]
