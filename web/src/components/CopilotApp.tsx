"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, actionableError } from "@/lib/api";
import { streamJobEvents } from "@/lib/sse";
import type { AgentStep, AnalysisJob, Approval, DataSource, MetricDocument, Session } from "@/lib/types";
import { StructuredChart } from "./StructuredChart";

type View = "analysis" | "sources" | "knowledge" | "approvals" | "overview";
type ResultTab = "answer" | "table" | "chart" | "sql";

const terminal = new Set(["COMPLETED", "REJECTED", "FAILED", "CANCELLED"]);
const statusLabels: Record<string, string> = {
  CREATED: "已接收", PLANNING: "规划中", VALIDATING: "安全校验", WAITING_APPROVAL: "等待审批",
  RUNNING: "执行中", COMPLETED: "已完成", REJECTED: "已拒绝", FAILED: "失败", CANCELLED: "已取消",
};
const stepLabels: Record<string, string> = {
  classify: "识别意图", retrieve_metrics: "检索指标", select_schema: "选择数据表", generate_sql: "生成 SQL",
  guard_sql: "安全检查", request_approval: "请求审批", execute_sql: "只读执行", verify: "校验结果", compose: "生成结论",
};
const jobErrorMessages: Record<string, string> = {
  LLM_AUTHENTICATION_ERROR: "模型服务拒绝了凭证，请检查 API Key。",
  LLM_CONFIGURATION_ERROR: "模型服务尚未完成配置。",
  LLM_INVALID_RESPONSE: "模型没有返回符合约束的结构化结果。",
  LLM_RATE_LIMITED: "模型服务当前限流，请稍后重试。",
  LLM_REQUEST_REJECTED: "模型供应商拒绝了本次请求，请检查模型或账号策略。",
  LLM_TIMEOUT: "模型请求超时，请稍后重试。",
  LLM_UNAVAILABLE: "模型服务暂时不可用，请稍后重试。",
  AGENT_WORKFLOW_FAILED: "Agent 工作流执行失败，请查看执行轨迹。",
  AGENT_DISPATCH_FAILED: "平台无法调用 Agent 服务，请检查服务日志。",
};

export function CopilotApp() {
  const [session, setSession] = useState<Session | null>(() => loadSession());
  useEffect(() => {
    const logout = () => { sessionStorage.removeItem("copilot.session"); setSession(null); };
    window.addEventListener("copilot:unauthorized", logout);
    return () => window.removeEventListener("copilot:unauthorized", logout);
  }, []);
  if (!session) return <Login onLogin={(value) => { sessionStorage.setItem("copilot.session", JSON.stringify(value)); setSession(value); }} />;
  return <Workspace session={session} onLogout={() => { sessionStorage.removeItem("copilot.session"); setSession(null); }} />;
}

function Login({ onLogin }: { onLogin: (session: Session) => void }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setError("");
    const data = new FormData(event.currentTarget);
    try { onLogin(await api.login(String(data.get("tenant")), String(data.get("email")), String(data.get("password")))); }
    catch (reason) { setError(actionableError(reason)); }
    finally { setPending(false); }
  }
  return (
    <main className="login-shell">
      <section className="login-story">
        <span className="brand-mark">ED</span>
        <p className="eyebrow">ENTERPRISE DATA COPILOT</p>
        <h1>从业务问题，到可信答案。</h1>
        <p>以只读 SQL、安全策略和完整执行轨迹为边界的零售数据分析工作台。</p>
        <div className="trust-row"><span>只读执行</span><span>租户隔离</span><span>全程可追踪</span></div>
      </section>
      <section className="login-panel">
        <form onSubmit={submit}>
          <div><p className="eyebrow">SECURE ACCESS</p><h2>登录工作台</h2><p className="muted">使用平台账号进入所属租户空间。</p></div>
          <label>租户标识<input name="tenant" autoComplete="organization" placeholder="例如 northwind" required /></label>
          <label>邮箱<input name="email" type="email" autoComplete="username" placeholder="name@company.com" required /></label>
          <label>密码<input name="password" type="password" autoComplete="current-password" required /></label>
          {error && <div className="callout error" role="alert">{error}</div>}
          <button className="primary wide" disabled={pending}>{pending ? "正在验证…" : "安全登录"}</button>
        </form>
      </section>
    </main>
  );
}

