from typing import Any, Protocol, runtime_checkable

import psycopg

from app.data_sources.errors import DataSourceError
from app.data_sources.models import DataSourceConfig
from app.data_sources.service import DataSourceService
from app.query_safety.errors import QueryExecutionError, QueryPermissionError, QueryTimeoutError
from app.query_safety.models import GuardedQuery, QueryCostEstimate


@runtime_checkable
class QueryCostEstimator(Protocol):
    def estimate(self, query: GuardedQuery, config: DataSourceConfig) -> QueryCostEstimate: ...


class PostgresQueryCostEstimator:
    def __init__(self, data_source_service: DataSourceService | None = None) -> None:
        self._data_source_service = data_source_service or DataSourceService()

    def estimate(self, query: GuardedQuery, config: DataSourceConfig) -> QueryCostEstimate:
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
                cursor.execute(f"EXPLAIN (FORMAT JSON) {query.normalized_sql}")
                row = cursor.fetchone()
        except psycopg.errors.QueryCanceled as exc:
            raise QueryTimeoutError() from exc
        except psycopg.errors.InsufficientPrivilege as exc:
            raise QueryPermissionError() from exc
        except (DataSourceError, psycopg.Error, OSError, TimeoutError) as exc:
            raise QueryExecutionError() from exc

        try:
            payload: Any = row[0] if row else None
            if isinstance(payload, str):
                import json

                payload = json.loads(payload)
            plan = payload[0]["Plan"]
            return QueryCostEstimate(
                total_cost=float(plan["Total Cost"]),
                plan_rows=int(plan["Plan Rows"]),
            )
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise QueryExecutionError() from exc
