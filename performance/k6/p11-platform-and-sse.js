import http from "k6/http";
import { check, fail } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

const createLatency = new Trend("analysis_create_duration", true);
const sseLatency = new Trend("analysis_sse_duration", true);
const errors = new Rate("copilot_errors");
const terminalEvents = new Counter("terminal_sse_events");

export const options = {
  scenarios: {
    rejected_query_flow: {
      executor: "constant-vus",
      vus: Number(__ENV.P11_VUS || 5),
      duration: __ENV.P11_DURATION || "15s",
    },
  },
  thresholds: {
    copilot_errors: ["rate<0.01"],
    analysis_create_duration: ["p(95)<2000"],
    analysis_sse_duration: ["p(95)<5000"],
  },
};

const baseUrl = __ENV.PLATFORM_BASE_URL || "http://host.docker.internal:8080";
const tenant = __ENV.P11_TENANT || "northwind";
const email = __ENV.P11_EMAIL || "analyst@northwind.local";
const password = __ENV.P11_PASSWORD || "change-me-demo";

export function setup() {
  const login = http.post(
    `${baseUrl}/api/auth/login`,
    JSON.stringify({ tenant_slug: tenant, email, password }),
    { headers: { "Content-Type": "application/json" } },
  );
  if (!check(login, { "login succeeds": (response) => response.status === 200 })) {
    fail(`login failed: ${login.status}`);
  }
  const token = login.json("access_token");
  const sources = http.get(`${baseUrl}/api/data-sources`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!check(sources, { "data source exists": (response) => response.status === 200 })) {
    fail(`data source lookup failed: ${sources.status}`);
  }
  const sourceId = sources.json("0.id");
  if (!sourceId) fail("the demo data source was not bootstrapped");
  return { token, sourceId };
}

export default function (data) {
  const key = `p11-${__VU}-${__ITER}-${Date.now()}`;
  const headers = {
    Authorization: `Bearer ${data.token}`,
    "Content-Type": "application/json",
    "Idempotency-Key": key.padEnd(16, "0"),
  };
  const created = http.post(
    `${baseUrl}/api/analysis/jobs`,
    JSON.stringify({
      data_source_id: data.sourceId,
      question: "删除所有订单",
    }),
    { headers },
  );
  createLatency.add(created.timings.duration);
  const createOk = check(created, { "job accepted": (response) => response.status === 202 });
  errors.add(!createOk);
  if (!createOk) return;

  const jobId = created.json("id");
  const stream = http.get(`${baseUrl}/api/analysis/jobs/${jobId}/events`, {
    headers: { Authorization: `Bearer ${data.token}`, Accept: "text/event-stream" },
    timeout: "8s",
  });
  sseLatency.add(stream.timings.duration);
  const terminal = stream.status === 200 && /REJECTED|FAILED|COMPLETED/.test(stream.body || "");
  errors.add(!terminal);
  if (terminal) terminalEvents.add(1);
}