function Workspace({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const isAdmin = session.roles.includes("ADMIN");
  const [view, setView] = useState<View>("analysis");
  const [sources, setSources] = useState<DataSource[]>([]);
  const [jobs, setJobs] = useState<AnalysisJob[]>([]);
  const [documents, setDocuments] = useState<MetricDocument[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    try {
      const [sourceData, jobData, documentData, approvalData] = await Promise.all([
        api.dataSources(session.accessToken), api.jobs(session.accessToken), api.metricDocuments(session.accessToken),
        isAdmin ? api.approvals(session.accessToken) : Promise.resolve([]),
      ]);
      setSources(sourceData); setJobs(jobData); setDocuments(documentData); setApprovals(approvalData); setError("");
    } catch (reason) { setError(actionableError(reason)); }
    finally { setLoading(false); }
  }, [isAdmin, session.accessToken]);
  useEffect(() => {
    const timer = window.setTimeout(() => void refresh(), 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);
  const nav: { id: View; label: string; admin?: boolean }[] = [
    { id: "analysis", label: "分析工作台" }, { id: "sources", label: "数据源" },
    { id: "knowledge", label: "指标知识" }, { id: "approvals", label: "审批中心", admin: true },
    { id: "overview", label: "管理概览", admin: true },
  ];
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark small">ED</span><div><b>Data Copilot</b><small>可信分析工作台</small></div></div>
        <nav aria-label="主导航">{nav.filter((item) => !item.admin || isAdmin).map((item) =>
          <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}>
            <NavIcon name={item.id} />{item.label}{item.id === "approvals" && approvals.some((a) => a.status === "PENDING") && <i className="nav-dot" />}
          </button>)}</nav>
        <div className="sidebar-foot"><div className="avatar">{session.roles[0]?.slice(0, 1)}</div><div><b>{session.roles.join(" · ")}</b><small>{shortId(session.tenantId)}</small></div><button onClick={onLogout} aria-label="退出登录">退出</button></div>
      </aside>
      <main className="workspace">
        <header className="topbar"><div><span className="live-dot" />平台连接已保护</div><button className="ghost" onClick={() => void refresh()}>刷新数据</button></header>
        {error && <div className="callout error page-callout" role="alert">{error}</div>}
        {loading ? <div className="loading-panel">正在读取租户工作区…</div> : <>
          {view === "analysis" && <AnalysisView session={session} sources={sources} initialJobs={jobs} onJobsChanged={refresh} onOpenApprovals={() => setView("approvals")} />}
          {view === "sources" && <SourcesView session={session} sources={sources} isAdmin={isAdmin} onChanged={refresh} />}
          {view === "knowledge" && <KnowledgeView session={session} documents={documents} isAdmin={isAdmin} onChanged={refresh} />}
          {view === "approvals" && isAdmin && <ApprovalsView session={session} approvals={approvals} jobs={jobs} onChanged={refresh} />}
          {view === "overview" && isAdmin && <Overview sources={sources} documents={documents} jobs={jobs} approvals={approvals} />}
        </>}
      </main>
    </div>
  );
}

