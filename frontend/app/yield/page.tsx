"use client";
import { useState, useEffect, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useUrlState } from "@/lib/useUrlState";
import type { RatesData, GlobalYieldCountry } from "@/lib/types";
import { MultiCountryYieldChart } from "@/components/yield/MultiCountryYieldChart";
import { Card as UiCard, PageSkeleton, TabButton } from "@/components/ui";
import { CHART_COLORS } from "@/lib/format";
import { PolicyDivergenceTable } from "@/components/policy/PolicyDivergenceTable";
import { SovereignSpreadTable } from "@/components/sovereign/SovereignSpreadTable";
import { CentralBanksTab } from "@/components/macro/CentralBanksTab";
import { CurveNoiseTab } from "@/components/yield/CurveNoiseTab";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, ReferenceLine,
} from "recharts";

const TABS = ["US Curve", "Foreign Spreads", "Global Yields", "Real & Breakeven", "Curve Noise", "US Rates Detail", "Policy Tracker", "Sovereign Risk", "Central Banks", "Default Risk"] as const;

function KpiCard({ label, value, badge }: { label: string; value: string; badge?: string }) {
  return (
    <div className="bg-surface rounded-lg p-4 border border-border">
      <div className="text-xs text-muted mb-1">{label}</div>
      <div className="text-xl font-semibold">{value}</div>
      {badge && (
        <span className="text-xs mt-1 px-2 py-0.5 rounded-full bg-red-500/20 text-red-400">{badge}</span>
      )}
    </div>
  );
}

