"use client";
import { Suspense, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useUrlState } from "@/lib/useUrlState";
import { PolicyDivergenceTable } from "@/components/policy/PolicyDivergenceTable";
import { SovereignSpreadTable } from "@/components/sovereign/SovereignSpreadTable";
import { CentralBanksTab } from "@/components/macro/CentralBanksTab";
import { TabButton } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { POLICY_TABS } from "@/lib/pageTabs";
import { useKeyboardShortcuts, tabKeys } from "@/lib/useKeyboardShortcuts";

// ─── Shared KPI card ────────────────────────────────────────────────
function KpiCard({ label, value, sub, prov }: { label: string; value: string; sub?: string; prov?: string }) {
  return (
    <div className="bg-surface rounded-lg p-4 border border-border" data-prov={prov}>
      <div className="text-xs text-text-muted mb-1">{label}</div>
      <div className="text-xl font-semibold">{value}</div>
      {sub && <div className="text-xs text-text-muted mt-1">{sub}</div>}
    </div>
  );
}

// ─── Tab definitions ────────────────────────────────────────────────
const TABS = POLICY_TABS;
type TabId = (typeof TABS)[number]["id"];

function resolveTab(param: string): TabId {
  if (param && TABS.some((t) => t.id === param)) return param as TabId;
  return "policy";
}

