import os
from uuid import uuid4

import pytest

from app.knowledge_graph.repository import Neo4jGraphStore
from app.knowledge_graph.service import KnowledgeGraphService
from tests.test_knowledge_graph import sample

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("GRAPH_INTEGRATION_URI"),
        reason="set GRAPH_INTEGRATION_URI for isolated Neo4j",
    ),
]


def test_actual_neo4j_replace_search_path_and_tenant_isolation():
    store = Neo4jGraphStore(
        os.environ["GRAPH_INTEGRATION_URI"],
        "neo4j",
        os.environ.get("GRAPH_INTEGRATION_PASSWORD", "upgrade-test-password"),
    )
    tenant, other = uuid4(), uuid4()
    try:
        store.setup()
        request, extraction = sample()
        service = KnowledgeGraphService(store, None, None)
        graph = service.persist(tenant, request, extraction)
        assert len(store.subgraph(tenant, "Revenue", 1, 60).nodes) == 2
        assert len(store.path(tenant, graph.nodes[0].id, graph.nodes[1].id, 3).edges) == 1
        assert not store.subgraph(other, "Revenue", 3, 60).nodes
        assert not store.path(other, graph.nodes[0].id, graph.nodes[1].id, 3).nodes
        service.persist(tenant, request, extraction)
        assert len(store.subgraph(tenant, "", 0, 60).nodes) == 2
        assert len(store.subgraph(tenant, "", 1, 1).nodes) == 1
        assert store.subgraph(tenant, "", 0, 1).truncated
    finally:
        # Delete only this test's randomly generated tenant, never shared graph data.
        with store.driver.session(database=store.database) as session:
            session.run(
                "MATCH (n {tenant_id:$tenant}) DETACH DELETE n", tenant=str(tenant)
            ).consume()
        store.close()
