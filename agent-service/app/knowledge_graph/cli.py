import argparse
from pathlib import Path
from uuid import UUID

from app.knowledge_graph.metadata import metadata_extraction
from app.knowledge_graph.repository import Neo4jGraphStore
from app.knowledge_graph.service import KnowledgeGraphService
from app.metadata.models import SchemaSnapshot
from app.settings import GraphSettings


def main():
    parser = argparse.ArgumentParser(description="Operator-only catalog graph import; no LLM calls")
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--tenant-id", type=UUID, required=True)
    args = parser.parse_args()
    snapshot = SchemaSnapshot.model_validate_json(args.metadata.read_text(encoding="utf-8"))
    request, extraction = metadata_extraction(snapshot, args.tenant_id)
    settings = GraphSettings()
    store = Neo4jGraphStore(
        settings.uri, settings.user, settings.password.get_secret_value(), settings.database
    )
    try:
        store.setup()
        graph = KnowledgeGraphService(store, None, None).persist(
            args.tenant_id, request, extraction
        )
        print(
            f"Imported {len(graph.nodes)} nodes and {len(graph.edges)} edges; "
            f"source={request.source_id}"
        )
    finally:
        store.close()


if __name__ == "__main__":
    main()