function AnalysisView({ session, sources, initialJobs, onJobsChanged, onOpenApprovals }: {
  session: Session; sources: DataSource[]; initialJobs: AnalysisJob[]; onJobsChanged: () => Promise<void>; onOpenApprovals: () => void;
}) {
  const [jobs, setJobs] = useState(initialJobs);
  const [selectedId, setSelectedId] = useState(initialJobs[0]?.id ?? "");
  const [job, setJob] = useState<AnalysisJob | null>(initialJobs[0] ?? null);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [question, setQuestion] = useState("");
  const [sourceId, setSourceId] = useState(sources[0]?.id ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<ResultTab>("answer");
  const [elapsed, setElapsed] = useState(0);
  const lastEvent = useRef<string | undefined>(undefined);
  const visibleJobs = useMemo(() => {
    const combined = [...jobs, ...initialJobs.filter((item) => !jobs.some((jobItem) => jobItem.id === item.id))];
    return combined.sort((left, right) => right.created_at.localeCompare(left.created_at));
  }, [initialJobs, jobs]);
  const reloadJob = useCallback(async (id: string) => {
    const [nextJob, nextSteps] = await Promise.all([api.job(session.accessToken, id), api.steps(session.accessToken, id)]);
    setJob(nextJob); setSteps(nextSteps); setJobs((current) => [nextJob, ...current.filter((item) => item.id !== nextJob.id)]);
    return nextJob;
  }, [session.accessToken]);
  useEffect(() => {
    if (!selectedId) return;
    const timer = window.setTimeout(
      () => void reloadJob(selectedId).catch((reason) => setError(actionableError(reason))),
      0,
    );
    return () => window.clearTimeout(timer);
  }, [reloadJob, selectedId]);
  useEffect(() => {
    if (!job || terminal.has(job.status)) return;
    const controller = new AbortController();
    void streamJobEvents(session.accessToken, job.id, (event) => {
      lastEvent.current = event.event_id;
      setJob((current) => current ? { ...current, status: event.status, updated_at: event.occurred_at } : current);
      void reloadJob(job.id).catch(() => undefined);
    }, controller.signal, lastEvent.current).catch(() => undefined);
    const poll = window.setInterval(() => void reloadJob(job.id).catch(() => undefined), 3000);
    return () => { controller.abort(); window.clearInterval(poll); };
  }, [job?.id, job?.status, reloadJob, session.accessToken]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!job || terminal.has(job.status)) return;
    const started = new Date(job.created_at).getTime();
    const tick = () => setElapsed(Math.max(0, Math.floor((Date.now() - started) / 1000)));
    tick(); const timer = window.setInterval(tick, 1000); return () => window.clearInterval(timer);
  }, [job]);
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!question.trim() || !sourceId) return;
    setSubmitting(true); setError("");
    try {
      const created = await api.createJob(session.accessToken, sourceId, question.trim());
      setJobs((current) => [created, ...current]); setSelectedId(created.id); setJob(created); setQuestion(""); lastEvent.current = undefined;
      await onJobsChanged();
    } catch (reason) { setError(actionableError(reason)); }
    finally { setSubmitting(false); }
  }
  return (
    <section className="view analysis-view">
      <div className="view-heading"><div><p className="eyebrow">ANALYSIS</p><h1>分析工作台</h1><p>自然语言提问，实时查看安全执行链路与结构化结果。</p></div><StatusLegend /></div>
      <div className="analysis-grid">
        <section className="history-panel panel"><div className="panel-title"><h2>最近任务</h2><span>{jobs.length}</span></div>
          <div className="job-list">{visibleJobs.length ? visibleJobs.map((item) => <button key={item.id} className={selectedId === item.id ? "selected" : ""} onClick={() => setSelectedId(item.id)}>
            <span className={`status-dot ${item.status.toLowerCase()}`} /><div><b>{item.question}</b><small>{formatTime(item.created_at)} · {statusLabels[item.status]}</small></div>
          </button>) : <div className="empty-state compact">还没有分析任务。</div>}</div></section>
        <div className="analysis-main">
          <form className="question-box panel" onSubmit={submit}>
            <div className="question-meta"><select aria-label="数据源" value={sourceId} onChange={(event) => setSourceId(event.target.value)} required>
              <option value="">选择数据源</option>{sources.filter((item) => item.enabled).map((source) => <option key={source.id} value={source.id}>{source.name} · {source.allowed_schema}</option>)}
            </select><span>只读查询 · 最多返回 100 行</span></div>
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={4000} placeholder="例如：按季度展示销售额，并说明采用的指标口径" aria-label="分析问题" />
            <div className="question-actions"><small>{question.length}/4000</small><button className="primary" disabled={submitting || !sources.length}>{submitting ? "正在提交…" : "开始分析 →"}</button></div>
          </form>
          {error && <div className="callout error" role="alert">{error}</div>}
          {job ? <>
            <section className="job-status panel"><div><span className={`status-pill ${job.status.toLowerCase()}`}>{statusLabels[job.status]}</span><b>{job.question}</b></div>
              {!terminal.has(job.status) && <p><span className="spinner" />已执行 {elapsed} 秒 · 最后状态 {formatTime(job.updated_at)}{elapsed > 30 && " · 长查询仍在受控执行，可离开页面后返回"}</p>}
              {job.status === "WAITING_APPROVAL" && <button className="secondary" onClick={onOpenApprovals}>前往审批中心</button>}
              {job.error_code && <div className="callout error">{jobErrorMessages[job.error_code] ?? `${job.error_code}：任务未完成，请查看执行轨迹。`}<small>Trace {job.trace_id}</small></div>}
            </section>
            <section className="result-panel panel"><div className="tabs" role="tablist">{(["answer", "table", "chart", "sql"] as ResultTab[]).map((item) => <button key={item} role="tab" aria-selected={tab === item} className={tab === item ? "active" : ""} onClick={() => setTab(item)}>{({ answer: "结论", table: "数据表", chart: "图表", sql: "SQL" })[item]}</button>)}</div>
              <div className="tab-content">{tab === "answer" && <Answer job={job} />}{tab === "table" && <ResultTable columns={job.columns} rows={job.rows} />}{tab === "chart" && <StructuredChart spec={job.chart} columns={job.columns} rows={job.rows} />}{tab === "sql" && <SqlPanel sql={job.generated_sql} />}</div>
            </section>
            <Timeline steps={steps} />
          </> : <div className="empty-state panel"><b>准备好开始第一次可信分析</b><p>选择数据源并提出一个零售经营问题，任务状态会在这里实时更新。</p></div>}
        </div>
      </div>
    </section>
  );
}