// ─── US Rates Detail tab (merged from RatesYields) ──────────────────
function USRatesDetailTab() {
  const [data, setData] = useState<RatesData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.macroRates().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <PageSkeleton text="Loading rates data…" />;
  if (!data) return <div className="text-muted text-sm py-8 text-center">Rates data unavailable.</div>;

  // Neutral grid colour readable in both light & dark themes
  const GRID = "rgba(128,128,128,0.18)";
  const C = CHART_COLORS;

  const spread = data.spread_2y10y;
  const spreadColor = spread != null && spread < 0 ? "text-danger" : "text-success";

  const tenors = ["DGS3MO", "DGS2", "DGS5", "DGS7", "DGS10", "DGS20", "DGS30"];
  const tenorLabels: Record<string, string> = { DGS3MO: "3M", DGS2: "2Y", DGS5: "5Y", DGS7: "7Y", DGS10: "10Y", DGS20: "20Y", DGS30: "30Y" };
  const curveData = tenors.map((t) => ({ tenor: tenorLabels[t], yield: data.yields[t] ?? null }));

  const hist10y = data.history["DGS10"] ?? [];
  const hist2y = data.history["DGS2"] ?? [];
  const hist3m = data.history["DGS3MO"] ?? [];
  const histData = hist10y.map((pt, i) => ({ date: pt.date.slice(0, 7), "10Y": pt.value, "2Y": hist2y[i]?.value ?? null, "3M": hist3m[i]?.value ?? null }));

  const histBe5 = data.history["T5YIE"] ?? [];
  const histBe10 = data.history["T10YIE"] ?? [];
  const breakevenData = histBe5.map((pt, i) => ({ date: pt.date.slice(0, 7), "5Y BE": pt.value, "10Y BE": histBe10[i]?.value ?? null }));

  const histHY = data.history["BAMLH0A0HYM2"] ?? [];
  const histIG = data.history["BAMLC0A0CM"] ?? [];
  const spreadHistoryData = histHY.map((pt, i) => ({ date: pt.date.slice(0, 7), "HY OAS": pt.value, "IG OAS": histIG[i]?.value ?? null }));

  const taylorImplied = data.taylor_rule?.implied ?? [];
  const taylorActual = data.taylor_rule?.actual ?? [];
  const taylorData = taylorImplied.map((pt, i) => ({ date: pt.date.slice(0, 7), "Taylor Rule": pt.value, Actual: taylorActual[i]?.value ?? null }));

  const acmExp = data.acm?.expectations ?? [];
  const acmTP = data.acm?.term_premium ?? [];
  const acmData = acmExp.map((pt, i) => ({ date: pt.date.slice(0, 7), Expectations: pt.value, "Term Premium": acmTP[i]?.value ?? null }));

  return (
    <div className="space-y-6">
      {/* KPI Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <KpiCard label="Fed Funds Rate" value={data.yields["FEDFUNDS"] != null ? `${data.yields["FEDFUNDS"].toFixed(2)}%` : "N/A"} />
        <KpiCard label="10Y Treasury" value={data.yields["DGS10"] != null ? `${data.yields["DGS10"].toFixed(2)}%` : "N/A"} />
        <KpiCard label="2Y Treasury" value={data.yields["DGS2"] != null ? `${data.yields["DGS2"].toFixed(2)}%` : "N/A"} />
        <KpiCard label="2Y/10Y Spread" value={spread != null ? `${spread.toFixed(2)}%` : "N/A"} badge={data.inverted ? "INVERTED" : undefined} />
        <KpiCard label="30Y Mortgage" value={data.yields["MORTGAGE30US"] != null ? `${data.yields["MORTGAGE30US"].toFixed(2)}%` : "N/A"} />
      </div>

      {/* Yield Curve Snapshot */}
      <UiCard className="p-4">
        <h3 className="font-semibold mb-3">US Treasury Yield Curve</h3>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={curveData}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
            <XAxis dataKey="tenor" tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={(v) => `${v}%`} domain={["auto", "auto"]} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`, "Yield"]} />
            <Line type="monotone" dataKey="yield" stroke="#3b82f6" strokeWidth={2} dot={{ r: 4 }} />
          </LineChart>
        </ResponsiveContainer>
      </UiCard>

      {/* Historical Yields */}
      {histData.length > 0 && (
        <UiCard className="p-4">
          <h3 className="font-semibold mb-3">Treasury Yields — Historical</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={histData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <Line type="monotone" dataKey="10Y" stroke="#3b82f6" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="2Y" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="3M" stroke="#10b981" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </UiCard>
      )}

      {/* Breakeven Rates */}
      {breakevenData.length > 0 && (
        <UiCard className="p-4">
          <h3 className="font-semibold mb-3">Breakeven Inflation Rates</h3>
          <div className="flex gap-6 mb-3">
            <div>
              <span className="text-xs text-text-muted">5Y BE</span>
              <span className="ml-2 text-sm font-mono font-semibold" style={{color: "#8b5cf6"}}>
                {histBe5.length ? `${histBe5[histBe5.length - 1].value?.toFixed(2)}%` : "—"}
              </span>
            </div>
            <div>
              <span className="text-xs text-text-muted">10Y BE</span>
              <span className="ml-2 text-sm font-mono font-semibold" style={{color: "#ec4899"}}>
                {histBe10.length ? `${histBe10[histBe10.length - 1].value?.toFixed(2)}%` : "—"}
              </span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={breakevenData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <Line type="monotone" dataKey="5Y BE" stroke="#8b5cf6" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="10Y BE" stroke="#ec4899" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </UiCard>
      )}

      {/* IG/HY OAS Credit Spreads */}
      {spreadHistoryData.length > 0 && (
        <UiCard className="p-4">
          <h3 className="font-semibold mb-3">Credit Spreads — IG / HY OAS</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={spreadHistoryData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <Line type="monotone" dataKey="IG OAS" stroke="#3b82f6" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="HY OAS" stroke="#ef4444" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </UiCard>
      )}

      {/* Taylor Rule */}
      {taylorData.length > 0 && (
        <UiCard className="p-4">
          <h3 className="font-semibold mb-3">Taylor Rule — Implied vs Actual Fed Funds</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={taylorData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <ReferenceLine y={0} stroke={GRID} strokeDasharray="4 4" />
              <Line type="monotone" dataKey="Taylor Rule" stroke="#8b5cf6" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="Actual" stroke="#f59e0b" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </UiCard>
      )}

      {/* ACM Decomposition */}
      {acmData.length > 0 && (
        <UiCard className="p-4">
          <h3 className="font-semibold mb-3">ACM Term Premium Decomposition</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={acmData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <Line type="monotone" dataKey="Expectations" stroke="#3b82f6" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="Term Premium" stroke="#ef4444" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </UiCard>
      )}
    </div>
  );
}

// ─── Global Yields Tab ─────────────────────────────────────────────
function GlobalYieldsTab({ data: countries }: { data: GlobalYieldCountry[] }) {
  const GRID = "rgba(128,128,128,0.18)";
  if (!countries || countries.length === 0) {
    return <div className="text-muted text-sm py-8 text-center">No global yield data available.</div>;
  }

  // Summary KPIs
  const withYields = countries.filter(c => c.yield_10y != null);
  const highest = withYields[0];
  const lowest = withYields[withYields.length - 1];
  const avgYield = withYields.length > 0
    ? withYields.reduce((s, c) => s + (c.yield_10y ?? 0), 0) / withYields.length
    : null;
  const widestSpread = [...countries]
    .filter(c => c.spread_vs_us != null)
    .sort((a, b) => Math.abs(b.spread_vs_us!) - Math.abs(a.spread_vs_us!))[0];

  const fmt = (v: number | null, decimals = 2) => v != null ? `${v > 0 ? "+" : ""}${v.toFixed(decimals)}%` : "N/A";
  const fmtPct = (v: number | null, decimals = 2) => v != null ? `${v.toFixed(decimals)}%` : "N/A";

  return (
    <div className="space-y-6">
      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KpiCard label="Countries Covered" value={String(withYields.length)} />
        <KpiCard label="Highest 10Y" value={fmtPct(highest?.yield_10y ?? null)} badge={highest?.name} />
        <KpiCard label="Lowest 10Y" value={fmtPct(lowest?.yield_10y ?? null)} badge={lowest?.name} />
        <KpiCard label="Average 10Y" value={fmtPct(avgYield)} />
        <KpiCard label="Widest vs US" value={fmt(widestSpread?.spread_vs_us ?? null)} badge={widestSpread?.name} />
      </div>

      {/* Yield Spread Matrix Table */}
      <UiCard className="p-4 overflow-x-auto">
        <h3 className="font-semibold mb-3">Global 10Y Government Bond Yields &amp; Spreads</h3>
        <p className="text-xs text-text-secondary mb-4">
          Real yield = nominal 10Y − latest CPI inflation (World Bank). Sorted by nominal yield.
        </p>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-text-secondary border-b border-border">
              <th className="py-2 pr-4">Country</th>
              <th className="py-2 px-2 text-right">Nominal 10Y</th>
              <th className="py-2 px-2 text-right">Real Yield</th>
              <th className="py-2 px-2 text-right">Inflation</th>
              <th className="py-2 px-2 text-right">vs US</th>
              <th className="py-2 px-2 text-right">vs Germany</th>
              <th className="py-2 px-2 text-right">vs Japan</th>
            </tr>
          </thead>
          <tbody>
            {countries.filter(c => c.yield_10y != null).map((c) => (
              <tr key={c.iso2} className="border-b border-border/50 hover:bg-surface-alt/50">
                <td className="py-2 pr-4 font-medium">{c.name}</td>
                <td className={`py-2 px-2 text-right font-mono ${(c.yield_10y ?? 0) > 6 ? "text-red-400" : (c.yield_10y ?? 0) < 1 ? "text-green-400" : ""}`}>
                  {fmtPct(c.yield_10y)}
                </td>
                <td className={`py-2 px-2 text-right font-mono ${(c.real_yield ?? 0) < -1 ? "text-red-400" : (c.real_yield ?? 0) > 2 ? "text-green-400" : ""}`}>
                  {fmtPct(c.real_yield)}
                </td>
                <td className="py-2 px-2 text-right font-mono text-text-secondary">{fmtPct(c.inflation)}</td>
                <td className={`py-2 px-2 text-right font-mono ${(c.spread_vs_us ?? 0) > 3 ? "text-red-400" : ""}`}>
                  {fmt(c.spread_vs_us)}
                </td>
                <td className={`py-2 px-2 text-right font-mono ${(c.spread_vs_de ?? 0) > 2 ? "text-amber-400" : ""}`}>
                  {fmt(c.spread_vs_de)}
                </td>
                <td className={`py-2 px-2 text-right font-mono ${(c.spread_vs_jp ?? 0) > 4 ? "text-amber-400" : ""}`}>
                  {fmt(c.spread_vs_jp)}
                </td>
              </tr>
            ))}
            {countries.filter(c => c.yield_10y == null).map((c) => (
              <tr key={c.iso2} className="border-b border-border/50 text-text-secondary">
                <td className="py-2 pr-4">{c.name}</td>
                <td colSpan={6} className="py-2 px-2 text-center text-xs">Data unavailable</td>
              </tr>
            ))}
          </tbody>
        </table>
      </UiCard>

      {/* Yield Bar Chart */}
      <UiCard className="p-4">
        <h3 className="font-semibold mb-3">10Y Government Bond Yields — Ranked</h3>
        <ResponsiveContainer width="100%" height={Math.max(300, withYields.length * 24)}>
          <BarChart
            data={withYields.map(c => ({ name: c.name, yield: c.yield_10y, real: c.real_yield }))}
            layout="vertical" margin={{ left: 100, right: 40 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
            <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={95} />
            <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
            <Bar dataKey="yield" fill="#3b82f6" radius={[0, 3, 3, 0]} name="Nominal 10Y" />
            <Bar dataKey="real" fill="#10b981" radius={[0, 3, 3, 0]} name="Real Yield" />
          </BarChart>
        </ResponsiveContainer>
      </UiCard>
    </div>
  );
}

function YieldPageInner() {
  const [urlState, setUrlState] = useUrlState({ tab: "US Curve" });
  const tab = urlState.tab;
  const { data, isLoading, error } = useQuery({
    queryKey: ["yieldCurves"],
    queryFn: api.yieldCurves,
  });

  if (isLoading) return <div className="p-8 text-muted">Loading yield curve data…</div>;
  if (error || !data) return <div className="p-8 text-red-400">Failed to load yield data.</div>;

  const { us_curve, foreign_10y, real_yields, breakevens, term_premium, global_yields } = data;
  const fwdBreakeven = data.forward_breakeven_5y5y;
  const fmt = (v: number | null, decimals = 2) => v != null ? `${v.toFixed(decimals)}%` : "N/A";

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Rates &amp; Policy</h1>

      {/* KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="US 10Y Yield" value={fmt(us_curve.points.find(p => p.tenor === "10y")?.yield ?? null)} />
        <KpiCard
          label="2Y–10Y Spread"
          value={fmt(us_curve.spread_2y10y)}
          badge={us_curve.inverted ? "INVERTED" : undefined}
        />
        <KpiCard label="10Y Breakeven" value={fmt(breakevens["10y"] ?? null)} />
        <KpiCard label="10Y Term Premium (Kim-Wright)" value={fmt(term_premium.current)} />
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border overflow-x-auto no-scrollbar">
        {TABS.map((t) => (
          <TabButton key={t} active={tab === t} onClick={() => setUrlState({ tab: t })}>
            {t}
          </TabButton>
        ))}
      </div>

      {tab === "US Curve" && (
        <div className="bg-surface rounded-lg p-4 border border-border">
          <h2 className="text-sm font-medium mb-4 text-muted">US Treasury Spot Curve</h2>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={us_curve.points.filter(p => p.yield !== null)}>
              <XAxis dataKey="tenor" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={(v) => `${v.toFixed(1)}%`} domain={["auto", "auto"]} />
              <Tooltip formatter={(v: number) => [`${v.toFixed(3)}%`, "Yield"]} />
              <Line type="monotone" dataKey="yield" stroke="#3b82f6" dot={{ r: 4 }} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {tab === "Foreign Spreads" && (
        <div className="bg-surface rounded-lg p-4 border border-border">
          <h2 className="text-sm font-medium mb-4 text-muted">10Y Sovereign Spread vs US Treasury</h2>
          <MultiCountryYieldChart data={foreign_10y} />
        </div>
      )}

      {tab === "Global Yields" && <GlobalYieldsTab data={global_yields ?? []} />}

      {tab === "Real & Breakeven" && (
        <div className="bg-surface rounded-lg p-4 border border-border">
          <h2 className="text-sm font-medium mb-4 text-muted">TIPS Real Yields by Tenor</h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={real_yields.filter(p => p.yield !== null)}>
              <XAxis dataKey="tenor" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={(v) => `${v.toFixed(1)}%`} />
              <Tooltip formatter={(v: number) => [`${v.toFixed(3)}%`, "Real Yield"]} />
              <Bar dataKey="yield" fill="#8b5cf6" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(breakevens).map(([tenor, val]) => (
              <KpiCard key={tenor} label={`${tenor} Breakeven`} value={fmt(val)} />
            ))}
            <KpiCard label="5y5y Forward Breakeven" value={fmt(fwdBreakeven?.current ?? null)} />
          </div>

          {/* 5y5y forward breakeven — the FOMC's preferred anchor measure */}
          {(fwdBreakeven?.history?.length ?? 0) > 0 && (
            <div className="mt-6">
              <h2 className="text-sm font-medium mb-1 text-muted">5y5y Forward Breakeven Inflation</h2>
              <p className="text-xs text-text-secondary mb-3">
                Inflation compensation priced for the five years starting five years out.
                Because it strips near-term energy passthrough, it is the anchor measure the
                FOMC cites for long-run expectations — though it still embeds an inflation
                risk premium, so it is not a pure expectation.
              </p>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={fwdBreakeven!.history.map((p) => ({ date: p.date, value: p.value }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(128,128,128,0.18)" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                  <YAxis tickFormatter={(v) => `${v.toFixed(1)}%`} domain={["auto", "auto"]} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`, "5y5y forward"]} />
                  <ReferenceLine y={2} stroke="#10b981" strokeDasharray="4 4" label={{ value: "2% target", fontSize: 10, fill: "#10b981" }} />
                  <Line type="monotone" dataKey="value" stroke="#f59e0b" dot={false} strokeWidth={1.6} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {tab === "Curve Noise" && <CurveNoiseTab />}

      {tab === "US Rates Detail" && <USRatesDetailTab />}

      {tab === "Policy Tracker" && <PolicyTrackerTab />}
      {tab === "Sovereign Risk" && <SovereignRiskTab />}
      {tab === "Central Banks" && <CentralBanksTab />}
      {tab === "Default Risk" && <DefaultRiskTab />}
    </div>
  );
}

