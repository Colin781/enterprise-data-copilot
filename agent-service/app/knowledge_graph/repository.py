from collections import deque
from typing import Protocol
from uuid import UUID

from neo4j import GraphDatabase, Query

from app.knowledge_graph.models import GraphEdge, GraphNode, Subgraph


class GraphStore(Protocol):
    def replace(self, tenant_id: UUID, source_id: UUID, graph: Subgraph) -> None: ...
    def subgraph(self, tenant_id: UUID, query: str, depth: int, limit: int) -> Subgraph: ...
    def path(self, tenant_id: UUID, source: str, target: str, depth: int) -> Subgraph: ...


class MemoryGraphStore:
    """Unit-test adapter; production uses Neo4j and persists across restarts."""

    def __init__(self):
        self.graphs: dict[tuple[UUID, UUID], Subgraph] = {}

    def replace(self, tenant_id, source_id, graph):
        self.graphs[tenant_id, source_id] = graph.model_copy(deep=True)

    def _all(self, tenant_id):
        graphs = [g for (tenant, _), g in self.graphs.items() if tenant == tenant_id]
        return [n for g in graphs for n in g.nodes], [e for g in graphs for e in g.edges]

    def subgraph(self, tenant_id, query, depth, limit):
        nodes, edges = self._all(tenant_id)
        seeds = [n.id for n in nodes if not query or _matches(n.name, query)][: limit + 1]
        selected = set(seeds)
        for _ in range(depth):
            adjacent = {e.target for e in edges if e.source in selected}
            adjacent |= {e.source for e in edges if e.target in selected}
            selected |= adjacent
        found = [n for n in nodes if n.id in selected]
        chosen = {n.id for n in found[:limit]}
        return Subgraph(
            nodes=found[:limit],
            edges=[e for e in edges if e.source in chosen and e.target in chosen][:200],
            truncated=len(found) > limit,
        )

    def path(self, tenant_id, source, target, depth):
        nodes, edges = self._all(tenant_id)
        lookup = {n.id: n for n in nodes}
        if source not in lookup or target not in lookup:
            return Subgraph()
        queue = deque([(source, [], {source})])
        while queue:
            node, route, visited = queue.popleft()
            if node == target:
                return Subgraph(nodes=[lookup[key] for key in sorted(visited)], edges=route)
            if len(route) >= depth:
                continue
            for edge in edges:
                neighbor = (
                    edge.target
                    if edge.source == node
                    else (edge.source if edge.target == node else None)
                )
                if neighbor and neighbor not in visited:
                    queue.append((neighbor, [*route, edge], visited | {neighbor}))
        return Subgraph()


def _matches(name, query):
    return name.casefold() in query.casefold() or query.casefold() in name.casefold()


