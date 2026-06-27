"use client";

import { useCallback, useEffect, useState } from "react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Cell, ResponsiveContainer, Legend,
} from "recharts";
import { Card } from "@/components/ui";
import { SearchBar } from "@/components/SearchBar";
import { api } from "@/lib/api";
import type { MomentsResponse, MomentsCrossSection } from "@/lib/types";

const PERIODS = ["1y", "2y", "3y", "5y"] as const;
type Period = (typeof PERIODS)[number];

const UNIVERSES = [
  { key: "dow",   label: "Dow 30" },
  { key: "ndx",   label: "Nasdaq 100" },
  { key: "sp500", label: "S&P 500" },
] as const;
type Universe = (typeof UNIVERSES)[number]["key"];

const WINDOWS = [
  { value: 21,  label: "1M" },
  { value: 63,  label: "3M" },
  { value: 126, label: "6M" },
] as const;

const tooltipStyle = {
  backgroundColor: "var(--color-surface-alt)",
  border: "1px solid var(--color-border)",
  borderRadius: 8,
  fontSize: 12,
};

function fmt(v: number | null | undefined, dp = 2): string {
  return v === null || v === undefined ? "—" : v.toFixed(dp);
}
function pct(v: number | null | undefined, dp = 1): string {
  return v === null || v === undefined ? "—" : `${(v * 100).toFixed(dp)}%`;
}