/* ─── Policy Tracker tab (merged from /policy) ─────────────────────── */
function PolicyTrackerTab() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["policyTracker"],
    queryFn: api.policyTracker,
  });

  if (isLoading) return <div className="p-8 text-muted">Loading policy data…</div>;
  if (error || !data) return <div className="p-8 text-red-400">Failed to load policy data.</div>;

  const { divergence, carry_differentials } = data;
  const fed = divergence.find((d: { cb: string }) => d.cb === "Fed");
  const tightening = divergence.filter((d: { stance: string }) => d.stance === "tightening")[0];
  const easing = divergence.filter((d: { stance: string }) => d.stance === "easing").at(-1);
  const maxCarryEntry = Object.entries(carry_differentials)
    .filter(([, v]) => v !== null)
    .sort(([, a], [, b]) => Math.abs(b as number) - Math.abs(a as number))[0];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Fed Funds Rate"
          value={fed?.current_rate != null ? `${fed.current_rate.toFixed(2)}%` : "N/A"}
          badge={fed ? `${fed.stance.replace("_", " ")} (12M: ${(fed.change_12m ?? 0).toFixed(2)}%)` : undefined}
        />
        <KpiCard
          label="Most Tightening"
          value={tightening?.cb ?? "None"}
          badge={tightening ? `+${(tightening.change_12m ?? 0).toFixed(2)}% (12M)` : undefined}
        />
        <KpiCard
          label="Most Easing"
          value={easing?.cb ?? "None"}
          badge={easing ? `${(easing.change_12m ?? 0).toFixed(2)}% (12M)` : undefined}
        />
        <KpiCard
          label="Max Carry Differential"
          value={maxCarryEntry ? maxCarryEntry[0] : "N/A"}
          badge={maxCarryEntry && maxCarryEntry[1] != null ? `${(maxCarryEntry[1] as number).toFixed(2)}%` : undefined}
        />
      </div>

      <UiCard className="p-4">
        <h2 className="text-sm font-medium mb-4 text-muted">Policy Rate Divergence — All Central Banks</h2>
        <PolicyDivergenceTable entries={divergence} />
      </UiCard>

      <UiCard className="p-4">
        <h2 className="text-sm font-medium mb-3 text-muted">G10 Carry Differentials vs USD</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {Object.entries(carry_differentials).map(([pair, val]) => (
            <div key={pair} className="flex justify-between px-3 py-2 rounded bg-background border border-border/50">
              <span className="text-sm">{pair}</span>
              <span className={`text-sm font-medium ${(val as number ?? 0) > 0 ? "text-red-400" : "text-green-400"}`}>
                {val != null ? `${(val as number) > 0 ? "+" : ""}${(val as number).toFixed(2)}%` : "N/A"}
              </span>
            </div>
          ))}
        </div>
      </UiCard>
    </div>
  );
}

