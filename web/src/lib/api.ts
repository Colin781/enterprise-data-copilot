import type {
  AgentStep,
  AnalysisJob,
  Approval,
  DataSource,
  MetricDocument,
  Session,
  TokenResponse,
} from "./types";

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly traceId?: string,
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  token?: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`/api/platform${path}`, { ...init, headers, cache: "no-store" });
  if (response.status === 401 && token) window.dispatchEvent(new Event("copilot:unauthorized"));
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as Record<string, unknown>;
    throw new ApiClientError(
      typeof body.message === "string" ? body.message : "请求未完成，请稍后重试。",
      response.status,
      typeof body.code === "string" ? body.code : "REQUEST_FAILED",
      typeof body.trace_id === "string" ? body.trace_id : undefined,
    );
  }
  return (await response.json()) as T;
}

export const api = {
  async login(tenantSlug: string, email: string, password: string): Promise<Session> {
    const result = await request<TokenResponse>("/auth/login", undefined, {
      method: "POST",
      body: JSON.stringify({ tenant_slug: tenantSlug, email, password }),
    });
    return {
      accessToken: result.access_token,
      expiresAt: Date.now() + result.expires_in * 1000,
      userId: result.user_id,
      tenantId: result.tenant_id,
      roles: result.roles,
    };
  },
  dataSources: (token: string) => request<DataSource[]>("/data-sources", token),
  createDataSource: (token: string, body: Record<string, unknown>) =>
    request<DataSource>("/data-sources", token, { method: "POST", body: JSON.stringify(body) }),
  jobs: (token: string) => request<AnalysisJob[]>("/analysis/jobs", token),
  job: (token: string, id: string) => request<AnalysisJob>(`/analysis/jobs/${id}`, token),
  createJob: (token: string, dataSourceId: string, question: string) =>
    request<AnalysisJob>("/analysis/jobs", token, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ data_source_id: dataSourceId, question }),
    }),
  steps: (token: string, id: string) =>
    request<AgentStep[]>(`/analysis/jobs/${id}/steps`, token),
  approvals: (token: string) => request<Approval[]>("/approvals", token),
  decideApproval: (token: string, id: string, decision: "approve" | "reject", comment: string) =>
    request<Approval>(`/approvals/${id}/${decision}`, token, {
      method: "POST",
      body: JSON.stringify({ comment }),
    }),
  metricDocuments: (token: string) => request<MetricDocument[]>("/metric-documents", token),
  uploadMetricDocument: (token: string, body: Record<string, unknown>) =>
    request<MetricDocument>("/metric-documents", token, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

export function actionableError(error: unknown): string {
  if (!(error instanceof ApiClientError)) return "服务暂时不可用，请检查本地服务是否已启动。";
  const suggestions: Record<string, string> = {
    AUTHENTICATION_REQUIRED: "登录已过期，请重新登录。",
    ACCESS_DENIED: "当前账号没有执行此操作的权限。",
    DOCUMENT_INVALID: "请上传内容完整的 UTF-8 Markdown 或未加密 PDF。",
    DOCUMENT_LIMIT_EXCEEDED: "文档超过限制，请拆分后再上传。",
    IDEMPOTENCY_CONFLICT: "相同请求标识已用于其他内容，请重新提交。",
  };
  return suggestions[error.code] ?? `${error.message}${error.traceId ? `（追踪号 ${error.traceId}）` : ""}`;
}
