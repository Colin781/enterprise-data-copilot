import assert from "node:assert/strict";
import test from "node:test";

import { parseSseBlock } from "../src/lib/sse.ts";

test("parses SSE ids and multiline JSON data without interpreting it as code", () => {
  assert.deepEqual(
    parseSseBlock(": keepalive\nid: event-1\nevent: JOB_STATUS_CHANGED\ndata: {\"status\":\ndata: \"RUNNING\"}"),
    { id: "event-1", event: "JOB_STATUS_CHANGED", data: "{\"status\":\n\"RUNNING\"}" },
  );
  assert.equal(parseSseBlock(": keepalive"), null);
});