class Neo4jGraphStore:
    def __init__(self, uri, user, password, database="neo4j"):
        self.driver = GraphDatabase.driver(
            uri, auth=(user, password), connection_timeout=5, max_transaction_retry_time=5
        )
        self.database = database

    def setup(self):
        with self.driver.session(database=self.database) as session:
            session.run(
                "CREATE CONSTRAINT graph_source_identity IF NOT EXISTS "
                "FOR (n:GraphSource) REQUIRE (n.tenant_id, n.id) IS UNIQUE"
            ).consume()
            session.run(
                "CREATE CONSTRAINT entity_identity IF NOT EXISTS "
                "FOR (n:Entity) REQUIRE (n.tenant_id, n.id) IS UNIQUE"
            ).consume()
            session.run(
                "CREATE INDEX entity_source IF NOT EXISTS "
                "FOR (n:Entity) ON (n.tenant_id, n.source_id)"
            ).consume()

    def close(self):
        self.driver.close()

    def replace(self, tenant_id, source_id, graph):
        tenant, source = str(tenant_id), str(source_id)

        def write(tx):
            # Lock the source record before replacement so concurrent extractions
            # cannot interleave their deletes and inserts.
            tx.run(
                "MERGE (s:GraphSource {tenant_id:$tenant, id:$source}) SET s.updated_at=datetime()",
                tenant=tenant,
                source=source,
            ).consume()
            tx.run(
                "MATCH (n:Entity {tenant_id:$tenant, source_id:$source}) DETACH DELETE n",
                tenant=tenant,
                source=source,
            ).consume()
            tx.run(
                "UNWIND $nodes AS node CREATE (n:Entity) SET n = node, n.tenant_id = $tenant",
                tenant=tenant,
                nodes=[n.model_dump(mode="json") for n in graph.nodes],
            ).consume()
            tx.run(
                "UNWIND $edges AS edge "
                "MATCH (a:Entity {tenant_id:$tenant, id:edge.source}), "
                "(b:Entity {tenant_id:$tenant, id:edge.target}) "
                "CREATE (a)-[r:RELATION]->(b) SET r = edge, r.tenant_id = $tenant",
                tenant=tenant,
                edges=[e.model_dump(mode="json") for e in graph.edges],
            ).consume()

        with self.driver.session(database=self.database) as session:
            session.execute_write(write)

    def subgraph(self, tenant_id, query, depth, limit):
        if not 0 <= depth <= 3 or not 1 <= limit <= 100:
            raise ValueError("invalid graph bounds")
        # Depth is a validated int. Every path node and relationship is tenant scoped.
        cypher = (
            "MATCH (seed:Entity {tenant_id:$tenant}) "
            "WHERE $q = '' OR toLower(seed.name) CONTAINS $q OR $q CONTAINS toLower(seed.name) "
            "WITH seed ORDER BY seed.id LIMIT $seed_limit "
            f"MATCH p=(seed)-[:RELATION*0..{depth}]-(n:Entity) "
            "WHERE all(x IN nodes(p) WHERE x.tenant_id=$tenant) "
            "AND all(r IN relationships(p) WHERE r.tenant_id=$tenant) "
            "RETURN DISTINCT properties(n) AS node ORDER BY node.id LIMIT $limit"
        )
        with self.driver.session(database=self.database) as session:
            nodes = [
                GraphNode.model_validate(r["node"])
                for r in session.run(
                    Query(cypher, timeout=5),
                    tenant=str(tenant_id),
                    q=query.casefold(),
                    limit=limit + 1,
                    seed_limit=limit + 1 if not query else min(10, limit + 1),
                )
            ]
            ids = [n.id for n in nodes[:limit]]
            edges = [
                GraphEdge.model_validate(r["edge"])
                for r in session.run(
                    Query(
                        "MATCH (a:Entity {tenant_id:$tenant})-[r:RELATION {tenant_id:$tenant}]->"
                        "(b:Entity {tenant_id:$tenant}) WHERE a.id IN $ids AND b.id IN $ids "
                        "RETURN properties(r) AS edge ORDER BY edge.id LIMIT 201",
                        timeout=5,
                    ),
                    tenant=str(tenant_id),
                    ids=ids,
                )
            ]
        return Subgraph(
            nodes=nodes[:limit], edges=edges[:200], truncated=len(nodes) > limit or len(edges) > 200
        )

    def path(self, tenant_id, source, target, depth):
        if not 1 <= depth <= 3:
            raise ValueError("invalid path depth")
        cypher = (
            "MATCH (a:Entity {tenant_id:$tenant, id:$source}), "
            "(b:Entity {tenant_id:$tenant, id:$target}) "
            f"MATCH p=shortestPath((a)-[:RELATION*..{depth}]-(b)) "
            "WHERE all(n IN nodes(p) WHERE n.tenant_id=$tenant) "
            "AND all(r IN relationships(p) WHERE r.tenant_id=$tenant) "
            "RETURN [n IN nodes(p) | properties(n)] AS nodes, "
            "[r IN relationships(p) | properties(r)] AS edges LIMIT 1"
        )
        with self.driver.session(database=self.database) as session:
            row = session.run(
                Query(cypher, timeout=5), tenant=str(tenant_id), source=source, target=target
            ).single()
            return Subgraph.model_validate(dict(row)) if row else Subgraph()