/* ─── Sovereign Risk tab (merged from /policy) ─────────────────────── */
function SovereignRiskTab() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["sovereignRisk"],
    queryFn: api.sovereignRisk,
  });

  if (isLoading) return <div className="p-8 text-muted">Loading sovereign risk data…</div>;
  if (error || !data) return <div className="p-8 text-red-400">Failed to load sovereign data.</div>;

  const { countries, top_risk, bottom_risk } = data;
  const redCount = countries.filter((c: { signal: string }) => c.signal === "red").length;
  const riskiest = top_risk[0];
  const safest = bottom_risk[bottom_risk.length - 1];
  const avgSpread =
    countries.reduce((s: number, c: { spread_vs_us: number | null }) => s + (c.spread_vs_us ?? 0), 0) / (countries.length || 1);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Highest Risk"
          value={riskiest?.name ?? "N/A"}
          badge={riskiest ? `Score: ${riskiest.composite_score.toFixed(1)}` : undefined}
        />
        <KpiCard
          label="Lowest Risk"
          value={safest?.name ?? "N/A"}
          badge={safest ? `Score: ${safest.composite_score.toFixed(1)}` : undefined}
        />
        <KpiCard label="Avg Spread vs US" value={`${avgSpread.toFixed(2)}%`} />
        <KpiCard label="Red-Signal Countries" value={String(redCount)} />
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <UiCard className="p-4 border-red-500/30">
          <h2 className="text-sm font-medium mb-3 text-red-400">Top 5 Riskiest</h2>
          <SovereignSpreadTable countries={top_risk} />
        </UiCard>
        <UiCard className="p-4 border-green-500/30">
          <h2 className="text-sm font-medium mb-3 text-green-400">Top 5 Safest</h2>
          <SovereignSpreadTable countries={bottom_risk.slice().reverse()} />
        </UiCard>
      </div>

      <UiCard className="p-4">
        <h2 className="text-sm font-medium mb-4 text-muted">All Countries — Sovereign Risk</h2>
        <SovereignSpreadTable countries={countries} />
      </UiCard>
    </div>
  );
}

