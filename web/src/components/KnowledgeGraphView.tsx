"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { actionableError, api } from "@/lib/api";
import { entityKinds, relationKinds, filterGraph, type GraphAnswer, type GraphNode, type GraphEdge, type Subgraph } from "@/lib/graph";
import type { Session } from "@/lib/types";

const empty: Subgraph = { nodes: [], edges: [], truncated: false };
const colors = ["#31c48d", "#6ea8fe", "#f5b94c", "#bd95ee", "#ef7d9c", "#73d9db"];
const symbols = ["circle", "rect", "diamond", "roundRect", "triangle", "pin"];

export function KnowledgeGraphView({ session }: { session: Session }) {
  const [graph, setGraph] = useState<Subgraph>(empty);
  const [query, setQuery] = useState("");
  const [depth, setDepth] = useState(1);
  const [kinds, setKinds] = useState<string[]>([...entityKinds]);
  const [relations, setRelations] = useState<string[]>([...relationKinds]);
  const [detail, setDetail] = useState<GraphNode | GraphEdge | null>(null);
  const [answer, setAnswer] = useState<GraphAnswer | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const filtered = useMemo(() => filterGraph(graph, kinds, relations), [graph, kinds, relations]);
  async function load(action: () => Promise<Subgraph>) {
    setPending(true); setError(""); setDetail(null); setAnswer(null);
    try { setGraph(await action()); } catch (reason) { setError(actionableError(reason)); }
    finally { setPending(false); }
  }
  async function ask() {
    setPending(true); setError(""); setDetail(null);
    try { const result = await api.graphAnswer(session.accessToken, query); setAnswer(result); setGraph(result.graph); }
    catch (reason) { setError(actionableError(reason)); } finally { setPending(false); }
  }
  return <section className="graph-page">
    <header className="view-heading"><div><p className="eyebrow">KNOWLEDGE NETWORK</p>
      <h1>关系网络与证据问答</h1><p>搜索业务实体，查看关联路径和原文证据。</p></div></header>
    <form className="panel graph-controls" onSubmit={e => { e.preventDefault(); void load(() => api.graphSearch(session.accessToken, query, depth)); }}>
      <label>实体或业务问题<input value={query} maxLength={4000} onChange={e => setQuery(e.target.value)} placeholder="例如 Revenue、销售额依赖哪些字段" /></label>
      <label>关联层数<select value={depth} onChange={e => setDepth(Number(e.target.value))}>{[0, 1, 2, 3].map(n => <option key={n}>{n}</option>)}</select></label>
      <button className="primary" disabled={pending}>搜索关系</button>
      <button type="button" className="ghost" disabled={pending || !query.trim()} onClick={() => void ask()}>基于证据回答</button>
    </form>
    {error && <p className="callout error" role="alert">{error}</p>}
    {pending && <p role="status">正在读取知识网络…</p>}
    <div className="graph-layout">
      <div className="panel graph-canvas-panel">
        <div className="graph-filters"><label>实体类型<select multiple value={kinds} onChange={e => setKinds(Array.from(e.target.selectedOptions, o => o.value))}>{entityKinds.map(k => <option key={k}>{k}</option>)}</select></label>
          <label>关系类型<select multiple value={relations} onChange={e => setRelations(Array.from(e.target.selectedOptions, o => o.value))}>{relationKinds.map(k => <option key={k}>{k}</option>)}</select></label>
          <p className="muted">按住 Ctrl / ⌘ 可多选。拖动节点、滚轮缩放；悬停可高亮邻居。</p></div>
        {filtered.nodes.length ? <GraphCanvas graph={filtered} onSelect={setDetail} /> : <div className="graph-empty">暂无匹配实体。请搜索，或由管理员导入来源文本。</div>}
        <p className="muted">{filtered.nodes.length} 个节点 · {filtered.edges.length} 条关系{graph.truncated ? " · 结果已截断，请缩小搜索范围" : ""}</p>
        <form className="graph-path" onSubmit={e => { e.preventDefault(); void load(() => api.graphPath(session.accessToken, source, target)); }}>
          <label>起点<select value={source} onChange={e => setSource(e.target.value)}><option value="">选择节点</option>{graph.nodes.map(n => <option key={n.id} value={n.id}>{n.name}</option>)}</select></label>
          <label>终点<select value={target} onChange={e => setTarget(e.target.value)}><option value="">选择节点</option>{graph.nodes.map(n => <option key={n.id} value={n.id}>{n.name}</option>)}</select></label>
          <button className="ghost" disabled={pending || !source || !target || source === target}>查询三跳内路径</button>
        </form>
        <details><summary>可访问的节点列表</summary>{filtered.nodes.map(n => <button className="ghost" key={n.id} onClick={() => setDetail(n)}>{n.name}</button>)}</details>
      </div>
      <aside className="panel graph-detail"><h2>来源与证据</h2>{detail ? <>
        <h3>{"name" in detail ? detail.name : detail.kind}</h3><p>类型：{detail.kind}</p>
        <p>来源：{detail.source_name}</p><p>置信度：{(detail.confidence * 100).toFixed(1)}%</p>
        <p>抽取时间：{new Date(detail.extracted_at).toLocaleString()}</p><blockquote>{detail.evidence}</blockquote>
      </> : <p className="muted">点击节点或关系查看原文。</p>}</aside>
    </div>
    {answer && <section className="panel graph-answer"><h2>{answer.should_answer ? "回答与引用" : "证据不足"}</h2>
      <p className="graph-answer-text">{answer.answer}</p>{answer.citations.map(c => <details key={c.id}><summary>{c.source_name ?? c.document_title ?? c.id}</summary><p>{c.id}</p><blockquote>{c.text}</blockquote></details>)}</section>}
    {session.roles.includes("ADMIN") && <ExtractionForm disabled={pending} onExtract={(id, name, text) => load(() => api.graphExtract(session.accessToken, id, name, text))} />}
  </section>;
}

