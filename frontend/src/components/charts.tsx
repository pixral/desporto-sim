// Small hand-written SVG charts. One y-axis per chart, thin marks, hairline grid,
// crosshair/per-mark tooltips, legend for >= 2 series, text in ink tokens (never series colour).

import { useEffect, useRef, useState, type ReactNode } from "react";
import { t } from "../i18n";

function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(600);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(200, Math.floor(e.contentRect.width))));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

function niceTicks(lo: number, hi: number, count = 4): number[] {
  if (lo === hi) {
    lo -= 1;
    hi += 1;
  }
  const span = hi - lo;
  const raw = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count + 0.5) ?? 10 * mag;
  const start = Math.floor(lo / step) * step;
  const out: number[] = [];
  for (let v = start; v <= hi + step * 0.5; v += step) out.push(Math.round(v * 1e6) / 1e6);
  return out;
}

export interface Series {
  key: string;
  label: string;
  color: string;
  values: (number | null)[];
}

export function Legend({ series }: { series: { label: string; color: string }[] }) {
  if (series.length < 2) return null;
  return (
    <div className="legend">
      {series.map((s) => (
        <span className="key" key={s.label}>
          <span className="swatch" style={{ background: s.color }} />
          {s.label}
        </span>
      ))}
    </div>
  );
}

export function LineChart({ x, series, height = 220, format, zeroLine = false }: {
  x: string[];
  series: Series[];
  height?: number;
  format: (v: number) => string;
  zeroLine?: boolean;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const m = { l: 58, r: 14, t: 10, b: 24 };
  const iw = width - m.l - m.r;
  const ih = height - m.t - m.b;
  const all = series.flatMap((s) => s.values.filter((v): v is number => v !== null));
  if (zeroLine) all.push(0);
  const ticks = niceTicks(all.length ? Math.min(...all) : 0, all.length ? Math.max(...all) : 1);
  const lo = ticks[0];
  const hi = ticks[ticks.length - 1];
  const n = x.length;
  const sx = (i: number) => m.l + (n <= 1 ? iw / 2 : (i / (n - 1)) * iw);
  const sy = (v: number) => m.t + ih - ((v - lo) / (hi - lo || 1)) * ih;
  const xTicks = n <= 1 ? [0] : Array.from({ length: Math.min(6, n) }, (_, k) => Math.round((k / (Math.min(6, n) - 1)) * (n - 1)));

  const onMove = (e: React.MouseEvent<SVGRectElement>) => {
    const rect = (e.target as SVGRectElement).getBoundingClientRect();
    const px = e.clientX - rect.left;
    const i = Math.round((px / rect.width) * (n - 1));
    setHover(Math.max(0, Math.min(n - 1, i)));
  };

  return (
    <div className="chart" ref={ref}>
      <Legend series={series} />
      <svg height={height} role="img" aria-label={series.map((s) => s.label).join(", ")}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={m.l} x2={width - m.r} y1={sy(t)} y2={sy(t)} stroke={t === 0 && zeroLine ? "var(--axis)" : "var(--grid)"} strokeWidth={1} />
            <text x={m.l - 8} y={sy(t)} className="axis-text" textAnchor="end" dominantBaseline="middle">
              {format(t)}
            </text>
          </g>
        ))}
        {xTicks.map((i) => (
          <text key={i} x={sx(i)} y={height - 6} className="axis-text" textAnchor="middle">
            {x[i]}
          </text>
        ))}
        {series.map((s) => {
          let d = "";
          s.values.forEach((v, i) => {
            if (v === null) return;
            d += `${d ? "L" : "M"}${sx(i).toFixed(1)},${sy(v).toFixed(1)}`;
          });
          return <path key={s.key} d={d} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />;
        })}
        {hover !== null && (
          <g>
            <line x1={sx(hover)} x2={sx(hover)} y1={m.t} y2={m.t + ih} stroke="var(--axis)" strokeWidth={1} />
            {series.map((s) =>
              s.values[hover] === null ? null : (
                <circle key={s.key} cx={sx(hover)} cy={sy(s.values[hover] as number)} r={4} fill={s.color} stroke="var(--panel)" strokeWidth={2} />
              ),
            )}
          </g>
        )}
        <rect x={m.l} y={m.t} width={iw} height={ih} fill="transparent" onMouseMove={onMove} onMouseLeave={() => setHover(null)} />
      </svg>
      {hover !== null && (
        <div className="chart-tip" style={{ left: sx(hover), top: m.t + 34 }}>
          <div className="muted">{x[hover]}</div>
          {series.map((s) =>
            s.values[hover] === null ? null : (
              <div className="row" key={s.key}>
                <span className="swatch" style={{ display: "inline-block", width: 10, height: 3, background: s.color }} />
                {s.label}: <b>{format(s.values[hover] as number)}</b>
              </div>
            ),
          )}
        </div>
      )}
    </div>
  );
}

