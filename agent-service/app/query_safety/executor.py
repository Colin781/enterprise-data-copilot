import json
from typing import Any, Protocol, runtime_checkable

import psycopg
from psycopg.errors import InsufficientPrivilege, QueryCanceled

from app.data_sources.errors import DataSourceError
from app.data_sources.models import DataSourceConfig
from app.data_sources.service import DataSourceService
from app.query_safety.errors import (
    QueryExecutionError,
    QueryPermissionError,
    QueryResultLimitError,
    QuerySafetyError,
    QueryTimeoutError,
)
from app.query_safety.models import GuardedQuery, QueryExecutionResult, QueryPolicy


@runtime_checkable
class QueryExecutor(Protocol):
    def execute(
        self,
        query: GuardedQuery,
        config: DataSourceConfig,
        policy: QueryPolicy,
    ) -> QueryExecutionResult: ...


class PostgresReadOnlyExecutor:
    def __init__(self, data_source_service: DataSourceService | None = None) -> None:
        self._data_source_service = data_source_service or DataSourceService()

    def execute(
        self,
        query: GuardedQuery,
        config: DataSourceConfig,
        policy: QueryPolicy,
    ) -> QueryExecutionResult:
        try:
            with (
                self._data_source_service.connect(config) as connection,
                connection.transaction(),
                connection.cursor() as cursor,
            ):
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    (str(config.statement_timeout_ms),),
                )
                cursor.execute(query.bounded_sql)
                if cursor.description is None:
                    raise QueryExecutionError()

                columns = tuple(column.name for column in cursor.description)
                if len(columns) > policy.max_columns or len(set(columns)) != len(columns):
                    raise QueryResultLimitError()
                raw_rows = cursor.fetchmany(query.row_fetch_limit)
        except QuerySafetyError:
            raise
        except QueryCanceled as exc:
            raise QueryTimeoutError() from exc
        except InsufficientPrivilege as exc:
            raise QueryPermissionError() from exc
        except (DataSourceError, psycopg.Error, OSError, TimeoutError) as exc:
            raise QueryExecutionError() from exc

        return _bounded_result(columns, raw_rows, policy)


def _bounded_result(
    columns: tuple[str, ...],
    raw_rows: list[tuple[Any, ...]],
    policy: QueryPolicy,
) -> QueryExecutionResult:
    base_size = len(
        json.dumps(
            {"columns": columns, "rows": []},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    )
    if base_size > policy.max_result_bytes:
        raise QueryResultLimitError()

    rows: list[dict[str, Any]] = []
    serialized_bytes = base_size
    truncated = len(raw_rows) > policy.max_rows
    for raw_row in raw_rows[: policy.max_rows]:
        row = dict(zip(columns, raw_row, strict=True))
        encoded = json.dumps(
            row,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode()
        added_size = len(encoded) + (1 if rows else 0)
        if serialized_bytes + added_size > policy.max_result_bytes:
            truncated = True
            break
        rows.append(json.loads(encoded))
        serialized_bytes += added_size

    return QueryExecutionResult(
        columns=columns,
        rows=tuple(rows),
        returned_row_count=len(rows),
        serialized_bytes=serialized_bytes,
        truncated=truncated,
    )