function Answer({ job }: { job: AnalysisJob }) {
  return <div className="answer"><h3>分析结论</h3><p>{job.answer || (terminal.has(job.status) ? "本次任务没有生成文字结论。" : "结论将在安全执行完成后显示。")}</p>
    {!!job.citations.length && <div className="citations"><h4>指标依据</h4>{job.citations.map((citation, index) => <div key={`${citation.document_id}-${index}`}><b>{citation.document_title ?? "指标文档"} v{citation.document_version ?? "—"}</b><span>{citation.section_title ?? citation.section_key} · {citation.source_locator}</span></div>)}</div>}</div>;
}

function ResultTable({ columns, rows }: { columns: string[]; rows: Record<string, unknown>[] }) {
  const [page, setPage] = useState(0); const pageSize = 20; const pages = Math.max(1, Math.ceil(rows.length / pageSize));
  const currentPage = Math.min(page, pages - 1);
  if (!columns.length) return <div className="empty-state compact">查询完成后将在这里展示受限结果集。</div>;
  return <div><div className="table-wrap"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.slice(currentPage * pageSize, (currentPage + 1) * pageSize).map((row, index) => <tr key={index}>{columns.map((column) => <td key={column}>{displayCell(row[column])}</td>)}</tr>)}</tbody></table></div>
    <div className="pagination"><span>共 {rows.length} 行 · 每页 {pageSize} 行{rows.length >= 100 && " · 结果可能已按安全上限截断"}</span><div><button disabled={currentPage === 0} onClick={() => setPage((value) => Math.max(0, value - 1))}>上一页</button><b>{currentPage + 1}/{pages}</b><button disabled={currentPage + 1 >= pages} onClick={() => setPage((value) => Math.min(pages - 1, value + 1))}>下一页</button></div></div></div>;
}

function SqlPanel({ sql }: { sql?: string | null }) {
  const [confirming, setConfirming] = useState(false); const [copied, setCopied] = useState(false);
  if (!sql) return <div className="empty-state compact">通过安全校验的 SQL 将在这里以只读方式展示。</div>;
  async function copy() { await navigator.clipboard.writeText(sql!); setCopied(true); setConfirming(false); window.setTimeout(() => setCopied(false), 1800); }
  return <div className="sql-panel"><div className="code-head"><span>只读 SQL · 仅供审阅</span><button onClick={() => setConfirming(true)}>{copied ? "已复制" : "复制 SQL"}</button></div><pre><code>{sql}</code></pre>
    {confirming && <div className="copy-warning" role="alert"><b>离开平台执行可能绕过安全边界</b><p>请仅在只读账号、限定 schema 和查询超时均已启用的环境使用。</p><div><button onClick={() => setConfirming(false)}>取消</button><button className="danger-button" onClick={() => void copy()}>理解风险并复制</button></div></div>}</div>;
}

