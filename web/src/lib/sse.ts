import type { AnalysisEvent } from "./types";

export interface ParsedSseEvent {
  id?: string;
  event?: string;
  data: string;
}

export class SseHttpError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`SSE connection failed (${status})`);
    this.status = status;
  }
}

export function parseSseBlock(block: string): ParsedSseEvent | null {
  const parsed: ParsedSseEvent = { data: "" };
  const data: string[] = [];
  for (const line of block.replaceAll("\r", "").split("\n")) {
    if (!line || line.startsWith(":")) continue;
    const separator = line.indexOf(":");
    const field = separator < 0 ? line : line.slice(0, separator);
    const value = separator < 0 ? "" : line.slice(separator + 1).replace(/^ /, "");
    if (field === "id") parsed.id = value;
    if (field === "event") parsed.event = value;
    if (field === "data") data.push(value);
  }
  parsed.data = data.join("\n");
  return parsed.data ? parsed : null;
}

export async function streamJobEvents(
  token: string,
  jobId: string,
  onEvent: (event: AnalysisEvent) => void,
  signal: AbortSignal,
  lastEventId?: string,
): Promise<void> {
  const headers: Record<string, string> = {
    Accept: "text/event-stream",
    Authorization: `Bearer ${token}`,
  };
  if (lastEventId) headers["Last-Event-ID"] = lastEventId;
  const response = await fetch(`/api/platform/analysis/jobs/${jobId}/events`, {
    headers,
    signal,
    cache: "no-store",
  });
  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event("copilot:unauthorized"));
    }
    throw new SseHttpError(response.status);
  }
  if (!response.body) throw new Error("SSE response has no body");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (!signal.aborted) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done }).replaceAll("\r\n", "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const item = parseSseBlock(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      if (item) onEvent(JSON.parse(item.data) as AnalysisEvent);
      boundary = buffer.indexOf("\n\n");
    }
    if (done) return;
  }
}

export async function watchJobEvents(
  token: string,
  jobId: string,
  onEvent: (event: AnalysisEvent) => void,
  signal: AbortSignal,
  lastEventId?: string,
  retryDelayMs = 1_000,
): Promise<void> {
  let cursor = lastEventId;
  let failures = 0;
  while (!signal.aborted) {
    try {
      await streamJobEvents(token, jobId, (event) => {
        if (event.event_id) cursor = event.event_id;
        onEvent(event);
      }, signal, cursor);
      failures = 0;
    } catch (error) {
      if (signal.aborted) return;
      if (error instanceof SseHttpError && error.status >= 400 && error.status < 500
        && error.status !== 408 && error.status !== 429) throw error;
      failures += 1;
    }
    await retryAfter(Math.min(15_000, retryDelayMs * 2 ** Math.min(failures, 4)), signal);
  }
}

function retryAfter(delayMs: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) return Promise.resolve();
  return new Promise((resolve) => {
    const finish = () => { globalThis.clearTimeout(timer); signal.removeEventListener("abort", finish); resolve(); };
    const timer = globalThis.setTimeout(finish, delayMs);
    signal.addEventListener("abort", finish, { once: true });
  });
}
