"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useValuationFull } from "@/lib/useValuationFull";
import type { CountryRate, DcfResponse, DcfSensitivity, ValuationFullResponse } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { fmtNum, fmtPrice, fmtLarge, currencySymbol, fmtPctFromFraction } from "@/lib/format";
import { NaReason } from "@/components/markets/NaReason";
import { useRefreshNonce } from "@/lib/refresh";

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
  prov: string;
}[] = [
  { key: "wacc",           label: "WACC",            min: 0.04, max: 0.15, step: 0.0025, isPct: true,  isInt: false, prov: "inputs.wacc" },
  { key: "fcf_growth",     label: "FCF Growth",      min: 0,    max: 0.20, step: 0.005,  isPct: true,  isInt: false, prov: "inputs.fcfGrowth" },
  { key: "terminal_growth",label: "Terminal Growth", min: 0,    max: 0.05, step: 0.0025, isPct: true,  isInt: false, prov: "inputs.terminalGrowth" },
  { key: "stage1_years",   label: "Stage-1 Years",   min: 5,    max: 15,   step: 1,      isPct: false, isInt: true,  prov: "inputs.stage1Years" },
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
  return s != null && "fcfGrowthAxis" in s && Array.isArray((s as DcfSensitivity).fcfGrowthAxis);
}

// ── Main component ─────────────────────────────────────────────────────────
// Generic fallback, used only when the backend gives no per-ticker DCF assumptions.
const FALLBACK_PARAMS: Params = { wacc: 0.09, fcf_growth: 0.08, terminal_growth: 0.025, stage1_years: 10 };

/**
 * Pull the assumptions the valuation engine's own DCF model used for this ticker
 * (CAPM/WACC-derived discount rate, analyst-based FCF growth), so the panel starts
 * on the same DCF as the model grid instead of a hard-coded 9 % / 8 %.
 */
function defaultsFromFull(r: ValuationFullResponse): Params {
  const dcf = r.valuation.models.find((m) => m.model.startsWith("DCF"));
  const inp = (dcf?.detail as { inputs?: Partial<Record<string, number>> } | undefined)?.inputs;
  const num = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
  return {
    wacc: num(inp?.wacc) ? inp.wacc : num(r.valuation.wacc?.wacc) ? r.valuation.wacc.wacc : FALLBACK_PARAMS.wacc,
    fcf_growth: num(inp?.fcfGrowth) ? inp.fcfGrowth : FALLBACK_PARAMS.fcf_growth,
    terminal_growth: num(inp?.terminalGrowth) ? inp.terminalGrowth : FALLBACK_PARAMS.terminal_growth,
    stage1_years: num(inp?.stage1Years) ? inp.stage1Years : FALLBACK_PARAMS.stage1_years,
  };
}

