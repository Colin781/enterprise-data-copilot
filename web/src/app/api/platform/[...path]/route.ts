import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const platformBase = process.env.PLATFORM_API_URL ?? "http://localhost:8080";
const forwardedHeaders = ["authorization", "content-type", "idempotency-key", "last-event-id"];

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (!path.length || path.some((part) => !part || part === "." || part === "..")) {
    return Response.json({ code: "INVALID_PROXY_PATH", message: "Invalid API path." }, { status: 400 });
  }
  const target = new URL(`/api/${path.map(encodeURIComponent).join("/")}`, platformBase);
  target.search = request.nextUrl.search;
  const headers = new Headers();
  for (const name of forwardedHeaders) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const upstream = await fetch(target, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    cache: "no-store",
    signal: request.signal,
  });
  const responseHeaders = new Headers();
  for (const name of ["content-type", "cache-control", "location"]) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  responseHeaders.set("X-Content-Type-Options", "nosniff");
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

export const GET = proxy;
export const POST = proxy;
