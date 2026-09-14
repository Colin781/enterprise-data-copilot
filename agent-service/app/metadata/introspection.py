import hashlib
import json
from collections import defaultdict
from typing import Any

from psycopg import sql
from psycopg.rows import dict_row

from app.data_sources.models import DataSourceConfig
from app.data_sources.service import DataSourceService
from app.metadata.models import (
    ColumnMetadata,
    ForeignKeyMetadata,
    PrimaryKeyMetadata,
    SchemaSnapshot,
    TableMetadata,
)

_COLUMNS_SQL = """
SELECT
    columns.table_name,
    obj_description(classes.oid, 'pg_class') AS table_comment,
    columns.column_name,
    columns.ordinal_position,
    CASE
        WHEN columns.data_type = 'USER-DEFINED' THEN columns.udt_name
        ELSE columns.data_type
    END AS data_type,
    columns.is_nullable = 'YES' AS nullable,
    col_description(classes.oid, columns.ordinal_position) AS column_comment
FROM information_schema.columns AS columns
JOIN pg_namespace AS namespaces
  ON namespaces.nspname = columns.table_schema
JOIN pg_class AS classes
  ON classes.relnamespace = namespaces.oid
 AND classes.relname = columns.table_name
 AND classes.relkind IN ('r', 'p')
WHERE columns.table_schema = %s
  AND columns.table_name <> 'dataset_manifest'
ORDER BY columns.table_name, columns.ordinal_position
"""

_PRIMARY_KEYS_SQL = """
SELECT
    tables.relname AS table_name,
    constraints.conname AS constraint_name,
    array_agg(columns.attname ORDER BY key_columns.ordinality) AS columns
FROM pg_constraint AS constraints
JOIN pg_class AS tables ON tables.oid = constraints.conrelid
JOIN pg_namespace AS schemas ON schemas.oid = tables.relnamespace
CROSS JOIN LATERAL unnest(constraints.conkey)
  WITH ORDINALITY AS key_columns(attribute_number, ordinality)
JOIN pg_attribute AS columns
  ON columns.attrelid = tables.oid
 AND columns.attnum = key_columns.attribute_number
WHERE schemas.nspname = %s
  AND constraints.contype = 'p'
  AND tables.relname <> 'dataset_manifest'
GROUP BY tables.relname, constraints.conname
ORDER BY tables.relname
"""

_FOREIGN_KEYS_SQL = """
SELECT
    source_tables.relname AS table_name,
    constraints.conname AS constraint_name,
    array_agg(source_columns.attname ORDER BY source_keys.ordinality) AS columns,
    MIN(target_schemas.nspname) AS referenced_schema,
    MIN(target_tables.relname) AS referenced_table,
    array_agg(target_columns.attname ORDER BY source_keys.ordinality) AS referenced_columns
FROM pg_constraint AS constraints
JOIN pg_class AS source_tables ON source_tables.oid = constraints.conrelid
JOIN pg_namespace AS source_schemas ON source_schemas.oid = source_tables.relnamespace
JOIN pg_class AS target_tables ON target_tables.oid = constraints.confrelid
JOIN pg_namespace AS target_schemas ON target_schemas.oid = target_tables.relnamespace
CROSS JOIN LATERAL unnest(constraints.conkey)
  WITH ORDINALITY AS source_keys(attribute_number, ordinality)
JOIN LATERAL unnest(constraints.confkey)
  WITH ORDINALITY AS target_keys(attribute_number, ordinality)
  ON target_keys.ordinality = source_keys.ordinality
JOIN pg_attribute AS source_columns
  ON source_columns.attrelid = source_tables.oid
 AND source_columns.attnum = source_keys.attribute_number
JOIN pg_attribute AS target_columns
  ON target_columns.attrelid = target_tables.oid
 AND target_columns.attnum = target_keys.attribute_number
WHERE source_schemas.nspname = %s
  AND constraints.contype = 'f'
GROUP BY source_tables.relname, constraints.conname
ORDER BY source_tables.relname, constraints.conname
"""


class PostgresSchemaIntrospector:
    def __init__(self, data_source_service: DataSourceService | None = None) -> None:
        self._data_source_service = data_source_service or DataSourceService()

    def inspect(self, config: DataSourceConfig) -> SchemaSnapshot:
        with (
            self._data_source_service.connect(config) as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            cursor.execute(_COLUMNS_SQL, (config.allowed_schema,))
            column_rows = cursor.fetchall()
            cursor.execute(_PRIMARY_KEYS_SQL, (config.allowed_schema,))
            primary_key_rows = cursor.fetchall()
            cursor.execute(_FOREIGN_KEYS_SQL, (config.allowed_schema,))
            foreign_key_rows = cursor.fetchall()
            cursor.execute(
                sql.SQL(
                    "SELECT dataset_version FROM {}.dataset_manifest WHERE dataset_name = %s"
                ).format(sql.Identifier(config.allowed_schema)),
                ("northwind",),
            )
            version_row = cursor.fetchone()

        return build_snapshot(
            source_id=config.source_id,
            schema_name=config.allowed_schema,
            dataset_version=(version_row or {}).get("dataset_version", "unknown"),
            column_rows=column_rows,
            primary_key_rows=primary_key_rows,
            foreign_key_rows=foreign_key_rows,
        )


def build_snapshot(
    *,
    source_id: str,
    schema_name: str,
    dataset_version: str,
    column_rows: list[dict[str, Any]],
    primary_key_rows: list[dict[str, Any]],
    foreign_key_rows: list[dict[str, Any]],
) -> SchemaSnapshot:
    columns_by_table: dict[str, list[ColumnMetadata]] = defaultdict(list)
    comments_by_table: dict[str, str | None] = {}
    for row in column_rows:
        table_name = row["table_name"]
        comments_by_table[table_name] = row["table_comment"]
        columns_by_table[table_name].append(
            ColumnMetadata(
                name=row["column_name"],
                ordinal_position=row["ordinal_position"],
                data_type=row["data_type"],
                nullable=row["nullable"],
                comment=row["column_comment"],
            )
        )

    primary_keys = {
        row["table_name"]: PrimaryKeyMetadata(
            name=row["constraint_name"], columns=list(row["columns"])
        )
        for row in primary_key_rows
    }
    foreign_keys: dict[str, list[ForeignKeyMetadata]] = defaultdict(list)
    for row in foreign_key_rows:
        foreign_keys[row["table_name"]].append(
            ForeignKeyMetadata(
                name=row["constraint_name"],
                columns=list(row["columns"]),
                referenced_schema=row["referenced_schema"],
                referenced_table=row["referenced_table"],
                referenced_columns=list(row["referenced_columns"]),
            )
        )

    tables = [
        TableMetadata(
            name=table_name,
            comment=comments_by_table[table_name],
            columns=columns_by_table[table_name],
            primary_key=primary_keys.get(table_name),
            foreign_keys=foreign_keys.get(table_name, []),
        )
        for table_name in sorted(columns_by_table)
    ]
    version_payload = json.dumps(
        [table.model_dump(mode="json") for table in tables],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    schema_version = f"sha256:{hashlib.sha256(version_payload).hexdigest()}"
    return SchemaSnapshot(
        source_id=source_id,
        schema_name=schema_name,
        schema_version=schema_version,
        dataset_version=dataset_version,
        tables=tables,
    )
