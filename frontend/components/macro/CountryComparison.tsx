"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SnapshotResponse, Country } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { fmtNum, fmtLarge } from "@/lib/format";
import { useRefreshNonce } from "@/lib/refresh";

const LABELS: Record<string, string> = {
  gdp_growth: "GDP Growth",
  inflation: "Inflation (CPI)",
  unemployment: "Unemployment",
  debt_gdp: "Govt Debt / GDP",
  current_account: "Current Account",
  gdp_per_capita: "GDP per Capita",
};

type Tone = "good" | "watch" | "warn" | "neutral";

// Traffic-light classification per indicator (configurable thresholds).
function classify(id: string, v: number): Tone {
  switch (id) {
    case "gdp_growth": return v >= 2 ? "good" : v >= 0 ? "watch" : "warn";
    case "inflation": return v >= 1 && v <= 3 ? "good" : (v < 0 || v > 6) ? "warn" : "watch";
    case "unemployment": return v < 5 ? "good" : v <= 8 ? "watch" : "warn";
    case "debt_gdp": return v < 60 ? "good" : v <= 100 ? "watch" : "warn";
    case "current_account": return v > 0 ? "good" : v >= -3 ? "watch" : "warn";
    default: return "neutral";
  }
}

const TONE_BG: Record<Tone, string> = {
  good: "bg-success/15 text-success",
  watch: "bg-warning/15 text-warning",
  warn: "bg-danger/15 text-danger",
  neutral: "bg-surface-alt text-text-primary",
};

function formatValue(id: string, unit: string, v: number): string {
  if (id === "gdp_per_capita") return `$${fmtLarge(v)}`;
  return `${fmtNum(v)}${unit === "%" ? "%" : ""}`;
}

export function CountryComparison({ selected, countries }: { selected: string[]; countries: Country[] }) {
  const [data, setData] = useState<SnapshotResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const cols = selected.slice(0, 4);
  const key = cols.join(",");
  const scope = useSourceScope(provOf(data));

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    if (!cols.length) { setData(null); return; }
    let live = true;
    setLoading(true);
    api.snapshot(key)
      .then((r) => live && setData(r))
      .catch(() => live && setData(null))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [key, refreshNonce]);

  const nameOf = (iso: string) => countries.find((c) => c.iso2 === iso)?.name ?? iso;

  return (
    <Card {...scope}>
      <h2 className="text-sm font-semibold mb-1 text-text-secondary">Country Comparison</h2>
      <p className="text-xs text-text-muted mb-4">
        Latest headline indicators · green = healthy, amber = watch, red = warning.
      </p>
      {loading && !data ? (
        <Skeleton className="h-56" />
      ) : !data ? (
        <div className="text-text-muted text-sm">No comparison data.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-text-secondary border-b border-border">
                <th className="text-left py-2 px-3 font-medium">Indicator</th>
                {cols.map((iso) => (
                  <th key={iso} className="text-right py-2 px-3 font-medium">{nameOf(iso)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.indicators.map((ind) => (
                <tr key={ind.id} className="border-b border-border/50" data-prov={`indicators.${ind.id}`} data-prov-ctx={LABELS[ind.id] ?? ind.id}>
                  <td className="py-2 px-3 text-text-secondary">{LABELS[ind.id] ?? ind.id}</td>
                  {cols.map((iso) => {
                    const entry = ind.values[iso];
                    if (!entry) return <td key={iso} className="py-2 px-3 text-right text-text-muted" data-prov-ctx={`${nameOf(iso)} · ${LABELS[ind.id] ?? ind.id}`}>—</td>;
                    const tone = classify(ind.id, entry.value);
                    return (
                      <td key={iso} className="py-1.5 px-3 text-right" data-prov-ctx={`${nameOf(iso)} · ${LABELS[ind.id] ?? ind.id} · ${entry.year}`}>
                        <span className={`inline-block px-2 py-0.5 rounded-md font-mono ${TONE_BG[tone]}`}
                          title={`as of ${entry.year}`}>
                          {formatValue(ind.id, ind.unit, entry.value)}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
