from pydantic import BaseModel, ConfigDict, Field


class ColumnMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    ordinal_position: int
    data_type: str
    nullable: bool
    comment: str | None = None


class PrimaryKeyMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    columns: list[str]


class ForeignKeyMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    columns: list[str]
    referenced_schema: str
    referenced_table: str
    referenced_columns: list[str]


class TableMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    comment: str | None = None
    columns: list[ColumnMetadata]
    primary_key: PrimaryKeyMetadata | None = None
    foreign_keys: list[ForeignKeyMetadata] = Field(default_factory=list)


class SchemaSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    format_version: str = "1.0"
    source_id: str
    schema_name: str
    schema_version: str
    dataset_version: str
    tables: list[TableMetadata]