function ExtractionForm({ disabled, onExtract }: { disabled: boolean; onExtract: (id: string, name: string, text: string) => Promise<void> }) {
  const [sourceId, setSourceId] = useState("");
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    const id = sourceId || crypto.randomUUID(); setSourceId(id);
    void onExtract(id, String(data.get("name")), String(data.get("text")));
  }
  return <details className="panel graph-extraction"><summary>管理员：抽取来源文本中的实体与关系</summary>
    <form onSubmit={submit}><label>来源标识（同一标识再次抽取会替换该来源的图）<input value={sourceId} onChange={e => setSourceId(e.target.value)} placeholder="留空自动生成 UUID" pattern="[0-9a-fA-F-]{36}" /></label>
      <label>来源名称<input name="name" required maxLength={255} placeholder="例如：销售额指标说明" /></label>
      <label>来源原文<textarea name="text" required maxLength={20000} rows={7} /></label>
      <button className="primary" disabled={disabled}>抽取并保存</button></form></details>;
}

function GraphCanvas({ graph, onSelect }: { graph: Subgraph; onSelect: (value: GraphNode | GraphEdge) => void }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let disposed = false;
    let cleanup = () => {};
    void Promise.all([import("echarts/core"), import("echarts/charts"), import("echarts/components"), import("echarts/renderers")]).then(([core, charts, components, renderers]) => {
      if (disposed || !host.current) return;
      core.use([charts.GraphChart, components.TooltipComponent, components.LegendComponent, renderers.CanvasRenderer]);
      const chart = core.init(host.current, "dark");
      chart.setOption({ backgroundColor: "transparent", tooltip: { renderMode: "richText" },
        series: [{ type: "graph", layout: "force", roam: true, draggable: true,
          force: { repulsion: 240, edgeLength: 110 }, emphasis: { focus: "adjacency" },
          label: { show: true, position: "right", formatter: "{b}", color: "#e9f7ef" },
          edgeLabel: { show: true, formatter: "{c}", color: "#91aa9e", fontSize: 10 },
          edgeSymbol: ["none", "arrow"], lineStyle: { color: "#547463", curveness: 0.12 },
          data: graph.nodes.map(n => ({ id: n.id, name: n.name, symbolSize: n.kind === "Metric" ? 38 : 25,
            symbol: symbols[Math.max(0, entityKinds.indexOf(n.kind as typeof entityKinds[number]))],
            itemStyle: { color: colors[Math.max(0, entityKinds.indexOf(n.kind as typeof entityKinds[number]))] } })),
          links: graph.edges.map(e => ({ id: e.id, source: e.source, target: e.target, value: e.kind })) }],
      });
      chart.on("click", params => {
        const item = params.data as { id?: string };
        const detail = params.dataType === "edge" ? graph.edges.find(e => e.id === item?.id) : graph.nodes.find(n => n.id === item?.id);
        if (detail) onSelect(detail);
      });
      const observer = new ResizeObserver(() => chart.resize()); observer.observe(host.current);
      cleanup = () => { observer.disconnect(); chart.dispose(); };
    });
    return () => { disposed = true; cleanup(); };
  }, [graph, onSelect]);
  return <div ref={host} className="graph-canvas" role="img" aria-label="业务实体关系网络，可使用下方节点列表查看证据" />;
}
