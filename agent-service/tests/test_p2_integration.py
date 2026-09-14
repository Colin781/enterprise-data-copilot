import json
import os
from pathlib import Path

import psycopg
import pytest
from psycopg.errors import InsufficientPrivilege, QueryCanceled

from app.data_sources.models import DataSourceConfig
from app.data_sources.service import DataSourceService
from app.metadata.introspection import PostgresSchemaIntrospector
from app.settings import get_business_database_settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_P2_INTEGRATION") != "1",
        reason="set RUN_P2_INTEGRATION=1 to test the local business database",
    ),
]


@pytest.fixture
def config() -> DataSourceConfig:
    return DataSourceConfig.from_settings(get_business_database_settings())


def test_fixed_dataset_version_and_row_counts(config: DataSourceConfig) -> None:
    with DataSourceService().connect(config) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT dataset_version FROM northwind.dataset_manifest")
        assert cursor.fetchone()[0] == "northwind-compact-v1"
        cursor.execute("SELECT COUNT(*) FROM northwind.orders")
        assert cursor.fetchone()[0] == 20
        cursor.execute("SELECT COUNT(*) FROM northwind.order_details")
        assert cursor.fetchone()[0] == 40


def test_reader_can_select_but_cannot_write_or_cross_schema(config: DataSourceConfig) -> None:
    service = DataSourceService()
    check = service.test_connection(config)
    assert check.transaction_read_only is True

    with service.connect(config) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM northwind.customers")
        assert cursor.fetchone()[0] == 10

        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            cursor.execute("CREATE TABLE northwind.p2_python_probe(id integer)")
        connection.rollback()

        with pytest.raises(InsufficientPrivilege):
            cursor.execute("SELECT * FROM restricted.private_notes")
        connection.rollback()


def test_reader_statement_timeout_is_enforced(config: DataSourceConfig) -> None:
    with (
        DataSourceService().connect(config) as connection,
        connection.cursor() as cursor,
        pytest.raises(QueryCanceled),
    ):
        cursor.execute("SELECT pg_sleep(3)")


def test_live_schema_matches_committed_metadata_snapshot(config: DataSourceConfig) -> None:
    actual = PostgresSchemaIntrospector().inspect(config).model_dump(mode="json")
    snapshot_path = Path(__file__).parents[2] / "metadata/northwind-schema-v1.json"
    expected = json.loads(snapshot_path.read_text(encoding="utf-8"))

    assert actual == expected
    assert all(table["name"] != "private_notes" for table in actual["tables"])


def test_every_gold_query_executes_with_expected_columns(config: DataSourceConfig) -> None:
    gold_path = Path(__file__).parents[2] / "evaluation/northwind/gold-v1.jsonl"
    cases = [json.loads(line) for line in gold_path.read_text().splitlines() if line.strip()]

    with DataSourceService().connect(config) as connection, connection.cursor() as cursor:
        for case in cases:
            cursor.execute(case["gold_sql"])
            actual_columns = [column.name for column in cursor.description]
            assert actual_columns == case["expected_columns"], case["id"]
            assert cursor.fetchone() is not None, case["id"]
