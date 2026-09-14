from typing import Any

import pytest
from psycopg import OperationalError
from pydantic import SecretStr

from app.data_sources.errors import DataSourceUnavailableError
from app.data_sources.models import DataSourceConfig
from app.data_sources.service import DataSourceService


def make_config(**overrides: Any) -> DataSourceConfig:
    values = {
        "source_id": "northwind-demo",
        "host": "database.internal",
        "port": 5432,
        "database": "northwind",
        "username": "northwind_reader",
        "password": SecretStr("do-not-leak"),
        "allowed_schema": "northwind",
    }
    values.update(overrides)
    return DataSourceConfig(**values)


def test_connection_parameters_apply_bounded_timeouts() -> None:
    parameters = make_config().connection_parameters()

    assert parameters["connect_timeout"] == 3
    assert parameters["options"] == "-c statement_timeout=2000"


def test_config_repr_redacts_password() -> None:
    rendered = repr(make_config())

    assert "do-not-leak" not in rendered
    assert "**********" in rendered


def test_schema_name_rejects_sql_fragments() -> None:
    with pytest.raises(ValueError, match="simple PostgreSQL identifier"):
        make_config(allowed_schema="northwind; DROP SCHEMA northwind")


def test_unavailable_database_returns_stable_error_without_connection_details() -> None:
    def unavailable_factory(**_: object) -> object:
        raise OperationalError("could not connect to database.internal with do-not-leak")

    service = DataSourceService(connection_factory=unavailable_factory)  # type: ignore[arg-type]

    with pytest.raises(DataSourceUnavailableError) as captured:
        service.connect(make_config())

    assert captured.value.code == "DATA_SOURCE_UNAVAILABLE"
    assert str(captured.value) == "The configured business data source is unavailable."
    assert "database.internal" not in str(captured.value)
    assert "do-not-leak" not in str(captured.value)
