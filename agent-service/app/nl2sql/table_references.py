from collections.abc import Sequence

from app.nl2sql.errors import SchemaSelectionError


def normalize_reported_tables(tables: Sequence[str], *, allowed_schema: str) -> tuple[str, ...]:
    """Normalize model-reported table metadata without weakening schema isolation."""
    normalized: list[str] = []
    for value in tables:
        parts = value.split(".")
        if len(parts) == 1 and parts[0]:
            table = parts[0]
        elif len(parts) == 2 and parts[0] == allowed_schema and parts[1]:
            table = parts[1]
        else:
            raise SchemaSelectionError()
        normalized.append(table)

    if len(set(normalized)) != len(normalized):
        raise SchemaSelectionError()
    return tuple(normalized)
