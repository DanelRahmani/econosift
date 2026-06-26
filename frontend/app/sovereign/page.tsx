"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { SovereignSpreadTable } from "@/components/sovereign/SovereignSpreadTable";

function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-surface rounded-lg p-4 border border-border">
      <div className="text-xs text-muted mb-1">{label}</div>
      <div className="text-xl font-semibold">{value}</div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
    </div>
  );
}

export default function SovereignPage() {
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
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Sovereign Risk Dashboard</h1>

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
        <KpiCard
          label="Avg Spread vs US"
          value={`${avgSpread.toFixed(2)}%`}
        />
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
