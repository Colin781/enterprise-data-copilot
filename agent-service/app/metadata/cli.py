import argparse
import json
from pathlib import Path

from app.data_sources.models import DataSourceConfig
from app.metadata.introspection import PostgresSchemaIntrospector
from app.settings import get_business_database_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the allowed business schema summary")
    parser.add_argument("--check", type=Path, help="fail if this snapshot differs")
    args = parser.parse_args()

    config = DataSourceConfig.from_settings(get_business_database_settings())
    snapshot = PostgresSchemaIntrospector().inspect(config)
    rendered = json.dumps(snapshot.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"

    if args.check:
        expected = json.loads(args.check.read_text(encoding="utf-8"))
        if expected != snapshot.model_dump(mode="json"):
            raise SystemExit(f"schema snapshot is stale: {args.check}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
