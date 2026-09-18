from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.llm.models import LLMTokenUsage
from app.query_safety.models import SafeQueryOutcome


class TableSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tables: tuple[str, ...] = Field(min_length=1, max_length=6)


class AnalysisPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: str = Field(min_length=1, max_length=500)
    steps: tuple[str, ...] = Field(min_length=1, max_length=8)
    expected_columns: tuple[
        Annotated[str, Field(pattern=r"^[a-z_][a-z0-9_]*$", max_length=63)], ...
    ] = Field(min_length=1, max_length=50)


class NL2SQLDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_plan: AnalysisPlan
    tables_used: tuple[str, ...] = Field(min_length=1, max_length=6)
    sql: str = Field(min_length=1, max_length=50_000, repr=False)


class NL2SQLResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_plan: AnalysisPlan
    selected_tables: tuple[str, ...]
    sql: str = Field(min_length=1, repr=False)
    repair_count: int = Field(ge=0, le=2)
    model_calls: int = Field(ge=2)
    provider: str
    model: str
    usage: LLMTokenUsage
    outcome: SafeQueryOutcome
