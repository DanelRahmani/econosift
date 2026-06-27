"use client";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PolicyDivergenceTable } from "@/components/policy/PolicyDivergenceTable";
import { SovereignSpreadTable } from "@/components/sovereign/SovereignSpreadTable";
import { CentralBanksTab } from "@/components/macro/CentralBanksTab";

// ─── Shared KPI card ────────────────────────────────────────────────
function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-surface rounded-lg p-4 border border-border">
      <div className="text-xs text-muted mb-1">{label}</div>
      <div className="text-xl font-semibold">{value}</div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
    </div>
  );
}

// ─── Tab definitions ────────────────────────────────────────────────
const TABS = [
  { id: "policy", label: "Policy Tracker" },
  { id: "sovereign", label: "Sovereign Risk" },
  { id: "centralbanks", label: "Central Banks" },
] as const;
type TabId = (typeof TABS)[number]["id"];

function resolveTab(param: string | null): TabId {
  if (param && TABS.some((t) => t.id === param)) return param as TabId;
  return "policy";
}

// ─── Policy Tracker tab ─────────────────────────────────────────────
function PolicyTrackerTab() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["policyTracker"],
    queryFn: api.policyTracker,
  });

  if (isLoading) return <div className="p-8 text-muted">Loading policy data…</div>;
  if (error || !data) return <div className="p-8 text-red-400">Failed to load policy data.</div>;

  const { divergence, carry_differentials } = data;
  const fed = divergence.find((d) => d.cb === "Fed");
  const tightening = divergence.filter((d) => d.stance === "tightening")[0];
  const easing = divergence.filter((d) => d.stance === "easing").at(-1);
  const maxCarryEntry = Object.entries(carry_differentials)
    .filter(([, v]) => v !== null)
    .sort(([, a], [, b]) => Math.abs(b!) - Math.abs(a!))[0];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Fed Funds Rate"
          value={fed?.current_rate != null ? `${fed.current_rate.toFixed(2)}%` : "N/A"}
          sub={fed ? `${fed.stance.replace("_", " ")} (12M: ${(fed.change_12m ?? 0).toFixed(2)}%)` : undefined}
        />
        <KpiCard
          label="Most Tightening"
          value={tightening?.cb ?? "None"}
          sub={tightening ? `+${(tightening.change_12m ?? 0).toFixed(2)}% (12M)` : undefined}
        />
        <KpiCard
          label="Most Easing"
          value={easing?.cb ?? "None"}
          sub={easing ? `${(easing.change_12m ?? 0).toFixed(2)}% (12M)` : undefined}
        />
        <KpiCard
          label="Max Carry Differential"
          value={maxCarryEntry ? maxCarryEntry[0] : "N/A"}
          sub={maxCarryEntry && maxCarryEntry[1] != null ? `${maxCarryEntry[1].toFixed(2)}%` : undefined}
        />
      </div>

      <div className="bg-surface rounded-lg p-4 border border-border">
        <h2 className="text-sm font-medium mb-4 text-muted">Policy Rate Divergence — All Central Banks</h2>
        <PolicyDivergenceTable entries={divergence} />
      </div>

      <div className="bg-surface rounded-lg p-4 border border-border">
        <h2 className="text-sm font-medium mb-3 text-muted">G10 Carry Differentials vs USD</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {Object.entries(carry_differentials).map(([pair, val]) => (
            <div key={pair} className="flex justify-between px-3 py-2 rounded bg-background border border-border/50">
              <span className="text-sm">{pair}</span>
              <span className={`text-sm font-medium ${(val ?? 0) > 0 ? "text-red-400" : "text-green-400"}`}>
                {val != null ? `${val > 0 ? "+" : ""}${val.toFixed(2)}%` : "N/A"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Sovereign Risk tab ─────────────────────────────────────────────
function SovereignRiskTab() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["sovereignRisk"],
    queryFn: api.sovereignRisk,
  });

  if (isLoading) return <div className="p-8 text-muted">Loading sovereign risk data…</div>;
  if (error || !data) return <div className="p-8 text-red-400">Failed to load sovereign data.</div>;

  const { countries, top_risk, bottom_risk } = data;
  const redCount = countries.filter((c) => c.signal === "red").length;
  const riskiest = top_risk[0];
  const safest = bottom_risk[bottom_risk.length - 1];
  const avgSpread =
    countries.reduce((s, c) => s + (c.spread_vs_us ?? 0), 0) / (countries.length || 1);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Highest Risk"
          value={riskiest?.name ?? "N/A"}
          sub={riskiest ? `Score: ${riskiest.composite_score.toFixed(1)}` : undefined}
        />
        <KpiCard
          label="Lowest Risk"
          value={safest?.name ?? "N/A"}
          sub={safest ? `Score: ${safest.composite_score.toFixed(1)}` : undefined}
        />
        <KpiCard label="Avg Spread vs US" value={`${avgSpread.toFixed(2)}%`} />
        <KpiCard label="Red-Signal Countries" value={String(redCount)} />
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-surface rounded-lg p-4 border border-red-500/30">
          <h2 className="text-sm font-medium mb-3 text-red-400">Top 5 Riskiest</h2>
          <SovereignSpreadTable countries={top_risk} />
        </div>
        <div className="bg-surface rounded-lg p-4 border border-green-500/30">
          <h2 className="text-sm font-medium mb-3 text-green-400">Top 5 Safest</h2>
          <SovereignSpreadTable countries={bottom_risk.slice().reverse()} />
        </div>
      </div>

      <div className="bg-surface rounded-lg p-4 border border-border">
        <h2 className="text-sm font-medium mb-4 text-muted">All Countries — Sovereign Risk</h2>
        <SovereignSpreadTable countries={countries} />
      </div>
    </div>
  );
}

// ─── Main page (wrapped in Suspense for useSearchParams) ──────────
function PolicyPageInner() {
  const searchParams = useSearchParams();
  const [tab, setTab] = useState<TabId>(resolveTab(searchParams.get("tab")));

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Policy &amp; Sovereign</h1>

      {/* Tab bar */}
      <div className="flex gap-0 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
              tab === t.id
                ? "border-accent text-accent"
                : "border-transparent text-text-secondary hover:text-text-primary"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "policy" && <PolicyTrackerTab />}
      {tab === "sovereign" && <SovereignRiskTab />}
      {tab === "centralbanks" && <CentralBanksTab />}
    </div>
  );
}

export default function PolicyPage() {
  return (
    <Suspense fallback={<div className="p-8 text-muted">Loading…</div>}>
      <PolicyPageInner />
    </Suspense>
  );
}
