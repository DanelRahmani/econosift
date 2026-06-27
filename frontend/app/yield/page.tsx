"use client";
import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { RatesData } from "@/lib/types";
import { MultiCountryYieldChart } from "@/components/yield/MultiCountryYieldChart";
import { Card as UiCard, PageSkeleton } from "@/components/ui";
import { CHART_COLORS } from "@/lib/format";
import { PolicyDivergenceTable } from "@/components/policy/PolicyDivergenceTable";
import { SovereignSpreadTable } from "@/components/sovereign/SovereignSpreadTable";
import { CentralBanksTab } from "@/components/macro/CentralBanksTab";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, ReferenceLine,
} from "recharts";

const TABS = ["US Curve", "Foreign Spreads", "Real & Breakeven", "US Rates Detail", "Policy Tracker", "Sovereign Risk", "Central Banks"] as const;

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

export default function YieldPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("US Curve");
  const { data, isLoading, error } = useQuery({
    queryKey: ["yieldCurves"],
    queryFn: api.yieldCurves,
  });

  if (isLoading) return <div className="p-8 text-muted">Loading yield curve data…</div>;
  if (error || !data) return <div className="p-8 text-red-400">Failed to load yield data.</div>;

  const { us_curve, foreign_10y, real_yields, breakevens, term_premium } = data;
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
        <KpiCard label="Term Premium (ACM)" value={fmt(term_premium.current)} />
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border overflow-x-auto no-scrollbar">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm whitespace-nowrap border-b-2 -mb-px transition-colors ${
              tab === t ? "border-accent text-accent" : "border-transparent text-muted hover:text-foreground"
            }`}
          >
            {t}
          </button>
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
          <div className="mt-4 grid grid-cols-3 gap-3">
            {Object.entries(breakevens).map(([tenor, val]) => (
              <KpiCard key={tenor} label={`${tenor} Breakeven`} value={fmt(val)} />
            ))}
          </div>
        </div>
      )}

      {tab === "US Rates Detail" && <USRatesDetailTab />}

      {tab === "Policy Tracker" && <PolicyTrackerTab />}
      {tab === "Sovereign Risk" && <SovereignRiskTab />}
      {tab === "Central Banks" && <CentralBanksTab />}
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