// ─── Policy Tracker tab ─────────────────────────────────────────────
function PolicyTrackerTab() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["policyTracker"],
    queryFn: api.policyTracker,
  });
  const scope = useSourceScope(provOf(data));

  if (isLoading) return <div className="p-8 text-text-muted">Loading policy data…</div>;
  if (error || !data) return <div className="p-8 text-red-400">Failed to load policy data.</div>;

  const { divergence, carry_differentials } = data;
  const fed = divergence.find((d) => d.cb === "Fed");
  const tightening = divergence.filter((d) => d.stance === "tightening")[0];
  const easing = divergence.filter((d) => d.stance === "easing").at(-1);
  const maxCarryEntry = Object.entries(carry_differentials)
    .filter(([, v]) => v !== null)
    .sort(([, a], [, b]) => Math.abs(b!) - Math.abs(a!))[0];

  return (
    <div className="space-y-6" {...scope}>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          prov="divergence.Fed"
          label="Fed Funds Rate"
          value={fed?.current_rate != null ? `${fed.current_rate.toFixed(2)}%` : "N/A"}
          sub={fed ? `${fed.stance.replace("_", " ")} (12M: ${(fed.change_12m ?? 0).toFixed(2)}%)` : undefined}
        />
        <KpiCard
          prov={tightening ? `divergence.${tightening.cb}` : undefined}
          label="Most Tightening"
          value={tightening?.cb ?? "None"}
          sub={tightening ? `+${(tightening.change_12m ?? 0).toFixed(2)}% (12M)` : undefined}
        />
        <KpiCard
          prov={easing ? `divergence.${easing.cb}` : undefined}
          label="Most Easing"
          value={easing?.cb ?? "None"}
          sub={easing ? `${(easing.change_12m ?? 0).toFixed(2)}% (12M)` : undefined}
        />
        <KpiCard
          prov={maxCarryEntry ? `carry_differentials.${maxCarryEntry[0]}` : undefined}
          label="Max Carry Differential"
          value={maxCarryEntry ? maxCarryEntry[0] : "N/A"}
          sub={maxCarryEntry && maxCarryEntry[1] != null ? `${maxCarryEntry[1].toFixed(2)}%` : undefined}
        />
      </div>

      <div className="bg-surface rounded-lg p-4 border border-border">
        <h2 className="text-sm font-medium mb-4 text-text-muted">Policy Rate Divergence — All Central Banks</h2>
        <PolicyDivergenceTable entries={divergence} />
      </div>

      <div className="bg-surface rounded-lg p-4 border border-border">
        <h2 className="text-sm font-medium mb-3 text-text-muted">G10 Carry Differentials vs USD</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {Object.entries(carry_differentials).map(([pair, val]) => (
            <div key={pair} className="flex justify-between px-3 py-2 rounded bg-background border border-border/50" data-prov={`carry_differentials.${pair}`} data-prov-ctx={pair}>
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
function DefaultRiskTab() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["sovereignDefault"],
    queryFn: api.sovereignDefaultProb,
  });
  const scope = useSourceScope(provOf(data));

  if (isLoading) return <div className="p-8 text-text-muted">Computing sovereign risk scores…</div>;
  if (error || !data) return <div className="p-8 text-red-400">Failed to load default model.</div>;
  if (data.error) return <div className="p-8 text-amber-400">{data.error}</div>;

  const { model, countries } = data;
  const redCount = countries.filter((c) => c.signal === "red").length;
  const yellowCount = countries.filter((c) => c.signal === "yellow").length;
  const greenCount = countries.filter((c) => c.signal === "green").length;

  return (
    <div className="space-y-6" {...scope}>
      {/* Summary KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          prov="countries"
          label="Countries Analyzed"
          value={String(countries.length)}
        />
        <KpiCard
          prov="countries"
          label="High Risk (Red)"
          value={String(redCount)}
          sub="score ≥ 20"
        />
        <KpiCard
          prov="countries"
          label="Medium Risk (Yellow)"
          value={String(yellowCount)}
          sub="score 5–20"
        />
        <KpiCard
          prov="countries"
          label="Low Risk (Green)"
          value={String(greenCount)}
          sub="score < 5"
        />
      </div>

      {/* Model Summary */}
      {model && (
        <div className="bg-surface rounded-lg p-4 border border-border" data-prov="model">
          <h2 className="text-sm font-medium mb-3 text-text-muted">Model Summary</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
            <div>
              <div className="text-xs text-text-muted">Pseudo R²</div>
              <div className="text-lg font-mono">{model.pseudoR2?.toFixed(3) ?? "—"}</div>
            </div>
            <div>
              <div className="text-xs text-text-muted">Observations</div>
              <div className="text-lg font-mono">{model.nObs}</div>
            </div>
            <div>
              <div className="text-xs text-text-muted">Converged</div>
              <div className={`text-lg ${model.converged ? "text-green-400" : "text-red-400"}`}>
                {model.converged ? "Yes" : "No"}
              </div>
            </div>
            <div>
              <div className="text-xs text-text-muted">Source</div>
              <div className="text-xs font-mono mt-1 text-text-muted">{data.source}</div>
            </div>
          </div>

          {/* Coefficients Table */}
          <h3 className="text-xs font-medium text-text-muted mb-2">Coefficients (Logistic Regression)</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-muted border-b border-border/50">
                  <th className="py-1.5 text-left font-medium">Predictor</th>
                  <th className="py-1.5 text-right font-medium">Coefficient</th>
                  <th className="py-1.5 text-right font-medium">Std Err</th>
                  <th className="py-1.5 text-right font-medium">t-Stat</th>
                  <th className="py-1.5 text-right font-medium">p-Value</th>
                </tr>
              </thead>
              <tbody>
                {model.coefficients.map((c) => (
                  <tr key={c.name} className="border-b border-border/30">
                    <td className="py-1.5 font-mono">{c.name}{c.stars ? <span className="text-accent ml-1">{c.stars}</span> : null}</td>
                    <td className="py-1.5 text-right font-mono">{c.coef?.toFixed(4) ?? "—"}</td>
                    <td className="py-1.5 text-right font-mono">{c.stdErr?.toFixed(4) ?? "—"}</td>
                    <td className="py-1.5 text-right font-mono">{c.tStat?.toFixed(2) ?? "—"}</td>
                    <td className="py-1.5 text-right font-mono">{c.pValue?.toFixed(4) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-text-muted mt-2">*** p&lt;0.01 &nbsp; ** p&lt;0.05 &nbsp; * p&lt;0.10</p>
        </div>
      )}

      {/* Country risk score table */}
      <div className="bg-surface rounded-lg p-4 border border-border">
        <h2 className="text-sm font-medium mb-1 text-text-muted">
          Relative Default Risk (sorted by score)
        </h2>
        <p className="text-xs text-text-muted mb-3">
          Score 0–100 from a weakly calibrated logistic model (few post-2000 default episodes in its training set).
          Read it as a ranking, not a default probability.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-text-secondary border-b border-border text-xs">
                <th className="py-2 text-right">Rank</th>
                <th className="py-2 text-left pl-3">Country</th>
                <th className="py-2 text-right">Risk score</th>
                <th className="py-2 text-center">Signal</th>
              </tr>
            </thead>
            <tbody>
              {countries.map((c) => (
                <tr key={c.iso3} className="border-b border-border/30 hover:bg-surface-alt/50" data-prov="countries" data-prov-ctx={c.name}>
                  <td className="py-1.5 text-right font-mono">{c.rank}</td>
                  <td className="py-1.5 pl-3">
                    <span className="font-mono text-xs text-text-muted mr-2">{c.iso3}</span>
                    {c.name}
                  </td>
                  <td className="py-1.5 text-right font-mono">{c.score.toFixed(1)}</td>
                  <td className="py-1.5 text-center">
                    <span className={`inline-block w-3 h-3 rounded-full ${
                      c.signal === "red" ? "bg-red-500" :
                      c.signal === "yellow" ? "bg-amber-500" :
                      "bg-green-500"
                    }`} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
  const scope = useSourceScope(provOf(data));

  if (isLoading) return <div className="p-8 text-text-muted">Loading sovereign risk data…</div>;
  if (error || !data) return <div className="p-8 text-red-400">Failed to load sovereign data.</div>;

  const { countries, top_risk, bottom_risk } = data;
  const redCount = countries.filter((c) => c.signal === "red").length;
  const riskiest = top_risk[0];
  const safest = bottom_risk[bottom_risk.length - 1];
  const avgSpread =
    countries.reduce((s, c) => s + (c.spread_vs_us ?? 0), 0) / (countries.length || 1);

  return (
    <div className="space-y-6" {...scope}>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          prov={riskiest ? `countries.${riskiest.iso3}` : undefined}
          label="Highest Risk"
          value={riskiest?.name ?? "N/A"}
          sub={riskiest ? `Score: ${riskiest.composite_score.toFixed(1)}` : undefined}
        />
        <KpiCard
          prov={safest ? `countries.${safest.iso3}` : undefined}
          label="Lowest Risk"
          value={safest?.name ?? "N/A"}
          sub={safest ? `Score: ${safest.composite_score.toFixed(1)}` : undefined}
        />
        <KpiCard prov="countries" label="Avg Spread vs US" value={`${avgSpread.toFixed(2)}%`} />
        <KpiCard prov="countries" label="Red-Signal Countries" value={String(redCount)} />
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
        <h2 className="text-sm font-medium mb-4 text-text-muted">All Countries — Sovereign Risk</h2>
        <SovereignSpreadTable countries={countries} />
      </div>
    </div>
  );
}

// ─── Main page (wrapped in Suspense for useSearchParams) ──────────
function PolicyPageInner() {
  const [urlState, setUrlState] = useUrlState({ tab: "policy" });
  const tab = resolveTab(urlState.tab);
  useKeyboardShortcuts({ onTabSwitch: tabKeys(TABS, (t) => setUrlState({ tab: t.id })) }); // P2-07

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Policy &amp; Sovereign</h1>

      {/* Tab bar */}
      <div className="flex gap-0 border-b border-border">
        {TABS.map((t) => (
          <TabButton key={t.id} active={tab === t.id} onClick={() => setUrlState({ tab: t.id })}>
            {t.label}
          </TabButton>
        ))}
      </div>

      {tab === "policy" && <PolicyTrackerTab />}
      {tab === "sovereign" && <SovereignRiskTab />}
      {tab === "centralbanks" && <CentralBanksTab />}
      {tab === "default" && <DefaultRiskTab />}
    </div>
  );
}

export default function PolicyPage() {
  return (
    <Suspense fallback={<div className="p-8 text-text-muted">Loading…</div>}>
      <PolicyPageInner />
    </Suspense>
  );
}