export function DcfPanel({ tickers, sharedWacc = null }: { tickers: string[]; period?: string; sharedWacc?: number | null }) {
  const [selectedTicker, setSelectedTicker] = useState<string>(tickers[0] ?? "");
  const [params, setParams] = useState<Params>(FALLBACK_PARAMS);
  // Ticker the params were last seeded for; the DCF is only fetched once seeded.
  const [seededFor, setSeededFor] = useState<string>("");
  const [defaults, setDefaults] = useState<Params>(FALLBACK_PARAMS);
  const [defaultsFromBackend, setDefaultsFromBackend] = useState(false);
  const [data, setData] = useState<DcfResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [countryRates, setCountryRates] = useState<CountryRate[]>([]);
  const [selectedCountry, setSelectedCountry] = useState<string>("");
  const scope = useSourceScope(provOf(data));
  // Latest parent override, read when a ticker is (re)seeded so the reseed does not drop it.
  const sharedWaccRef = useRef(sharedWacc);
  sharedWaccRef.current = sharedWacc;

  // Load live risk-free rates from backend
  useEffect(() => {
    api.riskFreeRates().then((r) => {
      if (r.rates?.length) setCountryRates(r.rates);
    }).catch(() => {});
  }, []);

  // When country selection changes, update WACC
  function handleCountryChange(name: string) {
    setSelectedCountry(name);
    if (name) {
      const c = countryRates.find((r) => r.name === name);
      if (c) {
        // Cost of equity of a beta-1 stock = risk-free + ERP (not a WACC; used as the discount rate override)
        setParams((prev) => ({ ...prev, wacc: Math.round((c.riskFreeRate + c.erp) * 10000) / 10000 }));
      }
    } else {
      setParams((prev) => ({ ...prev, wacc: defaults.wacc }));
    }
  }

  // The Valuation tab's own /valuation/full result (one shared query, P3-34), so the panel's
  // defaults always match the model grid's DCF, also when a degraded bundle is replaced (P2-39).
  const full = useValuationFull(selectedTicker);

  useEffect(() => {
    setSelectedCountry("");
    setData(null); // the previous ticker's result must not stay on screen while this one loads
  }, [selectedTicker]);

  // Seed the sliders with the backend's own DCF assumptions once per ticker. A provisional seed (fallback
  // after a failed request, or a degraded bundle) is replaced once by the full result; later refetches
  // never reset the user's sliders.
  const seed = useRef<{ ticker: string; provisional: boolean }>({ ticker: "", provisional: true });
  useEffect(() => {
    if (!selectedTicker) return;
    const fresh = seed.current.ticker !== selectedTicker;
    if (full.data) {
      if (!fresh && !(seed.current.provisional && !full.data.degraded)) return;
      const d = defaultsFromFull(full.data);
      seed.current = { ticker: selectedTicker, provisional: !!full.data.degraded };
      setDefaults(d);
      setDefaultsFromBackend(true);
      setParams(sharedWaccRef.current != null ? { ...d, wacc: sharedWaccRef.current } : d);
      setSeededFor(selectedTicker);
    } else if (fresh && full.failureCount > 0) {
      seed.current = { ticker: selectedTicker, provisional: true };
      setDefaults(FALLBACK_PARAMS);
      setDefaultsFromBackend(false);
      setParams(sharedWaccRef.current != null ? { ...FALLBACK_PARAMS, wacc: sharedWaccRef.current } : FALLBACK_PARAMS);
      setSeededFor(selectedTicker);
    }
  }, [selectedTicker, full.data, full.failureCount]);

  // When the shared cost-of-equity override changes in the parent, apply it; clearing it
  // restores the ticker's own default WACC.
  useEffect(() => {
    if (seededFor !== selectedTicker) return;
    setParams((prev) => ({ ...prev, wacc: sharedWacc ?? defaults.wacc }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sharedWacc]);
  useEffect(() => {
    if (tickers.length && !tickers.includes(selectedTicker)) {
      setSelectedTicker(tickers[0]);
    }
  }, [tickers, selectedTicker]);

  // Debounced fetch – 500ms after any change (mirrors ValuationTab pattern)
  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    if (!selectedTicker || seededFor !== selectedTicker) return;
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
  }, [selectedTicker, seededFor, params, refreshNonce]);

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

        {/* Country / discount rate selector */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm text-text-secondary" title="Risk-free rate + equity risk premium, i.e. the cost of equity of a beta-1 stock. Not a WACC.">Cost of equity (β = 1)</span>
          <select
            value={selectedCountry}
            onChange={(e) => handleCountryChange(e.target.value)}
            className="rounded-md bg-surface-alt border border-border px-2 py-1 text-xs text-text-primary"
          >
            <option value="">{defaultsFromBackend ? "Ticker WACC (default)" : "Custom"}</option>
            {countryRates.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name} ({(c.riskFreeRate * 100).toFixed(2)}%)
              </option>
            ))}
          </select>
        </div>

        {/* Sliders */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {SLIDERS.map((s) => (
            <div key={s.key} data-prov={s.prov} data-prov-ctx={s.label}>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-text-secondary">{s.label}</span>
                <span className="font-mono">
                  {s.isInt
                    ? String(Math.round(params[s.key]))
                    : fmtPctFromFraction(params[s.key])}
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
          <p className="text-sm text-text-muted" data-prov="reason">
            <span className="font-semibold">n/a</span> — {data.reason ?? "insufficient data to compute a DCF"}
          </p>
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
    <div className="space-y-6" {...scope} data-prov-ctx={selectedTicker}>
      {controls}

      {/* ── KPI row ──────────────────────────────────────────────────────── */}
      <Card>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <KpiTile
            label="Intrinsic Value"
            value={data.intrinsicValue !== null ? fmtPrice(data.intrinsicValue, sym) : "n/a"}
            valueClass={data.intrinsicValue !== null ? "text-text-primary" : "text-text-muted"}
            title={data.intrinsicValue === null ? (data.reason ?? undefined) : undefined}
          />
          <KpiTile
            label="Spot Price"
            value={fmtPrice(data.spotPrice, sym)}
            valueClass="text-text-primary"
            prov="spotPrice"
          />
          <KpiTile
            label="Upside"
            value={upside !== null ? fmtPctFromFraction(upside) : "n/a"}
            valueClass={upside !== null ? upsideColor : "text-text-muted"}
            prov="upsidePct"
          />
          <KpiTile
            label={`${data.inputs.fcfPeriod ?? "TTM"} FCF`}
            value={data.inputs.ttmFcf !== null ? fmtLarge(data.inputs.ttmFcf) : "—"}
            valueClass="text-text-primary"
            prov="inputs.ttmFcf"
          />
          <KpiTile
            label="Net Debt"
            value={data.inputs.netDebt !== null ? fmtLarge(data.inputs.netDebt) : "—"}
            valueClass="text-text-primary"
            prov="inputs.netDebt"
          />
        </div>
        {data.intrinsicValue === null && (
          <p className="text-xs text-text-muted mt-3">
            n/a — {data.reason ?? "intrinsic value could not be computed"}
          </p>
        )}
        <p className="text-xs text-text-muted mt-3">as of {data.asOf}</p>
      </Card>

      {/* ── Scenario table ───────────────────────────────────────────────── */}
      {data.scenarios.length > 0 && (
        <Card data-prov="scenarios">
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
                        {fmtPctFromFraction(s.fcfGrowth)}
                      </td>
                      <td className="py-2 text-right font-mono text-text-secondary">
                        {fmtPctFromFraction(s.wacc)}
                      </td>
                      <td className="py-2 text-right font-mono text-text-primary">
                        {s.intrinsicValue !== null ? fmtPrice(s.intrinsicValue, sym) : <NaReason />}
                      </td>
                      <td className={`py-2 text-right font-mono ${uColor}`}>
                        {s.upsidePct !== null ? fmtPctFromFraction(s.upsidePct) : <NaReason />}
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
        <Card data-prov="sensitivity">
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
                  {fmtPctFromFraction(w, 1)}
                </div>
              ))}

              {/* Data rows */}
              {sensitivity.fcfGrowthAxis.map((g, ri) => (
                <>
                  {/* Row label */}
                  <div key={`label-${g}`} className="px-1 py-1 font-mono text-text-muted text-right self-center">
                    {fmtPctFromFraction(g, 1)}
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
                            ? `FCF ${fmtPctFromFraction(g, 1)}, WACC ${fmtPctFromFraction(w, 1)} → ${fmtPrice(cellVal, sym)}`
                            : "n/a"
                        }
                      >
                        {cellVal !== null ? fmtPrice(cellVal, sym) : <NaReason />}
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
  prov,
  title,
}: {
  label: string;
  value: string;
  valueClass: string;
  prov?: string;
  title?: string;
}) {
  return (
    <div className="space-y-0.5" data-prov={prov} data-prov-ctx={label} title={title}>
      <p className="text-xs text-text-muted">{label}</p>
      <p className={`text-base font-mono font-semibold ${valueClass}`}>{value}</p>
    </div>
  );
}
