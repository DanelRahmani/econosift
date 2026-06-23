"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { DcfResponse, DcfSensitivity } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";
import { fmtNum, fmtPct, fmtPrice, fmtLarge, currencySymbol } from "@/lib/format";

// ── Slider config ──────────────────────────────────────────────────────────
interface Params {
  wacc: number;
  fcf_growth: number;
  terminal_growth: number;
  stage1_years: number;
}

const SLIDERS: {
  key: keyof Params;
  label: string;
  min: number;
  max: number;
  step: number;
  isPct: boolean;
  isInt: boolean;
}[] = [
  { key: "wacc",           label: "WACC",            min: 0.04, max: 0.15, step: 0.0025, isPct: true,  isInt: false },
  { key: "fcf_growth",     label: "FCF Growth",      min: 0,    max: 0.20, step: 0.005,  isPct: true,  isInt: false },
  { key: "terminal_growth",label: "Terminal Growth", min: 0,    max: 0.05, step: 0.0025, isPct: true,  isInt: false },
  { key: "stage1_years",   label: "Stage-1 Years",   min: 5,    max: 15,   step: 1,      isPct: false, isInt: true  },
];

// ── Sensitivity heatmap helpers ───────────────────────────────────────────
function heatColor(value: number | null, spot: number | null): string {
  if (value === null || spot === null || spot === 0) return "rgba(128,128,128,0.15)";
  const ratio = value / spot;
  const clamped = Math.max(0.5, Math.min(1.5, ratio));
  // Map 0.5..1..1.5 → red..white..green
  if (clamped <= 1) {
    // red (#c4394a) to white, t=0 (clamped=0.5) → red, t=1 (clamped=1) → white
    const t = (clamped - 0.5) / 0.5;
    const r = Math.round(196 + (255 - 196) * t);
    const g = Math.round(57  + (255 - 57)  * t);
    const b = Math.round(74  + (255 - 74)  * t);
    return `rgba(${r},${g},${b},0.75)`;
  } else {
    // white to green (#16a34a), t=0 (clamped=1) → white, t=1 (clamped=1.5) → green
    const t = (clamped - 1) / 0.5;
    const r = Math.round(255 + (22  - 255) * t);
    const g = Math.round(255 + (163 - 255) * t);
    const b = Math.round(255 + (74  - 255) * t);
    return `rgba(${r},${g},${b},0.75)`;
  }
}

function isSensitivityFull(s: DcfResponse["sensitivity"]): s is DcfSensitivity {
  return "fcfGrowthAxis" in s && Array.isArray((s as DcfSensitivity).fcfGrowthAxis);
}

