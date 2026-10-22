from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field, create_model

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


def catalog_selection_model(
    response_model: type[BaseModel], *, allowed_tables: frozenset[str], allowed_schema: str
) -> type[BaseModel]:
    """Constrain the wire schema as well as validating the returned table whitelist."""
    if not allowed_tables:
        raise SchemaSelectionError()
    names = tuple(sorted(allowed_tables | {f"{allowed_schema}.{name}" for name in allowed_tables}))
    return create_model(
        response_model.__name__,
        __base__=response_model,
        tables=(tuple[Literal[names], ...], Field(min_length=1, max_length=6)),
    )
