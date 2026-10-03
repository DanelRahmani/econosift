"use client";

import { useState, useEffect } from "react";
import {
  ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Bar, Legend,
} from "recharts";
import { Card, chartTooltipStyle, chartPalette } from "@/components/ui";
import { useTheme } from "@/components/ThemeProvider";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { api } from "@/lib/api";
import type {
  TechnicalsResponse, BollingerPoint, IchimokuPoint, FibLevel, PivotSet,
} from "@/lib/types";
import { useRefreshNonce } from "@/lib/refresh";

const PERIODS = ["1mo", "3mo", "6mo", "1y", "2y"] as const;
type Period = (typeof PERIODS)[number];

type Overlay = "bollinger" | "ichimoku" | "fibonacci" | "pivots";

const OVERLAY_LABELS: Record<Overlay, string> = {
  bollinger: "Bollinger Bands",
  ichimoku: "Ichimoku",
  fibonacci: "Fibonacci",
  pivots: "Pivot Points",
};

const FIB_COLORS = ["#94a3b8", "#f59e0b", "#10b981", "#3b82f6", "#8b5cf6", "#ef4444", "#94a3b8"];

function fmt(v: number | null | undefined, dec = 2): string {
  if (v == null) return "—";
  return v.toFixed(dec);
}

function trendBadge(trend: string) {
  if (trend === "Bullish") return "text-success bg-success/10 border-success/30";
  if (trend === "Bearish") return "text-danger bg-danger/10 border-danger/30";
  return "text-text-muted bg-surface-alt border-border";
}

function rsiBadge(rsi: number | null) {
  if (rsi == null) return "text-text-muted bg-surface-alt border-border";
  if (rsi > 70) return "text-danger bg-danger/10 border-danger/30";
  if (rsi < 30) return "text-success bg-success/10 border-success/30";
  return "text-text-secondary bg-surface-alt border-border";
}

// ---- Small sub-chart -------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyRow = Record<string, any>;

