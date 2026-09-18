import assert from "node:assert/strict";
import test from "node:test";

import { validateChartSpec } from "../src/lib/chart-policy.ts";

test("accepts only the closed chart vocabulary and known result columns", () => {
  assert.deepEqual(
    validateChartSpec(
      { type: "line", title: "Quarterly sales", x: "quarter", series: ["revenue", "unknown"] },
      ["quarter", "revenue"],
    ),
    { type: "line", title: "Quarterly sales", x: "quarter", series: ["revenue"] },
  );
  assert.equal(
    validateChartSpec(
      { type: "javascript", title: "bad", x: "quarter", series: ["revenue"], code: "alert(1)" },
      ["quarter", "revenue"],
    ),
    null,
  );
  assert.equal(
    validateChartSpec(
      { type: "bar", title: "bad", x: "constructor", series: ["__proto__"] },
      ["quarter", "revenue"],
    ),
    null,
  );
});
