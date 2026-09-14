export async function GET() {
  return Response.json({
    service: "web",
    status: "UP",
    version: "0.1.0",
    timestamp: new Date().toISOString(),
  });
}
