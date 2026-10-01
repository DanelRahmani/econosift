"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CurrencyCrisisData } from "@/lib/types";
import { Card } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

function signalColor(s: string): string {
  if (s === "red") return "text-danger";
  if (s === "yellow") return "text-warning";
  if (s === "green") return "text-success";
  return "text-text-muted";
}

function SignalDot({ color }: { color: string }) {
  const bg = color === "red" ? "bg-danger" : color === "yellow" ? "bg-warning" : "bg-success";
  return <span className={`inline-block w-3 h-3 rounded-full ${bg} mr-2`} />;
}

export function CurrencyCrisisPanel() {
  const [data, setData] = useState<CurrencyCrisisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const scope = useSourceScope(provOf(data));

  useEffect(() => {
    api.stabilityCurrencyCrisis().then(setData).catch(() => setError(true)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="py-8 text-center text-muted">Loading crisis early warning data…</div>;
  if (error || !data) return <div className="py-8 text-center text-red-400">Failed to load data.</div>;

  const { summary, countries, methodology, source } = data;

  return (
    <div className="space-y-6" {...scope}>
      {/* Summary KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Card className="p-4" data-prov="summary">
          <div className="text-xs text-text-secondary">Red Alerts</div>
          <div className="text-2xl font-bold text-danger">{summary.redCount}</div>
          <div className="text-xs text-text-secondary mt-0.5">≥5 risk factors</div>
        </Card>
        <Card className="p-4" data-prov="summary">
          <div className="text-xs text-text-secondary">Yellow Warnings</div>
          <div className="text-2xl font-bold text-warning">{summary.yellowCount}</div>
          <div className="text-xs text-text-secondary mt-0.5">3-4 risk factors</div>
        </Card>
        <Card className="p-4" data-prov="summary">
          <div className="text-xs text-text-secondary">Green / Stable</div>
          <div className="text-2xl font-bold text-success">{summary.greenCount}</div>
          <div className="text-xs text-text-secondary mt-0.5">0-2 risk factors</div>
        </Card>
        <Card className="p-4" data-prov="summary">
          <div className="text-xs text-text-secondary">Countries</div>
          <div className="text-2xl font-bold">{summary.totalCountries}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-text-secondary">Methodology</div>
          <div className="text-sm mt-1">{methodology}</div>
          <div className="text-xs text-text-secondary mt-1">Source: {source}</div>
        </Card>
      </div>

      {/* Country Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {countries.map((c) => (
          <Card key={c.iso2} data-prov={`countries.${c.iso2}`} data-prov-ctx={c.name} className={`p-4 border-l-4 ${
            c.signal === "red" ? "border-l-danger" : c.signal === "yellow" ? "border-l-warning" : "border-l-success"
          }`}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold">{c.name}</h3>
              <SignalDot color={c.signal} />
            </div>
            <div className="text-xs text-text-secondary mb-2">
              Score: {c.compositeScore}/{c.maxScore ?? 6} flags
            </div>
            <div className="grid grid-cols-3 gap-1 text-xs">
              <div data-prov={`countries.${c.iso2}.kpis.currentAccount`} className={signalColor(c.kpis.currentAccount != null && c.kpis.currentAccount < -5 ? "red" : "")}>
                CA: {c.kpis.currentAccount != null ? `${c.kpis.currentAccount.toFixed(1)}%` : "N/A"}
              </div>
              <div data-prov={`countries.${c.iso2}.kpis.inflation`} className={signalColor(c.kpis.inflation != null && c.kpis.inflation > 10 ? "red" : "")}>
                CPI: {c.kpis.inflation != null ? `${c.kpis.inflation.toFixed(1)}%` : "N/A"}
              </div>
              <div data-prov={`countries.${c.iso2}.kpis.shortTermDebt`} className={signalColor(c.kpis.shortTermDebt != null && c.kpis.shortTermDebt > 15 ? "red" : "")}>
                ST Debt: {c.kpis.shortTermDebt != null ? `${c.kpis.shortTermDebt.toFixed(0)}%` : "N/A"}
              </div>
              <div data-prov={`countries.${c.iso2}.kpis.debtGdp`} className={signalColor(c.kpis.debtGdp != null && c.kpis.debtGdp > 90 ? "red" : "")}>
                Debt/GDP: {c.kpis.debtGdp != null ? `${c.kpis.debtGdp.toFixed(0)}%` : "N/A"}
              </div>
              <div data-prov={`countries.${c.iso2}.kpis.reservesDecline`} className={signalColor(c.kpis.reservesDecline != null && c.kpis.reservesDecline > 10 ? "red" : "")}>
                Reserves Δ: {c.kpis.reservesDecline != null ? `${c.kpis.reservesDecline.toFixed(0)}%` : "N/A"}
              </div>
              <div data-prov={`countries.${c.iso2}.kpis.fxOvervaluation`} className={signalColor(c.kpis.fxOvervaluation != null && c.kpis.fxOvervaluation > 15 ? "red" : "")}>
                FX Overval: {c.kpis.fxOvervaluation != null ? `${c.kpis.fxOvervaluation.toFixed(0)}%` : "N/A"}
              </div>
            </div>
            {c.factors.length > 0 && (
              <div className="mt-2 text-xs text-warning">
                {c.factors.join(" · ")}
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
