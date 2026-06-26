"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PolicyDivergenceTable } from "@/components/policy/PolicyDivergenceTable";

function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-surface rounded-lg p-4 border border-border">
      <div className="text-xs text-muted mb-1">{label}</div>
      <div className="text-xl font-semibold">{value}</div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
    </div>
  );
}

export default function PolicyPage() {
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
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Global Policy Tracker</h1>

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