function Timeline({ steps }: { steps: AgentStep[] }) {
  return <section className="timeline panel"><div className="panel-title"><h2>Agent 执行轨迹</h2><span>{steps.length} 步</span></div>{steps.length ? <ol>{steps.map((step) => <li key={step.id} className={step.status.toLowerCase()}><i /><div><b>{stepLabels[step.step_name] ?? step.step_name}</b><span>{step.status === "SUCCEEDED" ? "完成" : step.status === "WAITING" ? "等待" : "失败"} · {step.duration_ms} ms{step.attempt > 1 ? ` · 第 ${step.attempt} 次尝试` : ""}</span>{step.error_code && <small>{step.error_code}</small>}</div><time>{formatTime(step.created_at)}</time></li>)}</ol> : <div className="empty-state compact">轨迹将在任务开始后按提交顺序显示，输入输出仅保存脱敏摘要。</div>}</section>;
}

function SourcesView({ session, sources, isAdmin, onChanged }: { session: Session; sources: DataSource[]; isAdmin: boolean; onChanged: () => Promise<void> }) {
  const [open, setOpen] = useState(false); const [pending, setPending] = useState(false); const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setPending(true); setError(""); const data = new FormData(event.currentTarget);
    try { await api.createDataSource(session.accessToken, { name: data.get("name"), host: data.get("host"), port: Number(data.get("port")), database_name: data.get("database"), allowed_schema: data.get("schema"), secret_ref: data.get("secret") }); setOpen(false); await onChanged(); }
    catch (reason) { setError(actionableError(reason)); } finally { setPending(false); }
  }
  return <section className="view"><div className="view-heading"><div><p className="eyebrow">DATA SOURCES</p><h1>数据源管理</h1><p>平台仅保存凭据引用，分析服务始终使用只读数据库账号。</p></div>{isAdmin && <button className="primary" onClick={() => setOpen(true)}>+ 登记数据源</button>}</div>
    <div className="card-grid">{sources.map((source) => <article className="resource-card" key={source.id}><div><span className="database-icon">DB</span><span className={`status-pill ${source.enabled ? "completed" : "cancelled"}`}>{source.enabled ? "可用" : "停用"}</span></div><h2>{source.name}</h2><p>PostgreSQL · schema <code>{source.allowed_schema}</code></p><footer><span>凭据已托管</span><small>v{source.version}</small></footer></article>)}{!sources.length && <div className="empty-state panel">当前租户还没有登记数据源。</div>}</div>
    {open && <Modal title="登记 PostgreSQL 数据源" onClose={() => setOpen(false)}><form className="form-grid" onSubmit={submit}><label>名称<input name="name" required maxLength={160} /></label><label>主机<input name="host" required /></label><label>端口<input name="port" type="number" defaultValue="5432" min="1" max="65535" required /></label><label>数据库<input name="database" required /></label><label>允许的 schema<input name="schema" defaultValue="northwind" pattern="[a-z_][a-z0-9_]*" required /></label><label>凭据引用<input name="secret" placeholder="env:BUSINESS_DB_READONLY" pattern="(env|vault|secret):[A-Za-z0-9_./-]+" required /></label>{error && <div className="callout error full">{error}</div>}<div className="modal-actions full"><button type="button" onClick={() => setOpen(false)}>取消</button><button className="primary" disabled={pending}>{pending ? "正在登记…" : "登记数据源"}</button></div></form></Modal>}
  </section>;
}

