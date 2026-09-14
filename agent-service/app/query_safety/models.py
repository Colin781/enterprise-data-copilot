from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.metadata.models import SchemaSnapshot


class QueryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed_schema: str = Field(pattern=r"^[a-z_][a-z0-9_]*$")
    allowed_tables: frozenset[str] = Field(min_length=1)
    allowed_columns: dict[str, frozenset[str]] = Field(default_factory=dict)
    max_rows: int = Field(default=100, ge=1, le=10_000)
    max_columns: int = Field(default=50, ge=1, le=500)
    max_result_bytes: int = Field(default=1_000_000, ge=64, le=10_000_000)
    max_total_cost: float = Field(default=10_000, gt=0)
    max_plan_rows: int = Field(default=100_000, ge=1)

    @field_validator("allowed_tables")
    @classmethod
    def validate_table_names(cls, tables: frozenset[str]) -> frozenset[str]:
        if any(not table or not table.replace("_", "a").isalnum() for table in tables):
            raise ValueError("allowed table names must be simple identifiers")
        return tables

    @field_validator("allowed_columns")
    @classmethod
    def validate_column_names(
        cls, columns_by_table: dict[str, frozenset[str]]
    ) -> dict[str, frozenset[str]]:
        for table, columns in columns_by_table.items():
            names = (table, *columns)
            if any(not name or not name.replace("_", "a").isalnum() for name in names):
                raise ValueError("allowed column names must be simple identifiers")
        return columns_by_table

    @classmethod
    def from_snapshot(
        cls,
        snapshot: SchemaSnapshot,
        **limits: int,
    ) -> "QueryPolicy":
        return cls(
            allowed_schema=snapshot.schema_name,
            allowed_tables=frozenset(table.name for table in snapshot.tables),
            allowed_columns={
                table.name: frozenset(column.name for column in table.columns)
                for table in snapshot.tables
            },
            **limits,
        )

    def restrict_to_tables(self, table_names: frozenset[str]) -> "QueryPolicy":
        if not table_names or not table_names.issubset(self.allowed_tables):
            raise ValueError("selected tables must be a non-empty subset of the policy")
        return self.model_copy(
            update={
                "allowed_tables": table_names,
                "allowed_columns": {
                    table: self.allowed_columns[table]
                    for table in sorted(table_names)
                    if table in self.allowed_columns
                },
            }
        )


class GuardedQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    normalized_sql: str = Field(min_length=1, repr=False)
    bounded_sql: str = Field(min_length=1, repr=False)
    query_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    referenced_tables: tuple[str, ...]
    row_fetch_limit: int = Field(ge=2)


class QueryExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...] = Field(repr=False)
    returned_row_count: int = Field(ge=0)
    serialized_bytes: int = Field(ge=0)
    truncated: bool


class QueryCostEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    total_cost: float = Field(ge=0)
    plan_rows: int = Field(ge=0)


class QueryContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: UUID
    user_id: UUID
    job_id: UUID
    data_source_id: UUID
    trace_id: str = Field(pattern=r"^[A-Za-z0-9_-]{16,64}$")


QueryAuditStatus = Literal["SUCCEEDED", "REJECTED", "APPROVAL_REQUIRED", "FAILED"]


class QueryAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_version: Literal[1] = 1
    event_id: UUID
    occurred_at: datetime
    tenant_id: UUID
    user_id: UUID
    job_id: UUID
    data_source_id: UUID
    trace_id: str
    status: QueryAuditStatus
    reason_code: str = Field(min_length=1, max_length=80)
    query_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    referenced_tables: tuple[str, ...] = ()
    planner_invoked: bool = False
    executor_invoked: bool
    estimated_total_cost: float | None = Field(default=None, ge=0)
    estimated_plan_rows: int | None = Field(default=None, ge=0)
    returned_rows: int = Field(default=0, ge=0)
    returned_columns: int = Field(default=0, ge=0)
    serialized_bytes: int = Field(default=0, ge=0)
    result_truncated: bool = False
    duration_ms: int = Field(ge=0)


class SafeQueryOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result: QueryExecutionResult
    audit: QueryAuditEvent