export interface Column {
  label: string;
  value: number;
  detail?: ReactNode;
}

export function ColumnChart({ data, height = 220, format }: { data: Column[]; height?: number; format: (v: number) => string }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const m = { l: 58, r: 10, t: 12, b: 24 };
  const iw = width - m.l - m.r;
  const ih = height - m.t - m.b;
  const vals = data.map((d) => d.value).concat(0);
  const ticks = niceTicks(Math.min(...vals), Math.max(...vals));
  const lo = ticks[0];
  const hi = ticks[ticks.length - 1];
  const sy = (v: number) => m.t + ih - ((v - lo) / (hi - lo || 1)) * ih;
  const band = iw / Math.max(1, data.length);
  const bw = Math.min(24, band * 0.6);
  const r = Math.min(4, bw / 2);
  const every = Math.ceil(data.length / 8);
  return (
    <div className="chart" ref={ref}>
      <svg height={height} role="img" aria-label={t("Signed columns")}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={m.l} x2={width - m.r} y1={sy(t)} y2={sy(t)} stroke={t === 0 ? "var(--axis)" : "var(--grid)"} strokeWidth={1} />
            <text x={m.l - 8} y={sy(t)} className="axis-text" textAnchor="end" dominantBaseline="middle">
              {format(t)}
            </text>
          </g>
        ))}
        {data.map((d, i) => {
          const cx = m.l + band * i + band / 2;
          const x0 = cx - bw / 2;
          const y0 = sy(0);
          const y1 = sy(d.value);
          const pos = d.value >= 0;
          const h = Math.abs(y1 - y0);
          const rr = Math.min(r, h);
          const path = pos
            ? `M${x0},${y0} L${x0},${y1 + rr} Q${x0},${y1} ${x0 + rr},${y1} L${x0 + bw - rr},${y1} Q${x0 + bw},${y1} ${x0 + bw},${y1 + rr} L${x0 + bw},${y0} Z`
            : `M${x0},${y0} L${x0},${y1 - rr} Q${x0},${y1} ${x0 + rr},${y1} L${x0 + bw - rr},${y1} Q${x0 + bw},${y1} ${x0 + bw},${y1 - rr} L${x0 + bw},${y0} Z`;
          return (
            <g key={d.label} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={m.l + band * i} y={m.t} width={band} height={ih} fill="transparent" />
              <path d={path} fill={pos ? "var(--div-pos)" : "var(--div-neg)"} opacity={hover === null || hover === i ? 1 : 0.55} />
              {i % every === 0 && (
                <text x={cx} y={height - 6} className="axis-text" textAnchor="middle">
                  {d.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {hover !== null && data[hover] && (
        <div className="chart-tip" style={{ left: m.l + band * hover + band / 2, top: Math.min(sy(data[hover].value), sy(0)) }}>
          <div className="muted">{data[hover].label}</div>
          <b>{format(data[hover].value)}</b>
          {data[hover].detail}
        </div>
      )}
    </div>
  );
}

export function Sparkline({ values, width = 90, height = 22, color = "var(--muted)", dot = "var(--accent)" }: {
  values: number[];
  width?: number;
  height?: number;
  color?: string;
  dot?: string;
}) {
  if (values.length < 2) return null;
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pts = values.map((v, i) => [(i / (values.length - 1)) * (width - 4) + 2, height - 2 - ((v - lo) / (hi - lo || 1)) * (height - 4)]);
  const last = pts[pts.length - 1];
  return (
    <svg width={width} height={height} aria-hidden>
      <polyline points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke={color} strokeWidth={1.5} />
      <circle cx={last[0]} cy={last[1]} r={2.5} fill={dot} />
    </svg>
  );
}
