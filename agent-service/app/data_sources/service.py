from collections.abc import Callable
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.errors import InsufficientPrivilege, OperationalError

from app.data_sources.errors import DataSourcePermissionError, DataSourceUnavailableError
from app.data_sources.models import ConnectionCheck, DataSourceConfig

ConnectionFactory = Callable[..., Connection[Any]]


class DataSourceService:
    def __init__(self, connection_factory: ConnectionFactory = psycopg.connect) -> None:
        self._connection_factory = connection_factory

    def connect(self, config: DataSourceConfig) -> Connection[Any]:
        try:
            return self._connection_factory(**config.connection_parameters())
        except InsufficientPrivilege as exc:
            raise DataSourcePermissionError() from exc
        except (OperationalError, OSError, TimeoutError) as exc:
            raise DataSourceUnavailableError() from exc

    def test_connection(self, config: DataSourceConfig) -> ConnectionCheck:
        try:
            with self.connect(config) as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT current_database(), current_user,
                           current_setting('transaction_read_only') = 'on'
                    """
                )
                database, username, transaction_read_only = cursor.fetchone()
        except InsufficientPrivilege as exc:
            raise DataSourcePermissionError() from exc
        except (OperationalError, OSError, TimeoutError) as exc:
            raise DataSourceUnavailableError() from exc

        return ConnectionCheck(
            source_id=config.source_id,
            database=database,
            username=username,
            transaction_read_only=transaction_read_only,
        )