/* ─── Default Risk tab (Phase 31) ──────────────────────────────────── */
function DefaultRiskTab() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["sovereignDefault"],
    queryFn: api.sovereignDefaultProb,
  });

  if (isLoading) return <div className="p-8 text-muted">Computing default probabilities…</div>;
  if (error || !data) return <div className="p-8 text-red-400">Failed to load default model.</div>;
  if (data.error) return <div className="p-8 text-amber-400">{data.error}</div>;

  const { model, countries } = data;
  const redCount = countries.filter((c) => c.signal === "red").length;
  const yellowCount = countries.filter((c) => c.signal === "yellow").length;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Countries" value={String(countries.length)} />
        <KpiCard label="High Risk" value={String(redCount)} badge=">20%" />
        <KpiCard label="Medium Risk" value={String(yellowCount)} badge="5-20%" />
        <KpiCard label="Pseudo R²" value={model?.pseudoR2?.toFixed(3) ?? "—"} />
      </div>

      {model && (
        <UiCard className="p-4">
          <h2 className="text-sm font-medium mb-3 text-muted">Model Summary · {model.nObs} observations</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-muted border-b border-border/50">
                  <th className="py-1.5 text-left">Predictor</th>
                  <th className="py-1.5 text-right">Coef</th>
                  <th className="py-1.5 text-right">Std Err</th>
                  <th className="py-1.5 text-right">t</th>
                  <th className="py-1.5 text-right">p</th>
                </tr>
              </thead>
              <tbody>
                {model.coefficients.map((c) => (
                  <tr key={c.name} className="border-b border-border/30">
                    <td className="py-1.5 font-mono">{c.name}{c.stars ? <span className="text-accent ml-1">{c.stars}</span> : null}</td>
                    <td className="py-1.5 text-right font-mono">{c.coef?.toFixed(4)}</td>
                    <td className="py-1.5 text-right font-mono">{c.stdErr?.toFixed(4) ?? "—"}</td>
                    <td className="py-1.5 text-right font-mono">{c.tStat?.toFixed(2) ?? "—"}</td>
                    <td className="py-1.5 text-right font-mono">{c.pValue?.toFixed(4) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </UiCard>
      )}

      <UiCard className="p-4">
        <h2 className="text-sm font-medium mb-3 text-muted">Default Probabilities · sorted by 5Y risk</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-text-secondary border-b border-border text-xs">
                <th className="py-2 text-left">Country</th>
                <th className="py-2 text-right">1Y Prob</th>
                <th className="py-2 text-right">5Y Prob</th>
                <th className="py-2 text-center">Signal</th>
              </tr>
            </thead>
            <tbody>
              {countries.map((c) => (
                <tr key={c.iso3} className="border-b border-border/30 hover:bg-surface-alt/50">
                  <td className="py-1.5">
                    <span className="font-mono text-xs text-text-muted mr-2">{c.iso3}</span>
                    {c.name}
                  </td>
                  <td className="py-1.5 text-right font-mono">{(c.prob1y * 100).toFixed(1)}%</td>
                  <td className="py-1.5 text-right font-mono">{(c.prob5y * 100).toFixed(1)}%</td>
                  <td className="py-1.5 text-center">
                    <span className={`inline-block w-3 h-3 rounded-full ${
                      c.signal === "red" ? "bg-red-500" : c.signal === "yellow" ? "bg-amber-500" : "bg-green-500"
                    }`} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </UiCard>
    </div>
  );
}

export default function YieldPage() {
  return (
    <Suspense fallback={<div className="p-8 text-muted">Loading…</div>}>
      <YieldPageInner />
    </Suspense>
  );
}