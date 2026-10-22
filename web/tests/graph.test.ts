import assert from "node:assert/strict";
import test from "node:test";
import { filterGraph, type Subgraph } from "../src/lib/graph.ts";

test("type filters retain only edges whose endpoints remain visible", () => {
  const graph = { nodes: [{ id: "metric", kind: "Metric" }, { id: "column", kind: "Column" }],
    edges: [{ id: "edge", source: "metric", target: "column", kind: "USES_COLUMN" }],
    truncated: false } as Subgraph;
  assert.equal(filterGraph(graph, ["Metric"], ["USES_COLUMN"]).edges.length, 0);
  assert.equal(filterGraph(graph, ["Metric", "Column"], ["USES_COLUMN"]).edges.length, 1);
  assert.equal(filterGraph(graph, ["Metric", "Column"], []).edges.length, 0);
});
