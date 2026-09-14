from app.metadata.cache import SchemaMetadataCache
from app.metadata.introspection import build_snapshot


def sample_snapshot():
    return build_snapshot(
        source_id="northwind-demo",
        schema_name="northwind",
        dataset_version="northwind-compact-v1",
        column_rows=[
            {
                "table_name": "customers",
                "table_comment": "Customer companies.",
                "column_name": "customer_id",
                "ordinal_position": 1,
                "data_type": "character varying",
                "nullable": False,
                "column_comment": "Stable customer code.",
            },
            {
                "table_name": "orders",
                "table_comment": "Order headers.",
                "column_name": "order_id",
                "ordinal_position": 1,
                "data_type": "integer",
                "nullable": False,
                "column_comment": None,
            },
            {
                "table_name": "orders",
                "table_comment": "Order headers.",
                "column_name": "customer_id",
                "ordinal_position": 2,
                "data_type": "character varying",
                "nullable": False,
                "column_comment": None,
            },
        ],
        primary_key_rows=[
            {
                "table_name": "customers",
                "constraint_name": "customers_pkey",
                "columns": ["customer_id"],
            },
            {
                "table_name": "orders",
                "constraint_name": "orders_pkey",
                "columns": ["order_id"],
            },
        ],
        foreign_key_rows=[
            {
                "table_name": "orders",
                "constraint_name": "orders_customer_id_fkey",
                "columns": ["customer_id"],
                "referenced_schema": "northwind",
                "referenced_table": "customers",
                "referenced_columns": ["customer_id"],
            }
        ],
    )


def test_snapshot_contains_only_schema_summary_and_relationships() -> None:
    snapshot = sample_snapshot()

    assert [table.name for table in snapshot.tables] == ["customers", "orders"]
    assert snapshot.tables[0].primary_key.columns == ["customer_id"]
    assert snapshot.tables[1].foreign_keys[0].referenced_table == "customers"
    assert snapshot.tables[0].columns[0].comment == "Stable customer code."
    assert snapshot.schema_version.startswith("sha256:")
    assert "sample_rows" not in snapshot.model_dump_json()


def test_schema_version_is_deterministic() -> None:
    assert sample_snapshot().schema_version == sample_snapshot().schema_version


def test_cache_reuses_snapshot_until_ttl_then_refreshes() -> None:
    now = [10.0]
    cache = SchemaMetadataCache(ttl_seconds=5, clock=lambda: now[0])
    calls = 0

    def load():
        nonlocal calls
        calls += 1
        return sample_snapshot()

    first = cache.get_or_load("source", "northwind", load)
    now[0] = 14.9
    second = cache.get_or_load("source", "northwind", load)
    now[0] = 15.0
    third = cache.get_or_load("source", "northwind", load)

    assert first is second
    assert third is not second
    assert calls == 2


def test_cache_can_be_invalidated_before_ttl() -> None:
    cache = SchemaMetadataCache(ttl_seconds=60)
    calls = 0

    def load():
        nonlocal calls
        calls += 1
        return sample_snapshot()

    cache.get_or_load("source", "northwind", load)
    cache.invalidate("source", "northwind")
    cache.get_or_load("source", "northwind", load)

    assert calls == 2