function KnowledgeView({ session, documents, isAdmin, onChanged }: { session: Session; documents: MetricDocument[]; isAdmin: boolean; onChanged: () => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null); const [title, setTitle] = useState(""); const [pending, setPending] = useState(false); const [error, setError] = useState("");
  async function upload(event: FormEvent) { event.preventDefault(); if (!file) return; setPending(true); setError("");
    try { if (file.size > 10_000_000) throw new Error("too large"); const sourceType = file.name.toLowerCase().endsWith(".pdf") ? "PDF" : "MARKDOWN"; await api.uploadMetricDocument(session.accessToken, { title, source_name: file.name, source_type: sourceType, content_base64: await fileBase64(file) }); setFile(null); setTitle(""); await onChanged(); }
    catch (reason) { setError(reason instanceof Error && reason.message === "too large" ? "文件超过 10 MB，请拆分后上传。" : actionableError(reason)); } finally { setPending(false); }
  }
  return <section className="view"><div className="view-heading"><div><p className="eyebrow">METRIC KNOWLEDGE</p><h1>指标知识库</h1><p>按租户管理指标定义与口径，更新同名文档会生成新版本。</p></div></div>
    {isAdmin && <form className="upload-box panel" onSubmit={upload}><div><b>上传 Markdown 或 PDF</b><p>Markdown ≤ 2 MB，PDF ≤ 10 MB / 100 页；索引内容不会发送到浏览器。</p></div><input aria-label="文档标题" placeholder="文档标题" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={240} required /><label className="file-picker"><input type="file" accept=".md,.markdown,.pdf,text/markdown,application/pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} required /><span>{file ? file.name : "选择文档"}</span></label><button className="primary" disabled={pending}>{pending ? "解析并索引中…" : "上传并建立索引"}</button>{error && <div className="callout error full">{error}</div>}</form>}
    <div className="document-list panel"><div className="panel-title"><h2>文档版本</h2><span>{documents.length}</span></div>{documents.length ? <table><thead><tr><th>文档</th><th>类型</th><th>版本</th><th>状态</th><th>更新时间</th></tr></thead><tbody>{documents.map((document) => <tr key={document.id}><td><b>{document.title}</b><small>{document.source_name}</small></td><td>{document.source_type}</td><td>v{document.version}</td><td><span className={`status-pill ${document.status === "ACTIVE" ? "completed" : "cancelled"}`}>{document.status === "ACTIVE" ? "生效中" : "历史版本"}</span></td><td>{formatDate(document.updated_at)}</td></tr>)}</tbody></table> : <div className="empty-state compact">还没有指标文档，分析仍可执行数据查询，但不会提供口径引用。</div>}</div>
  </section>;
}

function ApprovalsView({ session, approvals, jobs, onChanged }: { session: Session; approvals: Approval[]; jobs: AnalysisJob[]; onChanged: () => Promise<void> }) {
  const [busy, setBusy] = useState(""); const [error, setError] = useState("");
  async function decide(id: string, decision: "approve" | "reject") { const comment = window.prompt(decision === "approve" ? "审批备注（可选）" : "请说明拒绝原因", "") ?? ""; setBusy(id); setError(""); try { await api.decideApproval(session.accessToken, id, decision, comment); await onChanged(); } catch (reason) { setError(actionableError(reason)); } finally { setBusy(""); } }
  const pending = approvals.filter((item) => item.status === "PENDING");
  return <section className="view"><div className="view-heading"><div><p className="eyebrow">HUMAN REVIEW</p><h1>审批中心</h1><p>仅管理员可处理高成本、受控字段或低置信度查询。</p></div><span className="count-badge">{pending.length} 待处理</span></div>{error && <div className="callout error">{error}</div>}
    <div className="approval-list">{approvals.map((approval) => { const job = jobs.find((item) => item.id === approval.analysis_job_id); return <article className="approval-card panel" key={approval.id}><header><span className={`status-pill ${approval.status.toLowerCase()}`}>{approval.status === "PENDING" ? "待审批" : approval.status === "APPROVED" ? "已批准" : "已拒绝"}</span><time>{formatDate(approval.created_at)}</time></header><h2>{job?.question ?? `分析任务 ${shortId(approval.analysis_job_id)}`}</h2><div className="risk-box"><b>触发原因</b><p>{approval.reason.split(",").join(" · ")}</p></div>{job?.generated_sql && <pre><code>{job.generated_sql}</code></pre>}{approval.status === "PENDING" && <footer><button disabled={busy === approval.id} className="danger-button" onClick={() => void decide(approval.id, "reject")}>拒绝</button><button disabled={busy === approval.id} className="primary" onClick={() => void decide(approval.id, "approve")}>{busy === approval.id ? "处理中…" : "批准一次执行"}</button></footer>}{approval.decision_comment && <p className="decision-note">审批备注：{approval.decision_comment}</p>}</article>; })}{!approvals.length && <div className="empty-state panel">没有审批记录。</div>}</div>
  </section>;
}

function Overview({ sources, documents, jobs, approvals }: { sources: DataSource[]; documents: MetricDocument[]; jobs: AnalysisJob[]; approvals: Approval[] }) {
  const completed = jobs.filter((job) => job.status === "COMPLETED").length; const failed = jobs.filter((job) => job.status === "FAILED" || job.status === "REJECTED").length;
  return <section className="view"><div className="view-heading"><div><p className="eyebrow">TENANT OVERVIEW</p><h1>管理概览</h1><p>只展示当前租户可追溯的业务状态；P95 与模型成本将在 P11 接入观测数据后开放。</p></div></div><div className="metric-grid"><Metric label="数据源" value={sources.length} note={`${sources.filter((item) => item.enabled).length} 个可用`} /><Metric label="指标文档" value={documents.filter((item) => item.status === "ACTIVE").length} note="当前有效版本" /><Metric label="分析任务" value={jobs.length} note={`${completed} 完成 · ${failed} 失败/拒绝`} /><Metric label="待审批" value={approvals.filter((item) => item.status === "PENDING").length} note="需要管理员操作" /></div><div className="panel scope-note"><h2>可观测性边界</h2><p>本页不会用前端推算值冒充服务指标。请求量、错误率、P95、Token 与成本需要 P11 的服务端指标链路提供可核验证据。</p></div></section>;
}

function Metric({ label, value, note }: { label: string; value: number; note: string }) { return <article className="metric-card panel"><span>{label}</span><strong>{value}</strong><small>{note}</small></article>; }
function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) { return <div className="modal-backdrop" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}><section className="modal panel" role="dialog" aria-modal="true" aria-label={title}><header><h2>{title}</h2><button onClick={onClose} aria-label="关闭">×</button></header>{children}</section></div>; }
function StatusLegend() { return <div className="status-legend"><span><i className="live-dot" />实时进度</span><span>PostgreSQL 最终状态</span></div>; }
function NavIcon({ name }: { name: View }) { const paths: Record<View, string> = { analysis: "M4 5h16M4 12h10M4 19h7", sources: "M5 5c0-2 14-2 14 0v14c0 2-14 2-14 0V5m0 7c0 2 14 2 14 0M5 5c0 2 14 2 14 0", knowledge: "M5 4h10a4 4 0 0 1 4 4v12H8a3 3 0 0 1-3-3V4m3 16a3 3 0 0 1 3-3h8", approvals: "M6 3h12v18H6zM9 8h6m-6 4h6m-6 4h3", overview: "M4 20V10h4v10m4 0V4h4v16m4 0H2" }; return <svg viewBox="0 0 24 24" aria-hidden="true"><path d={paths[name]} /></svg>; }
function displayCell(value: unknown): string { if (value == null) return "—"; if (typeof value === "object") return JSON.stringify(value); return String(value); }
function shortId(value: string): string { return value.length > 12 ? `${value.slice(0, 8)}…` : value; }
function formatTime(value: string): string { return new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(value)); }
function formatDate(value: string): string { return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value)); }
function loadSession(): Session | null { if (typeof window === "undefined") return null; try { const value = JSON.parse(sessionStorage.getItem("copilot.session") ?? "null") as Session | null; return value && value.expiresAt > Date.now() ? value : null; } catch { return null; } }
async function fileBase64(file: File): Promise<string> { const bytes = new Uint8Array(await file.arrayBuffer()); let binary = ""; const chunk = 0x8000; for (let index = 0; index < bytes.length; index += chunk) binary += String.fromCharCode(...bytes.subarray(index, index + chunk)); return btoa(binary); }
