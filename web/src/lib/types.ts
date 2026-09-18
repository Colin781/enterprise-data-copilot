export type Role = "ADMIN" | "ANALYST" | "VIEWER";

export type JobStatus =
  | "CREATED"
  | "PLANNING"
  | "VALIDATING"
  | "WAITING_APPROVAL"
  | "RUNNING"
  | "COMPLETED"
  | "REJECTED"
  | "FAILED"
  | "CANCELLED";

export interface Session {
  accessToken: string;
  expiresAt: number;
  userId: string;
  tenantId: string;
  roles: Role[];
}

export interface TokenResponse {
  access_token: string;
  expires_in: number;
  user_id: string;
  tenant_id: string;
  roles: Role[];
}

export interface DataSource {
  id: string;
  name: string;
  source_type: "POSTGRESQL";
  allowed_schema: string;
  enabled: boolean;
  version: number;
}

export interface Citation {
  document_id?: string;
  document_title?: string;
  document_version?: number;
  section_key?: string;
  section_title?: string;
  source_locator?: string;
}

export interface ChartSpec {
  type: "bar" | "line" | "pie" | "table";
  title: string;
  x?: string | null;
  series: string[];
}

export interface AnalysisJob {
  id: string;
  data_source_id: string;
  question: string;
  status: JobStatus;
  trace_id: string;
  created_at: string;
  updated_at: string;
  finished_at?: string | null;
  version: number;
  workflow_thread_id?: string | null;
  generated_sql?: string | null;
  answer?: string | null;
  error_code?: string | null;
  columns: string[];
  rows: Record<string, unknown>[];
  chart: Record<string, unknown>;
  citations: Citation[];
}

export interface AgentStep {
  id: string;
  step_name: string;
  status: "SUCCEEDED" | "FAILED" | "WAITING";
  attempt: number;
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  duration_ms: number;
  error_code?: string | null;
  created_at: string;
}

export interface Approval {
  id: string;
  analysis_job_id: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  reason: string;
  decided_by?: string | null;
  decision_comment?: string | null;
  created_at: string;
  decided_at?: string | null;
  version: number;
}

export interface MetricDocument {
  id: string;
  tenant_id: string;
  title: string;
  version: number;
  status: "ACTIVE" | "SUPERSEDED";
  source_type: "MARKDOWN" | "PDF";
  source_name: string;
  content_sha256: string;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface AnalysisEvent {
  event_id: string;
  sequence: number;
  job_id: string;
  type: string;
  status: JobStatus;
  occurred_at: string;
  payload: Record<string, unknown>;
}
