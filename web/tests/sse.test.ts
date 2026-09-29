import assert from "node:assert/strict";
import test from "node:test";

import { parseSseBlock, watchJobEvents } from "../src/lib/sse.ts";

test("parses SSE ids and multiline JSON data without interpreting it as code", () => {
  assert.deepEqual(
    parseSseBlock(": keepalive\nid: event-1\nevent: JOB_STATUS_CHANGED\ndata: {\"status\":\ndata: \"RUNNING\"}"),
    { id: "event-1", event: "JOB_STATUS_CHANGED", data: "{\"status\":\n\"RUNNING\"}" },
  );
  assert.equal(parseSseBlock(": keepalive"), null);
});

test("reconnects after EOF with the last event id and stops when aborted", async () => {
  const originalFetch = globalThis.fetch;
  const headers: Array<string | null> = [];
  const controller = new AbortController();
  const received: string[] = [];
  globalThis.fetch = async (_input, init) => {
    const requestHeaders = init?.headers as Record<string, string>;
    headers.push(requestHeaders["Last-Event-ID"] ?? null);
    const id = headers.length === 1 ? "event-1" : "event-2";
    const data = JSON.stringify({ event_id: id, sequence: headers.length, job_id: "job-1", type: "JOB_STATUS_CHANGED", status: "RUNNING", occurred_at: "2026-01-01T00:00:00Z", payload: {} });
    return new Response(`id: ${id}\ndata: ${data}\n\n`, { headers: { "Content-Type": "text/event-stream" } });
  };
  try {
    await watchJobEvents("token", "job-1", (event) => {
      received.push(event.event_id);
      if (received.length === 2) controller.abort();
    }, controller.signal, undefined, 1);
    assert.deepEqual(received, ["event-1", "event-2"]);
    assert.deepEqual(headers, [null, "event-1"]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("does not retry an authorization failure", async () => {
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => { calls += 1; return new Response(null, { status: 401 }); };
  try {
    await assert.rejects(watchJobEvents("token", "job-1", () => {}, new AbortController().signal, undefined, 1));
    assert.equal(calls, 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("retries a transient connection failure before receiving an event", async () => {
  const originalFetch = globalThis.fetch;
  const controller = new AbortController();
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    if (calls === 1) throw new Error("connection reset");
    const event = { event_id: "event-1", sequence: 1, job_id: "job-1", type: "JOB_STATUS_CHANGED", status: "RUNNING", occurred_at: "2026-01-01T00:00:00Z", payload: {} };
    return new Response(`id: event-1\ndata: ${JSON.stringify(event)}\n\n`);
  };
  try {
    await watchJobEvents("token", "job-1", () => controller.abort(), controller.signal, undefined, 1);
    assert.equal(calls, 2);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