// ── Main component ─────────────────────────────────────────────────────────
export function DcfPanel({ tickers, period }: { tickers: string[]; period?: string }) {
  const [selectedTicker, setSelectedTicker] = useState<string>(tickers[0] ?? "");
  const [params, setParams] = useState<Params>({
    wacc: 0.09,
    fcf_growth: 0.08,
    terminal_growth: 0.025,
    stage1_years: 10,
  });
  const [data, setData] = useState<DcfResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  // Keep selectedTicker in sync when tickers prop changes
  useEffect(() => {
    if (tickers.length && !tickers.includes(selectedTicker)) {
      setSelectedTicker(tickers[0]);
    }
  }, [tickers, selectedTicker]);

  // Debounced fetch – 500ms after any change (mirrors ValuationTab pattern)
  useEffect(() => {
    if (!selectedTicker) return;
    const t = setTimeout(async () => {
      setLoading(true);
      setError(false);
      try {
        const r = await api.dcf(selectedTicker, {
          fcf_growth: params.fcf_growth,
          terminal_growth: params.terminal_growth,
          wacc: params.wacc,
          stage1_years: params.stage1_years,
        });
        setData(r);
      } catch {
        setError(true);
        setData(null);
      } finally {
        setLoading(false);
      }
    }, 500);
    return () => clearTimeout(t);
  }, [selectedTicker, params]);

  // ── Early states ──────────────────────────────────────────────────────────
  if (!tickers.length) {
    return (
      <Card>
        <p className="text-text-muted text-sm">Add a ticker to compute DCF valuation.</p>
      </Card>
    );
  }

  const sym = currencySymbol(data?.currency);

  // ── Shared: ticker selector + sliders ────────────────────────────────────
  const controls = (
    <Card>
      <div className="space-y-4">
        {/* Ticker selector */}
        {tickers.length > 1 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-text-secondary">Ticker</span>
            <select
              value={selectedTicker}
              onChange={(e) => setSelectedTicker(e.target.value)}
              className="rounded-md bg-surface-alt border border-border px-2 py-1 text-xs text-text-primary"
            >
              {tickers.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
        )}

        {/* Sliders */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {SLIDERS.map((s) => (
            <div key={s.key}>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-text-secondary">{s.label}</span>
                <span className="font-mono">
                  {s.isInt
                    ? String(Math.round(params[s.key]))
                    : fmtPct(params[s.key] * 100)}
                </span>
              </div>
              <input
                type="range"
                min={s.min}
                max={s.max}
                step={s.step}
                value={params[s.key]}
                onChange={(e) =>
                  setParams((p) => ({
                    ...p,
                    [s.key]: s.isInt
                      ? parseInt(e.target.value, 10)
                      : parseFloat(e.target.value),
                  }))
                }
                className="w-full accent-accent"
              />
            </div>
          ))}
        </div>
      </div>
    </Card>
  );

  // ── Loading (first load) ──────────────────────────────────────────────────
  if (loading && !data) {
    return (
      <div className="space-y-6">
        {controls}
        <Skeleton className="h-40" />
      </div>
    );
  }

  // ── Fetch error ───────────────────────────────────────────────────────────
  if (error && !data) {
    return (
      <div className="space-y-6">
        {controls}
        <Card>
          <p className="text-text-muted text-sm">DCF data unavailable. Please try again.</p>
        </Card>
      </div>
    );
  }

  // ── No data yet ───────────────────────────────────────────────────────────
  if (!data) {
    return <div className="space-y-6">{controls}</div>;
  }

  // ── Locked state ──────────────────────────────────────────────────────────
  if (data.locked) {
    return (
      <div className="space-y-6">
        {controls}
        <Card>
          <p className="text-sm font-semibold text-text-primary mb-1">DCF unavailable</p>
          <p className="text-sm text-text-muted">{data.reason ?? "Insufficient data to compute DCF."}</p>
          {data.asOf && (
            <p className="text-xs text-text-muted mt-3">as of {data.asOf}</p>
          )}
        </Card>
      </div>
    );
  }

  // ── Full render ───────────────────────────────────────────────────────────
  const upside = data.upsidePct;
  const upsideColor =
    upside === null ? "text-text-secondary"
    : upside > 0    ? "text-success"
    : "text-danger";

  const sensitivity = isSensitivityFull(data.sensitivity) ? data.sensitivity : null;

  return (
    <div className="space-y-6">
      {controls}

      {/* ── KPI row ──────────────────────────────────────────────────────── */}
      <Card>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <KpiTile
            label="Intrinsic Value"
            value={fmtPrice(data.intrinsicValue, sym)}
            valueClass="text-text-primary"
          />
          <KpiTile
            label="Spot Price"
            value={fmtPrice(data.spotPrice, sym)}
            valueClass="text-text-primary"
          />
          <KpiTile
            label="Upside"
            value={upside !== null ? fmtPct(upside * 100) : "—"}
            valueClass={upsideColor}
          />
          <KpiTile
            label="TTM FCF"
            value={data.inputs.ttmFcf !== null ? fmtLarge(data.inputs.ttmFcf) : "—"}
            valueClass="text-text-primary"
          />
          <KpiTile
            label="Net Debt"
            value={data.inputs.netDebt !== null ? fmtLarge(data.inputs.netDebt) : "—"}
            valueClass="text-text-primary"
          />
        </div>
        <p className="text-xs text-text-muted mt-3">as of {data.asOf}</p>
      </Card>

      {/* ── Scenario table ───────────────────────────────────────────────── */}
      {data.scenarios.length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold text-text-primary mb-3">Scenarios</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-text-muted text-xs border-b border-border">
                  <th className="text-left pb-2 font-medium">Scenario</th>
                  <th className="text-right pb-2 font-medium">FCF Growth</th>
                  <th className="text-right pb-2 font-medium">WACC</th>
                  <th className="text-right pb-2 font-medium">Intrinsic Value</th>
                  <th className="text-right pb-2 font-medium">Upside</th>
                </tr>
              </thead>
              <tbody>
                {data.scenarios.map((s) => {
                  const isBase = s.scenario === "Base";
                  const uColor =
                    s.upsidePct === null ? "text-text-secondary"
                    : s.upsidePct > 0    ? "text-success"
                    : "text-danger";
                  return (
                    <tr
                      key={s.scenario}
                      className={`border-b border-border/50 last:border-0 ${isBase ? "bg-surface-alt" : ""}`}
                    >
                      <td className="py-2 font-medium text-text-primary">{s.scenario}</td>
                      <td className="py-2 text-right font-mono text-text-secondary">
                        {fmtPct(s.fcfGrowth * 100)}
                      </td>
                      <td className="py-2 text-right font-mono text-text-secondary">
                        {fmtPct(s.wacc * 100)}
                      </td>
                      <td className="py-2 text-right font-mono text-text-primary">
                        {fmtPrice(s.intrinsicValue, sym)}
                      </td>
                      <td className={`py-2 text-right font-mono ${uColor}`}>
                        {s.upsidePct !== null ? fmtPct(s.upsidePct * 100) : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* ── Sensitivity heatmap ──────────────────────────────────────────── */}
      {sensitivity && (
        <Card>
          <h3 className="text-sm font-semibold text-text-primary mb-1">Sensitivity Analysis</h3>
          <p className="text-xs text-text-muted mb-4">
            Intrinsic value per share — rows: FCF growth, cols: WACC.
          </p>
          <div className="overflow-x-auto">
            {/* CSS grid: 1 label col + N wacc cols */}
            <div
              className="inline-grid gap-px text-xs"
              style={{ gridTemplateColumns: `auto repeat(${sensitivity.waccAxis.length}, minmax(52px, 1fr))` }}
            >
              {/* Top-left corner */}
              <div className="px-1 py-1 text-text-muted font-medium text-center">FCF \ WACC</div>

              {/* WACC header row */}
              {sensitivity.waccAxis.map((w) => (
                <div key={w} className="px-1 py-1 font-mono text-text-muted text-center">
                  {fmtPct(w * 100, 1)}
                </div>
              ))}

              {/* Data rows */}
              {sensitivity.fcfGrowthAxis.map((g, ri) => (
                <>
                  {/* Row label */}
                  <div key={`label-${g}`} className="px-1 py-1 font-mono text-text-muted text-right self-center">
                    {fmtPct(g * 100, 1)}
                  </div>

                  {/* Cells */}
                  {sensitivity.waccAxis.map((w, ci) => {
                    const cellVal = sensitivity.grid[ri]?.[ci] ?? null;
                    const bg = heatColor(cellVal, data.spotPrice);
                    return (
                      <div
                        key={`${g}-${w}`}
                        className="px-1 py-1 font-mono text-center rounded-sm"
                        style={{ backgroundColor: bg }}
                        title={
                          cellVal !== null
                            ? `FCF ${fmtPct(g * 100, 1)}, WACC ${fmtPct(w * 100, 1)} → ${fmtPrice(cellVal, sym)}`
                            : "—"
                        }
                      >
                        {cellVal !== null ? fmtPrice(cellVal, sym) : <span className="text-text-muted">—</span>}
                      </div>
                    );
                  })}
                </>
              ))}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

// ── Helper: KPI tile ──────────────────────────────────────────────────────
function KpiTile({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass: string;
}) {
  return (
    <div className="space-y-0.5">
      <p className="text-xs text-text-muted">{label}</p>
      <p className={`text-base font-mono font-semibold ${valueClass}`}>{value}</p>
    </div>
  );
}
