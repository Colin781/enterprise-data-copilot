"""Reproducible EXPLAIN experiment, isolated in rollback-only temporary tables."""

import argparse
import json
from pathlib import Path

import psycopg

from app.settings import get_platform_database_settings


def compare_plans(rows: int = 100_000) -> dict:
    settings = get_platform_database_settings()
    with psycopg.connect(
        host=settings.host,
        port=settings.port,
        dbname=settings.name,
        user=settings.user,
        password=settings.password.get_secret_value(),
    ) as connection:
        try:
            connection.execute("SET LOCAL statement_timeout = '30s'")
            connection.execute(
                "CREATE TEMP TABLE plan_jobs (id bigint, tenant int, owner_id int, "
                "status text, created_at timestamptz)"
            )
            connection.execute(
                "INSERT INTO plan_jobs SELECT n, n %% 20, n %% 200, "
                "CASE WHEN n %% 3 = 0 THEN 'FAILED' ELSE 'COMPLETED' END, "
                "now() - n * interval '1 second' FROM generate_series(1, %s) n",
                (rows,),
            )
            connection.execute("ANALYZE plan_jobs")
            query = (
                "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT id, "
                "count(*) OVER () AS matching_rows FROM plan_jobs "
                "WHERE tenant = 1 AND owner_id = 1 "
                "ORDER BY created_at DESC, id DESC LIMIT 20"
            )
            before = connection.execute(query).fetchone()[0][0]
            connection.execute(
                "CREATE INDEX ON plan_jobs (tenant, owner_id, created_at DESC, id DESC)"
            )
            connection.execute("ANALYZE plan_jobs")
            after = connection.execute(query).fetchone()[0][0]
            return {
                "rows": rows,
                "scope": "synthetic temporary tables; not production evidence",
                "before": before,
                "after": after,
                "execution_ms_delta": after["Execution Time"] - before["Execution Time"],
            }
        finally:
            connection.rollback()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1_000 <= args.rows <= 1_000_000:
        parser.error("rows must be between 1000 and 1000000")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(compare_plans(args.rows), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
