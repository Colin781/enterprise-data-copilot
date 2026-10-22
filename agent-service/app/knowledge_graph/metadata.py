"""Deterministic schema-to-graph import; only catalog metadata, never database rows."""

import json
from uuid import uuid5

from app.knowledge_graph.models import Extraction, ExtractRequest
from app.metadata.models import SchemaSnapshot


def metadata_extraction(snapshot: SchemaSnapshot, tenant_id):
    data = snapshot.model_dump(mode="json")
    text = json.dumps(data, ensure_ascii=False)
    if len(text) > 20_000:
        raise ValueError("split large schema catalogs before importing")
    source_id = uuid5(tenant_id, "schema:" + snapshot.source_id)
    entities = [
        {
            "id": "source",
            "kind": "DataSource",
            "name": snapshot.source_id,
            "evidence": snapshot.source_id,
            "confidence": 1,
        }
    ]
    relations = []
    table_ids = {table.name: "table_" + str(i) for i, table in enumerate(snapshot.tables)}
    for table in snapshot.tables:
        table_id = table_ids[table.name]
        entities.append(
            {
                "id": table_id,
                "kind": "Table",
                "name": table.name,
                "evidence": table.name,
                "confidence": 1,
            }
        )
        relations.append(
            {
                "source": table_id,
                "target": "source",
                "kind": "BELONGS_TO",
                "evidence": f'"name": "{table.name}"',
                "confidence": 1,
            }
        )
        for i, column in enumerate(table.columns):
            column_id = f"{table_id}_column_{i}"
            entities.append(
                {
                    "id": column_id,
                    "kind": "Column",
                    "name": f"{table.name}.{column.name}",
                    "evidence": f'"name": "{column.name}"',
                    "confidence": 1,
                }
            )
            relations.append(
                {
                    "source": column_id,
                    "target": table_id,
                    "kind": "BELONGS_TO",
                    "evidence": f'"name": "{column.name}"',
                    "confidence": 1,
                }
            )
        for key in table.foreign_keys:
            if key.referenced_table in table_ids:
                relations.append(
                    {
                        "source": table_id,
                        "target": table_ids[key.referenced_table],
                        "kind": "JOINS_WITH",
                        "confidence": 1,
                        "evidence": json.dumps(key.model_dump(mode="json"), ensure_ascii=False),
                    }
                )
    return ExtractRequest(
        source_id=source_id, source_name=f"{snapshot.source_id}-metadata.json", text=text
    ), Extraction(entities=entities, relations=relations)