function SubChart({
  data,
  dataKey,
  label,
  refLines = [],
  theme,
  formatter,
}: {
  data: AnyRow[];
  dataKey: string | string[];
  label: string;
  refLines?: { y: number; color: string; dash?: string }[];
  theme: "light" | "dark";
  formatter?: (v: number) => string;
}) {
  const pal = chartPalette(theme);
  const tt = chartTooltipStyle(theme);
  const keys = Array.isArray(dataKey) ? dataKey : [dataKey];
  const COLORS = ["#3b82f6", "#f59e0b", "#10b981", "#ef4444"];

  return (
    <div>
      <p className="text-xs font-medium text-text-muted mb-1">{label}</p>
      <div className="h-28 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data}>
            <CartesianGrid stroke={pal.grid} strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fill: pal.axis, fontSize: 10 }} minTickGap={60} />
            <YAxis tick={{ fill: pal.axis, fontSize: 10 }} width={45} domain={["auto", "auto"]} />
            <Tooltip
              {...tt}
              formatter={(v: number) => formatter ? formatter(v) : v?.toFixed(3)}
            />
            {refLines.map((rl, i) => (
              <ReferenceLine key={i} y={rl.y} stroke={rl.color} strokeDasharray={rl.dash ?? "3 3"} strokeOpacity={0.7} />
            ))}
            {keys.map((k, i) => (
              <Line
                key={k}
                type="monotone"
                dataKey={k}
                stroke={COLORS[i % COLORS.length]}
                strokeWidth={1.5}
                dot={false}
                connectNulls
                name={k}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function MACDChart({ data, theme }: { data: AnyRow[]; theme: "light" | "dark" }) {
  const pal = chartPalette(theme);
  const tt = chartTooltipStyle(theme);
  return (
    <div>
      <p className="text-xs font-medium text-text-muted mb-1">MACD (12,26,9)</p>
      <div className="h-28 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data}>
            <CartesianGrid stroke={pal.grid} strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fill: pal.axis, fontSize: 10 }} minTickGap={60} />
            <YAxis tick={{ fill: pal.axis, fontSize: 10 }} width={45} domain={["auto", "auto"]} />
            <Tooltip {...tt} formatter={(v: number) => v?.toFixed(4)} />
            <ReferenceLine y={0} stroke={pal.axis} strokeOpacity={0.4} />
            <Bar dataKey="hist" fill="#6366f1" opacity={0.5} name="Histogram" />
            <Line type="monotone" dataKey="macd" stroke="#3b82f6" strokeWidth={1.5} dot={false} connectNulls name="MACD" />
            <Line type="monotone" dataKey="signal" stroke="#f59e0b" strokeWidth={1.5} dot={false} connectNulls name="Signal" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ---- Main component --------------------------------------------------------

export function TechnicalsTab({ ticker }: { ticker: string }) {
  const { theme } = useTheme();
  const pal = chartPalette(theme);
  const tt = chartTooltipStyle(theme);

  const [period, setPeriod] = useState<Period>("1y");
  const [activeOverlays, setActiveOverlays] = useState<Set<Overlay>>(new Set(["bollinger"]));
  const [data, setData] = useState<TechnicalsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSubCharts, setShowSubCharts] = useState(true);
  const scope = useSourceScope(provOf(data));

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    setError(null);
    api
      .fetchTechnicals(ticker, period)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [ticker, period, refreshNonce]);

  function toggleOverlay(o: Overlay) {
    setActiveOverlays((prev) => {
      const next = new Set(prev);
      next.has(o) ? next.delete(o) : next.add(o);
      return next;
    });
  }

  if (loading) return <div className="text-text-muted text-sm py-8 text-center">Loading technical indicators…</div>;
  if (error) return <div className="text-danger text-sm py-4">{error}</div>;
  if (!data) return null;

  const { summary, prices, bollinger, ichimoku, macd, rsi, stochRsi, williamsR, obv, cmf, atr, fibLevels, pivotPoints } = data;

  // ---- Build main chart data ------------------------------------------------
  // Merge price + overlay series by date
  const bbMap = new Map<string, BollingerPoint>(bollinger.map((b) => [b.date, b]));
  const ichiMap = new Map<string, IchimokuPoint>(ichimoku.map((i) => [i.date, i]));

  const chartData = prices.map((p) => {
    const entry: Record<string, string | number | null> = {
      date: p.date, close: p.close, open: p.open, high: p.high, low: p.low,
    };
    if (activeOverlays.has("bollinger")) {
      const bb = bbMap.get(p.date);
      if (bb) { entry.bbUpper = bb.upper; entry.bbMid = bb.mid; entry.bbLower = bb.lower; }
    }
    if (activeOverlays.has("ichimoku")) {
      const ic = ichiMap.get(p.date);
      if (ic) {
        entry.tenkan = ic.tenkan;
        entry.kijun = ic.kijun;
        entry.senkouA = ic.senkouA;
        entry.senkouB = ic.senkouB;
      }
    }
    return entry;
  });
  // Forward cloud: the 26 projected Senkou bars dated after the last price (P3-29)
  if (activeOverlays.has("ichimoku") && prices.length > 0) {
    const lastDate = prices[prices.length - 1].date;
    for (const ic of ichimoku) {
      if (ic.date > lastDate) chartData.push({ date: ic.date, senkouA: ic.senkouA, senkouB: ic.senkouB });
    }
  }

  // Determine YAxis domain from price + overlays for clean display
  const allPriceVals = chartData.flatMap((d) => {
    const vals = [d.close, d.bbUpper, d.bbLower, d.senkouA, d.senkouB, d.tenkan, d.kijun].filter(
      (v): v is number => typeof v === "number"
    );
    return vals;
  });
  const yMin = allPriceVals.length ? Math.floor(Math.min(...allPriceVals) * 0.97) : "auto";
  const yMax = allPriceVals.length ? Math.ceil(Math.max(...allPriceVals) * 1.03) : "auto";

  // Pivot reference lines for selected timeframe
  const pivotSet: PivotSet | undefined = pivotPoints?.daily;
  const pivotColors: Record<string, string> = {
    p: "#94a3b8", r1: "#22c55e", r2: "#16a34a", s1: "#ef4444", s2: "#b91c1c",
  };

  return (
    <div className="space-y-6" {...scope} data-prov-ctx={ticker}>
      {/* ---- Summary KPIs ---- */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <div className="rounded-lg border border-border bg-surface-alt p-3" data-prov="summary.trend" data-prov-ctx="Trend">
          <p className="text-xs text-text-muted mb-1">Trend (SMA50 vs 200)</p>
          <span className={`text-sm font-semibold px-2 py-0.5 rounded border ${trendBadge(summary.trend)}`}>
            {summary.trend}
          </span>
        </div>
        <div className="rounded-lg border border-border bg-surface-alt p-3" data-prov="summary.rsi" data-prov-ctx="RSI (14)">
          <p className="text-xs text-text-muted mb-1">RSI (14)</p>
          <span className={`text-sm font-semibold px-2 py-0.5 rounded border ${rsiBadge(summary.rsi)}`}>
            {fmt(summary.rsi, 1)}
            {summary.rsi != null && (
              <span className="ml-1 text-xs font-normal">
                {summary.rsi > 70 ? "Overbought" : summary.rsi < 30 ? "Oversold" : "Neutral"}
              </span>
            )}
          </span>
        </div>
        <div className="rounded-lg border border-border bg-surface-alt p-3" data-prov="summary.macdSignal" data-prov-ctx="MACD signal">
          <p className="text-xs text-text-muted mb-1">MACD Signal</p>
          <span className={`text-sm font-semibold px-2 py-0.5 rounded border ${trendBadge(summary.macdSignal)}`}>
            {summary.macdSignal}
          </span>
        </div>
        <div className="rounded-lg border border-border bg-surface-alt p-3" data-prov="summary.volumeVs20d" data-prov-ctx="Volume vs 20-day">
          <p className="text-xs text-text-muted mb-1">Volume vs 20D Avg</p>
          <p className={`text-sm font-semibold ${
            summary.volumeVs20d != null && summary.volumeVs20d > 2
              ? "text-warning"
              : "text-text-primary"
          }`}>
            {summary.volumeVs20d != null ? `${fmt(summary.volumeVs20d, 2)}×` : "—"}
          </p>
        </div>
        <div className="rounded-lg border border-border bg-surface-alt p-3" data-prov="summary.week52Position" data-prov-ctx="52-week position">
          <p className="text-xs text-text-muted mb-1">52W Position</p>
          <p className="text-sm font-semibold text-text-primary">
            {summary.week52Position != null ? `${fmt(summary.week52Position, 1)}%` : "—"}
          </p>
          <p className="text-xs text-text-muted mt-0.5">
            {summary.week52Low != null && summary.week52High != null
              ? `L ${fmt(summary.week52Low, 2)} · H ${fmt(summary.week52High, 2)}`
              : ""}
          </p>
          {summary.bbSqueeze && (
            <span className="mt-1 inline-block text-xs px-1.5 py-0.5 rounded bg-warning/15 text-warning border border-warning/30" data-prov="summary.bbSqueeze">
              BB Squeeze
            </span>
          )}
        </div>
      </div>

      {/* ---- Controls ---- */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-2.5 py-1 rounded text-xs font-mono transition-colors border ${
                period === p
                  ? "bg-accent/20 text-accent border-accent/40"
                  : "text-text-muted border-border hover:text-text-primary"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
        <div className="h-4 w-px bg-border" />
        <span className="text-xs text-text-muted">Overlays:</span>
        {(Object.keys(OVERLAY_LABELS) as Overlay[]).map((o) => (
          <button
            key={o}
            onClick={() => toggleOverlay(o)}
            className={`px-2 py-0.5 rounded text-xs transition-colors border ${
              activeOverlays.has(o)
                ? "bg-accent/20 text-accent border-accent/40"
                : "text-text-muted border-border hover:text-text-primary"
            }`}
          >
            {OVERLAY_LABELS[o]}
          </button>
        ))}
      </div>

      {/* ---- Main Price Chart ---- */}
      <Card className="p-4" data-prov="prices">
        <p className="text-sm font-semibold text-text-primary mb-3">{ticker} — Price Chart</p>
        {prices.length === 0 ? (
          <div className="text-text-muted text-sm">No price data available.</div>
        ) : (
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData}>
                <CartesianGrid stroke={pal.grid} strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fill: pal.axis, fontSize: 11 }} minTickGap={40} />
                <YAxis
                  tick={{ fill: pal.axis, fontSize: 11 }}
                  tickFormatter={(v: number) => `$${v.toFixed(0)}`}
                  domain={[yMin, yMax]}
                  width={60}
                />
                <Tooltip
                  {...tt}
                  formatter={(v: number, name: string) => [v?.toFixed(2), name]}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />

                {/* Main close price */}
                <Line type="monotone" dataKey="close" stroke="#3b82f6" strokeWidth={2} dot={false} connectNulls name="Close" />

                {/* Bollinger Bands */}
                {activeOverlays.has("bollinger") && bollinger.length > 0 && (
                  <>
                    <Line type="monotone" dataKey="bbUpper" stroke="#a78bfa" strokeWidth={1} strokeDasharray="3 2" dot={false} connectNulls name="BB Upper" />
                    <Line type="monotone" dataKey="bbMid" stroke="#a78bfa" strokeWidth={1} strokeDasharray="5 3" strokeOpacity={0.6} dot={false} connectNulls name="BB Mid" />
                    <Line type="monotone" dataKey="bbLower" stroke="#a78bfa" strokeWidth={1} strokeDasharray="3 2" dot={false} connectNulls name="BB Lower" />
                  </>
                )}

                {/* Ichimoku lines */}
                {activeOverlays.has("ichimoku") && ichimoku.length > 0 && (
                  <>
                    <Line type="monotone" dataKey="tenkan" stroke="#ef4444" strokeWidth={1.5} dot={false} connectNulls name="Tenkan" />
                    <Line type="monotone" dataKey="kijun" stroke="#3b82f6" strokeWidth={1.5} strokeDasharray="4 2" dot={false} connectNulls name="Kijun" />
                    <Line type="monotone" dataKey="senkouA" stroke="#22c55e" strokeWidth={1} strokeOpacity={0.5} dot={false} connectNulls name="Senkou A" />
                    <Line type="monotone" dataKey="senkouB" stroke="#ef4444" strokeWidth={1} strokeOpacity={0.5} dot={false} connectNulls name="Senkou B" />
                  </>
                )}

                {/* Fibonacci levels */}
                {activeOverlays.has("fibonacci") && fibLevels.map((fl, i) => (
                  <ReferenceLine
                    key={`fib-${fl.label}`}
                    y={fl.price}
                    stroke={FIB_COLORS[i % FIB_COLORS.length]}
                    strokeDasharray="4 3"
                    strokeOpacity={0.7}
                    label={{ value: fl.label, position: "right", fontSize: 9, fill: FIB_COLORS[i % FIB_COLORS.length] }}
                  />
                ))}

                {/* Pivot Points (daily) */}
                {activeOverlays.has("pivots") && pivotSet && (
                  (Object.entries(pivotSet) as [string, number][]).map(([key, val]) => (
                    <ReferenceLine
                      key={`piv-${key}`}
                      y={val}
                      stroke={pivotColors[key] ?? "#94a3b8"}
                      strokeDasharray="3 2"
                      strokeOpacity={0.8}
                      label={{ value: key.toUpperCase(), position: "insideLeft", fontSize: 9, fill: pivotColors[key] ?? "#94a3b8" }}
                    />
                  ))
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      {/* ---- Sub-charts ---- */}
      <div>
        <button
          onClick={() => setShowSubCharts((v) => !v)}
          className="text-xs text-accent hover:underline mb-3"
        >
          {showSubCharts ? "▾ Hide indicator charts" : "▸ Show indicator charts"}
        </button>
        {showSubCharts && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {macd.length > 0 && (
              <Card className="p-3" data-prov="macd">
                <MACDChart data={macd} theme={theme} />
              </Card>
            )}
            {rsi.length > 0 && (
              <Card className="p-3" data-prov="rsi">
                <SubChart
                  data={rsi}
                  dataKey="value"
                  label="RSI (14)"
                  refLines={[
                    { y: 70, color: "#ef4444", dash: "3 3" },
                    { y: 30, color: "#22c55e", dash: "3 3" },
                    { y: 50, color: "#94a3b8", dash: "4 4" },
                  ]}
                  theme={theme}
                  formatter={(v) => v.toFixed(1)}
                />
              </Card>
            )}
            {stochRsi.length > 0 && (
              <Card className="p-3" data-prov="stochRsi">
                <SubChart
                  data={stochRsi}
                  dataKey={["k", "d"]}
                  label="Stochastic RSI"
                  refLines={[
                    { y: 80, color: "#ef4444", dash: "3 3" },
                    { y: 20, color: "#22c55e", dash: "3 3" },
                  ]}
                  theme={theme}
                  formatter={(v) => v.toFixed(1)}
                />
              </Card>
            )}
            {williamsR.length > 0 && (
              <Card className="p-3" data-prov="williamsR">
                <SubChart
                  data={williamsR}
                  dataKey="value"
                  label="Williams %R (14)"
                  refLines={[
                    { y: -20, color: "#ef4444", dash: "3 3" },
                    { y: -80, color: "#22c55e", dash: "3 3" },
                  ]}
                  theme={theme}
                  formatter={(v) => v.toFixed(1)}
                />
              </Card>
            )}
            {obv.length > 0 && (
              <Card className="p-3" data-prov="obv">
                <SubChart
                  data={obv}
                  dataKey="value"
                  label="On-Balance Volume (OBV)"
                  theme={theme}
                  formatter={(v) => (v / 1e6).toFixed(2) + "M"}
                />
              </Card>
            )}
            {cmf.length > 0 && (
              <Card className="p-3" data-prov="cmf">
                <SubChart
                  data={cmf}
                  dataKey="value"
                  label="Chaikin Money Flow (20)"
                  refLines={[{ y: 0, color: "#94a3b8", dash: "3 3" }]}
                  theme={theme}
                  formatter={(v) => v.toFixed(3)}
                />
              </Card>
            )}
            {atr.length > 0 && (
              <Card className="p-3" data-prov="atr">
                <SubChart
                  data={atr}
                  dataKey="value"
                  label="ATR (14)"
                  theme={theme}
                  formatter={(v) => v.toFixed(2)}
                />
              </Card>
            )}
          </div>
        )}
      </div>

      {/* ---- Fibonacci & Pivot Tables ---- */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {fibLevels.length > 0 && (
          <Card className="p-4" data-prov="fibLevels">
            <p className="text-sm font-semibold text-text-primary mb-3">
              Fibonacci Retracement (6M {data.fibDirection ?? "swing"}
              {data.fibSwing ? `, ${data.fibSwing.direction === "downswing" ? "high → low" : "low → high"}` : ""})
            </p>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-text-muted border-b border-border">
                  <th className="text-left pb-1">Level</th>
                  <th className="text-right pb-1">Price</th>
                </tr>
              </thead>
              <tbody>
                {fibLevels.map((fl) => (
                  <tr key={fl.label} className="border-b border-border/50">
                    <td className="py-1 text-text-secondary">{fl.label}</td>
                    <td className="py-1 text-right font-mono text-text-primary">{fmt(fl.price, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}

        {Object.keys(pivotPoints ?? {}).length > 0 && (
          <Card className="p-4" data-prov="pivotPoints">
            <p className="text-sm font-semibold text-text-primary mb-3">Pivot Points (Classic)</p>
            {(["daily", "weekly", "monthly"] as const).map((tf) => {
              const ps = (pivotPoints as Record<string, PivotSet>)?.[tf];
              if (!ps) return null;
              return (
                <div key={tf} className="mb-3" data-prov={`pivotPoints.${tf}`}>
                  <p className="text-xs text-text-muted uppercase tracking-wide mb-1 capitalize">{tf}</p>
                  <div className="grid grid-cols-5 gap-1 text-xs text-center">
                    {[
                      { k: "s2", label: "S2", color: "text-danger" },
                      { k: "s1", label: "S1", color: "text-danger" },
                      { k: "p",  label: "P",  color: "text-text-primary font-semibold" },
                      { k: "r1", label: "R1", color: "text-success" },
                      { k: "r2", label: "R2", color: "text-success" },
                    ].map(({ k, label, color }) => (
                      <div key={k} className="rounded bg-surface-alt p-1">
                        <p className={`text-xs font-medium ${color}`}>{label}</p>
                        <p className="font-mono text-text-primary">{fmt((ps as unknown as Record<string, number>)[k], 2)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </Card>
        )}
      </div>

      {data.asOf && (
        <p className="text-xs text-text-muted text-right">Data as of {data.asOf} · Indicators via pandas_ta</p>
      )}
    </div>
  );
}
