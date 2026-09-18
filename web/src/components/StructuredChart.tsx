"use client";

import { validateChartSpec } from "@/lib/chart-policy";

interface Props {
  spec: Record<string, unknown>;
  columns: string[];
  rows: Record<string, unknown>[];
}

const colors = ["#31c48d", "#6ea8fe", "#f5b94c"];

export function StructuredChart({ spec: rawSpec, columns, rows }: Props) {
  const spec = validateChartSpec(rawSpec, columns);
  if (!spec) {
    return <div className="empty-state compact">当前结果不适合绘制受支持的图表，请查看数据表。</div>;
  }
  const points = rows.slice(0, 30);
  const values = points.flatMap((row) => spec.series.map((key) => numberValue(row[key])));
  const max = Math.max(1, ...values);

  if (spec.type === "pie") {
    const key = spec.series[0];
    const pieValues = points.map((row) => Math.max(0, numberValue(row[key])));
    const total = pieValues.reduce((sum, value) => sum + value, 0);
    if (!total) return <div className="empty-state compact">没有可绘制的正数数据。</div>;
    const angles = pieValues.map((_, index) =>
      -Math.PI / 2 + pieValues.slice(0, index).reduce((sum, value) => sum + value, 0) / total * Math.PI * 2,
    );
    return (
      <figure className="chart-card" aria-label={spec.title}>
        <figcaption>{spec.title}</figcaption>
        <div className="pie-layout">
          <svg viewBox="0 0 320 320" role="img" aria-label={`${key} 饼图`}>
            {pieValues.map((value, index) => {
              const next = angles[index] + (value / total) * Math.PI * 2;
              const path = sectorPath(160, 160, 118, angles[index], next);
              return <path key={index} d={path} fill={colors[index % colors.length]} stroke="#0c1814" strokeWidth="3" />;
            })}
            <circle cx="160" cy="160" r="62" fill="#0c1814" />
            <text x="160" y="154" textAnchor="middle" className="chart-label">合计</text>
            <text x="160" y="180" textAnchor="middle" className="chart-total">{formatValue(total)}</text>
          </svg>
          <ul className="chart-legend">
            {points.map((row, index) => (
              <li key={index}>
                <span style={{ background: colors[index % colors.length] }} />
                <b>{String(row[spec.x!] ?? "—")}</b>
                <small>{formatValue(pieValues[index])}</small>
              </li>
            ))}
          </ul>
        </div>
      </figure>
    );
  }

  const width = 720;
  const height = 310;
  const left = 54;
  const top = 22;
  const plotWidth = width - left - 24;
  const plotHeight = height - top - 54;
  const xStep = plotWidth / Math.max(points.length, 1);

  return (
    <figure className="chart-card" aria-label={spec.title}>
      <figcaption>{spec.title}</figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${spec.type} chart`}>
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const y = top + plotHeight * (1 - ratio);
          return (
            <g key={ratio}>
              <line x1={left} x2={width - 24} y1={y} y2={y} className="grid-line" />
              <text x={left - 10} y={y + 4} textAnchor="end" className="axis-label">{formatValue(max * ratio)}</text>
            </g>
          );
        })}
        {spec.type === "bar" && points.flatMap((row, index) =>
          spec.series.map((key, seriesIndex) => {
            const value = numberValue(row[key]);
            const barWidth = Math.max(3, (xStep * 0.72) / spec.series.length);
            const barHeight = (value / max) * plotHeight;
            const x = left + index * xStep + xStep * 0.14 + seriesIndex * barWidth;
            return <rect key={`${index}-${key}`} x={x} y={top + plotHeight - barHeight} width={barWidth - 2} height={barHeight} rx="2" fill={colors[seriesIndex]} />;
          }),
        )}
        {spec.type === "line" && spec.series.map((key, seriesIndex) => {
          const linePoints = points.map((row, index) => {
            const x = left + index * xStep + xStep / 2;
            const y = top + plotHeight - (numberValue(row[key]) / max) * plotHeight;
            return `${x},${y}`;
          }).join(" ");
          return <polyline key={key} points={linePoints} fill="none" stroke={colors[seriesIndex]} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />;
        })}
        {points.map((row, index) => (
          <text key={index} x={left + index * xStep + xStep / 2} y={height - 22} textAnchor="middle" className="axis-label">
            {shortLabel(row[spec.x!])}
          </text>
        ))}
      </svg>
      <div className="inline-legend">
        {spec.series.map((key, index) => <span key={key}><i style={{ background: colors[index] }} />{key}</span>)}
      </div>
      {rows.length > 30 && <p className="chart-note">图表仅展示前 30 条，完整结果请查看数据表。</p>}
    </figure>
  );
}

function numberValue(value: unknown): number {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatValue(value: number): string {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 1, notation: Math.abs(value) >= 10_000 ? "compact" : "standard" }).format(value);
}

function shortLabel(value: unknown): string {
  const text = String(value ?? "—");
  return text.length > 10 ? `${text.slice(0, 9)}…` : text;
}

function sectorPath(cx: number, cy: number, radius: number, start: number, end: number): string {
  const startPoint = [cx + radius * Math.cos(start), cy + radius * Math.sin(start)];
  const endPoint = [cx + radius * Math.cos(end), cy + radius * Math.sin(end)];
  const largeArc = end - start > Math.PI ? 1 : 0;
  return `M ${cx} ${cy} L ${startPoint[0]} ${startPoint[1]} A ${radius} ${radius} 0 ${largeArc} 1 ${endPoint[0]} ${endPoint[1]} Z`;
}
