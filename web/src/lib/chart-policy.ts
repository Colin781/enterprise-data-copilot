import type { ChartSpec } from "./types";

const TYPES = new Set(["bar", "line", "pie", "table"]);

export function validateChartSpec(
  input: Record<string, unknown>,
  columns: string[],
): ChartSpec | null {
  const type = typeof input.type === "string" && TYPES.has(input.type) ? input.type : null;
  const title = typeof input.title === "string" ? input.title.slice(0, 160) : "分析结果";
  const x = typeof input.x === "string" && columns.includes(input.x) ? input.x : null;
  const series = Array.isArray(input.series)
    ? input.series.filter((item): item is string => typeof item === "string" && columns.includes(item)).slice(0, 3)
    : [];
  if (!type || type === "table") return null;
  if (!x || series.length === 0) return null;
  return { type: type as ChartSpec["type"], title, x, series };
}