export function RealizedMomentsTab() {
  // --- Single-ticker moments ---
  const [ticker, setTicker] = useState("AAPL");
  const [period, setPeriod] = useState<Period>("3y");
  const [data, setData] = useState<MomentsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<"rvol" | "skew" | "kurt">("rvol");

  // --- Cross-section ---
  const [universe, setUniverse] = useState<Universe>("dow");
  const [window_, setWindow] = useState(21);
  const [xs, setXs] = useState<MomentsCrossSection | null>(null);
  const [xsLoading, setXsLoading] = useState(false);

  const loadMoments = useCallback((t: string, p: Period) => {
    if (!t.trim()) return;
    setLoading(true);
    api.moments(t.trim().toUpperCase(), p)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  // Auto-load moments on mount and when ticker/period changes (🟢)
  useEffect(() => {
    loadMoments(ticker, period);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period]);  // only period change auto-triggers; ticker requires Enter/blur

  const runCrossSection = () => {
    setXsLoading(true);
    api.momentsCrosssection(universe, window_)
      .then(setXs)
      .catch(() => setXs(null))
      .finally(() => setXsLoading(false));
  };

  // Build chart series — show last 252 rows to keep chart readable
  const seriesSlice = (data?.series ?? []).slice(-252);
  const chartData = seriesSlice.map((r) => ({
    date:    r.date.slice(5),    // MM-DD
    rvol21:  r.rvol21  !== null ? +(r.rvol21  * 100).toFixed(2)  : null,
    rvol63:  r.rvol63  !== null ? +(r.rvol63  * 100).toFixed(2)  : null,
    rvol252: r.rvol252 !== null ? +(r.rvol252 * 100).toFixed(2)  : null,
    skew21:  r.skew21  !== null ? +r.skew21.toFixed(3)   : null,
    skew63:  r.skew63  !== null ? +r.skew63.toFixed(3)   : null,
    skew252: r.skew252 !== null ? +r.skew252.toFixed(3)  : null,
    kurt21:  r.kurt21  !== null ? +r.kurt21.toFixed(3)   : null,
    kurt63:  r.kurt63  !== null ? +r.kurt63.toFixed(3)   : null,
    kurt252: r.kurt252 !== null ? +r.kurt252.toFixed(3)  : null,
  }));

  const xsDeciles = (xs?.deciles ?? []).map((d) => ({
    decile: `D${d.decile}`,
    value:  (d.avgFwdReturn ?? 0) * 100,
    count:  d.count,
  }));

  return (
    <div className="space-y-6">
      {/* ── Ticker controls ──────────────────────────────────────────────── */}
      <Card>
        <div className="flex flex-wrap items-end gap-6">
          <div className="flex-1 min-w-[160px]">
            <label className="block text-xs text-text-muted mb-1">Ticker</label>
            <SearchBar onAdd={(sym) => {
              setTicker(sym.toUpperCase());
              loadMoments(sym.toUpperCase(), period);
            }} />
            {ticker && (
              <span className="inline-flex items-center gap-1 mt-1.5 px-2 py-0.5 rounded-full bg-surface-alt border border-border text-xs font-mono">
                {ticker}
              </span>
            )}
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Period</label>
            <div className="flex gap-1">
              {PERIODS.map((p) => (
                <button key={p} onClick={() => setPeriod(p)}
                  className={`px-2.5 py-1 rounded-md text-xs font-mono ${period === p ? "bg-surface-alt text-text-primary" : "text-text-muted hover:text-text-primary"}`}>
                  {p.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Series</label>
            <div className="flex gap-1">
              {([["rvol", "Realized Vol"], ["skew", "Skewness"], ["kurt", "Excess Kurtosis"]] as const).map(([k, label]) => (
                <button key={k} onClick={() => setView(k)}
                  className={`px-2.5 py-1 rounded-md text-xs ${view === k ? "bg-accent text-white" : "text-text-muted hover:text-text-primary"}`}>
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
        <p className="text-xs text-text-muted mt-2">
          Garman-Klass realized variance · rolling 1M / 3M / 12M windows · log-return skew & excess kurtosis
        </p>
      </Card>

      {/* ── KPI strip ────────────────────────────────────────────────────── */}
      {data && !data.error && data.latest && (
        <div className="grid grid-cols-3 gap-4">
          {([
            ["Realized Vol (1M)", data.latest.rvol21 !== null ? pct(data.latest.rvol21) : "—", "ann. GK vol"],
            ["Skewness (1M)",     fmt(data.latest.skew21), "log-return skew"],
            ["Excess Kurtosis (1M)", fmt(data.latest.kurt21), "log-return kurt"],
          ] as const).map(([label, value, sub]) => (
            <Card key={label}>
              <div className="text-xs text-text-muted">{label}</div>
              <div className="text-2xl font-mono font-semibold text-accent mt-1">{value}</div>
              <div className="text-xs text-text-muted mt-0.5">{sub}</div>
            </Card>
          ))}
        </div>
      )}

      {loading && <div className="h-72 animate-pulse bg-surface-alt rounded-lg" />}

      {/* ── Time-series chart ─────────────────────────────────────────────── */}
      {!loading && data && !data.error && chartData.length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold text-text-secondary mb-3">
            {view === "rvol" ? "Annualised Realized Volatility (%)"
              : view === "skew" ? "Realized Skewness"
              : "Realized Excess Kurtosis"}
            {data.asOf && <span className="text-text-muted font-normal"> · {data.asOf}</span>}
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData} margin={{ left: 8, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--color-text-muted)" }} minTickGap={48} />
              <YAxis tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} domain={["auto", "auto"]} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {view === "rvol" && <>
                <Line type="monotone" dataKey="rvol21"  name="1M RVol"  stroke="#6366f1" dot={false} strokeWidth={1.5} connectNulls />
                <Line type="monotone" dataKey="rvol63"  name="3M RVol"  stroke="#f59e0b" dot={false} strokeWidth={1.5} connectNulls />
                <Line type="monotone" dataKey="rvol252" name="12M RVol" stroke="#10b981" dot={false} strokeWidth={1.5} connectNulls />
              </>}
              {view === "skew" && <>
                <Line type="monotone" dataKey="skew21"  name="1M Skew"  stroke="#6366f1" dot={false} strokeWidth={1.5} connectNulls />
                <Line type="monotone" dataKey="skew63"  name="3M Skew"  stroke="#f59e0b" dot={false} strokeWidth={1.5} connectNulls />
                <Line type="monotone" dataKey="skew252" name="12M Skew" stroke="#10b981" dot={false} strokeWidth={1.5} connectNulls />
              </>}
              {view === "kurt" && <>
                <Line type="monotone" dataKey="kurt21"  name="1M Kurt"  stroke="#6366f1" dot={false} strokeWidth={1.5} connectNulls />
                <Line type="monotone" dataKey="kurt63"  name="3M Kurt"  stroke="#f59e0b" dot={false} strokeWidth={1.5} connectNulls />
                <Line type="monotone" dataKey="kurt252" name="12M Kurt" stroke="#10b981" dot={false} strokeWidth={1.5} connectNulls />
              </>}
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {!loading && data?.error && (
        <Card><p className="text-sm text-text-muted">Moments unavailable: {data.error}</p></Card>
      )}

      {/* ── Cross-section ────────────────────────────────────────────────── */}
      <Card>
        <div className="flex flex-wrap items-end gap-6 mb-3">
          <div>
            <label className="block text-xs text-text-muted mb-1">Universe</label>
            <div className="flex gap-1">
              {UNIVERSES.map((u) => (
                <button key={u.key} onClick={() => setUniverse(u.key)}
                  className={`px-2.5 py-1 rounded-md text-xs ${universe === u.key ? "bg-accent text-white" : "text-text-muted hover:text-text-primary"}`}>
                  {u.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Formation Window</label>
            <div className="flex gap-1">
              {WINDOWS.map((w) => (
                <button key={w.value} onClick={() => setWindow(w.value)}
                  className={`px-2.5 py-1 rounded-md text-xs font-mono ${window_ === w.value ? "bg-surface-alt text-text-primary" : "text-text-muted hover:text-text-primary"}`}>
                  {w.label}
                </button>
              ))}
            </div>
          </div>
          <button onClick={runCrossSection} disabled={xsLoading}
            className="px-3 py-1.5 rounded-lg bg-danger/90 hover:bg-danger text-white text-xs font-semibold disabled:opacity-50">
            {xsLoading ? "Running…" : "🔴 Run Cross-Section"}
          </button>
        </div>
        <p className="text-xs text-text-muted">
          Sort universe by prior-skewness into deciles; compute forward returns. Tests the MAX/MIN effect.
          Excess Kurtosis axis on the ticker chart measures fat-tail risk relative to a normal distribution.
        </p>
      </Card>

      {xsLoading && <div className="h-72 animate-pulse bg-surface-alt rounded-lg" />}

      {!xsLoading && xs && !xs.error && xs.deciles.length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold text-text-secondary mb-3">
            Decile Avg Forward Return by Prior Skewness
            {xs.asOf && <span className="text-text-muted font-normal"> · {xs.asOf}</span>}
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={xsDeciles} margin={{ left: 8, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="decile" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
              <YAxis
                tickFormatter={(v) => `${v.toFixed(1)}%`}
                tick={{ fontSize: 11, fill: "var(--color-text-muted)" }}
                label={{ value: "Avg Fwd Return (%)", angle: -90, position: "insideLeft", fontSize: 10, fill: "var(--color-text-muted)", dy: 60 }}
              />
              <Tooltip
                formatter={(v: number) => [`${v.toFixed(2)}%`, "Avg Fwd Return"]}
                contentStyle={tooltipStyle}
              />
              <Bar dataKey="value" name="Avg Fwd Return" radius={[4, 4, 0, 0]}>
                {xsDeciles.map((d, i) => (
                  <Cell key={i} fill={d.value >= 0 ? "#10b981" : "#ef4444"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs text-text-muted mt-2">
            D1 = most negative prior skew · D{xs.deciles.length} = most positive prior skew ·{" "}
            {xs.missing.length > 0 && `${xs.missing.length} tickers excluded (insufficient history)`}
          </p>
        </Card>
      )}

      {!xsLoading && xs?.error && (
        <Card><p className="text-sm text-text-muted">Cross-section unavailable: {xs.error}</p></Card>
      )}

      {!xsLoading && !xs && (
        <Card>
          <p className="text-sm text-text-muted">
            Press <span className="font-semibold">Run Cross-Section</span> to sort the selected universe by
            prior skewness and compute forward returns per decile.
          </p>
        </Card>
      )}
    </div>
  );
}
