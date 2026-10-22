export const entityKinds = ["Metric", "Table", "Column", "BusinessTerm", "Document", "DataSource"] as const;
export const relationKinds = ["DEFINED_IN", "DERIVED_FROM", "USES_COLUMN", "BELONGS_TO", "RELATED_TO", "JOINS_WITH"] as const;
export interface GraphNode {
  id: string; name: string; kind: string; source_id: string; source_name: string;
  evidence: string; confidence: number; extracted_at: string;
}
export interface GraphEdge {
  id: string; source: string; target: string; kind: string; source_id: string;
  source_name: string; evidence: string; confidence: number; extracted_at: string;
}
export interface Subgraph { nodes: GraphNode[]; edges: GraphEdge[]; truncated: boolean }
export interface GraphAnswer {
  answer: string; graph: Subgraph; should_answer: boolean;
  citations: { id: string; text: string; source_name?: string; document_title?: string }[];
}

export function filterGraph(graph: Subgraph, kinds: string[], relations: string[]): Subgraph {
  const nodes = graph.nodes.filter(n => kinds.includes(n.kind)).slice(0, 100);
  const ids = new Set(nodes.map(n => n.id));
  return { nodes, edges: graph.edges.filter(e => relations.includes(e.kind)
    && ids.has(e.source) && ids.has(e.target)).slice(0, 200), truncated: graph.truncated };
}
