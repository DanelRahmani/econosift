"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { CrossborderData, FactbookCountry } from "@/lib/types";
import { Card, PageSkeleton } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

function fmtUsd(v: number): string {
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  return `$${v.toFixed(0)}`;
}

export default function CrossborderPage() {
  const [data, setData] = useState<CrossborderData | null>(null);
  const [countries, setCountries] = useState<FactbookCountry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const scope = useSourceScope(provOf(data));

  useEffect(() => {
    Promise.all([api.crossborderClaims(), api.factbookCountries()])
      .then(([d, c]) => { setData(d); setCountries(c); })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  // Build lookup: iso3 → {flag, name} and iso2 → {flag, name}
  const flagMap = useMemo(() => {
    const m: Record<string, { flag: string; name: string }> = {};
    countries.forEach((c) => {
      m[c.iso2] = { flag: c.flag, name: c.name };
      if (c.iso3) m[c.iso3] = { flag: c.flag, name: c.name };
    });
    return m;
  }, [countries]);

  function flagFor(code: string) {
    return flagMap[code]?.flag || "";
  }

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Cross-Border Finance</h1>
          <p className="text-sm text-text-secondary mt-1">
            BIS Locational Banking Statistics — international banking claims
          </p>
        </div>
        <PageSkeleton text="Loading BIS cross-border claims… (may take up to 2 min on first load)" />
      </div>
    );
  }

  if (error || !data || data.claims.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold text-text-primary">Cross-Border Finance</h1>
        <p className="text-sm text-text-secondary mt-1">
          BIS Locational Banking Statistics
        </p>
        <div className="text-text-secondary text-sm py-8 text-center">
          Cross-border claims data unavailable — BIS data may be temporarily inaccessible.
        </div>
      </div>
    );
  }

  const { claims, source } = data;

  // Build unique country lists
  const creditors = [...new Set(claims.map((c) => c.creditor))].sort();
  const debtors = [...new Set(claims.map((c) => c.debtor))].sort();
  const allCountries = [...new Set([...creditors, ...debtors])].sort();

  // Aggregate by creditor and debtor for side tables
  const creditorTotals: Record<string, number> = {};
  const debtorTotals: Record<string, number> = {};
  claims.forEach((c) => {
    creditorTotals[c.creditor] = (creditorTotals[c.creditor] || 0) + c.value_usd;
    debtorTotals[c.debtor] = (debtorTotals[c.debtor] || 0) + c.value_usd;
  });

  const topCreditors = Object.entries(creditorTotals)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 10);
  const topDebtors = Object.entries(debtorTotals)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 10);

  // Find max value for color scaling
  const maxVal = Math.max(...claims.map((c) => c.value_usd));

  // Build lookup for matrix
  const lookup: Record<string, Record<string, number>> = {};
  claims.forEach((c) => {
    if (!lookup[c.creditor]) lookup[c.creditor] = {};
    lookup[c.creditor][c.debtor] = c.value_usd;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6" {...scope}>
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Cross-Border Finance</h1>
        <p className="text-sm text-text-secondary mt-1">
          International banking claims · {source}
          {data.asOf && ` · ${data.asOf}`}
        </p>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="p-4" data-prov="totalUsd">
          <div className="text-xs text-text-secondary">Global Cross-Border Claims</div>
          <div className="text-2xl font-bold mt-1">{data.totalUsd != null ? fmtUsd(data.totalUsd) : "—"}</div>
        </Card>
        <Card className="p-4" data-prov="pairCount">
          <div className="text-xs text-text-secondary">Largest Pairs Shown</div>
          <div className="text-2xl font-bold mt-1">
            {claims.length}
            {data.pairCount != null && <span className="text-sm font-normal text-text-muted"> of {data.pairCount}</span>}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-text-secondary">Creditor Countries</div>
          <div className="text-2xl font-bold mt-1">{creditors.length}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-text-secondary">Debtor Countries</div>
          <div className="text-2xl font-bold mt-1">{debtors.length}</div>
        </Card>
      </div>

      {/* Adjacency Matrix Heatmap */}
      <Card className="p-4 overflow-x-auto">
        <h3 className="font-semibold mb-3 text-text-primary">Claims Heatmap (Creditors → Debtors)</h3>
        <div className="text-xs text-text-muted mb-3">
          Rows = creditor countries (lenders) · Columns = debtor countries (borrowers) · largest {claims.length} pairs only
        </div>
        <div className="inline-block min-w-max">
          {/* Header row */}
          <div className="flex">
            <div className="w-12 shrink-0" />
            {debtors.map((d) => (
              <div key={d} className="w-14 text-center text-[10px] font-medium text-text-muted px-1" title={flagMap[d]?.name || d}>
                <span className="text-sm">{flagFor(d)}</span><br />{d}
              </div>
            ))}
          </div>
          {/* Data rows */}
          {creditors.map((cred) => (
            <div key={cred} className="flex items-center">
              <div className="w-12 shrink-0 text-right pr-2 text-[10px] font-medium text-text-muted" title={flagMap[cred]?.name || cred}>
                <span className="text-sm">{flagFor(cred)}</span>&nbsp;{cred}
              </div>
              {debtors.map((deb) => {
                const val = lookup[cred]?.[deb];
                const intensity = val ? Math.min(val / maxVal, 1) : 0;
                const r = Math.round(59 + intensity * 180);
                const g = Math.round(130 - intensity * 100);
                const b = Math.round(246 - intensity * 200);
                return (
                  <div
                    key={deb}
                    className="w-14 h-8 flex items-center justify-center text-[9px] font-mono border border-border/30"
                    style={{ backgroundColor: val ? `rgb(${r},${g},${b})` : "transparent" }}
                    title={val ? `${cred} → ${deb}: ${fmtUsd(val)}` : ""}
                  >
                    {val ? (val >= 1e9 ? `${(val / 1e9).toFixed(0)}B` : `${(val / 1e6).toFixed(0)}M`) : "·"}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </Card>

      {/* Top Creditors & Debtors side by side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="p-4">
          <h3 className="font-semibold mb-3 text-text-primary">Top Creditors (Lenders)</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-text-secondary text-xs">
                <th className="py-2 text-left">#</th>
                <th className="py-2 text-left">Country</th>
                <th className="py-2 text-right">Claims (pairs shown)</th>
              </tr>
            </thead>
            <tbody>
              {topCreditors.map(([iso, total], i) => (
                <tr key={iso} className="border-b border-border/50">
                  <td className="py-1.5 text-text-muted text-xs">{i + 1}</td>
                  <td className="py-1.5 font-mono"><span className="mr-1">{flagFor(iso)}</span>{flagMap[iso]?.name || iso}</td>
                  <td className="py-1.5 text-right font-mono">{fmtUsd(total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card className="p-4">
          <h3 className="font-semibold mb-3 text-text-primary">Top Debtors (Borrowers)</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-text-secondary text-xs">
                <th className="py-2 text-left">#</th>
                <th className="py-2 text-left">Country</th>
                <th className="py-2 text-right">Owed (pairs shown)</th>
              </tr>
            </thead>
            <tbody>
              {topDebtors.map(([iso, total], i) => (
                <tr key={iso} className="border-b border-border/50">
                  <td className="py-1.5 text-text-muted text-xs">{i + 1}</td>
                  <td className="py-1.5 font-mono"><span className="mr-1">{flagFor(iso)}</span>{flagMap[iso]?.name || iso}</td>
                  <td className="py-1.5 text-right font-mono">{fmtUsd(total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      {/* Claim Detail Table */}
      <Card className="p-4">
        <h3 className="font-semibold mb-3 text-text-primary">Top Claims by Pair</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-text-secondary text-xs">
              <th className="py-2 text-left">#</th>
              <th className="py-2 text-left">Creditor</th>
              <th className="py-2 text-left">Debtor</th>
              <th className="py-2 text-right">Value (USD)</th>
            </tr>
          </thead>
          <tbody>
            {claims.slice(0, 20).map((c, i) => (
              <tr key={`${c.creditor}-${c.debtor}`} className="border-b border-border/50">
                <td className="py-1.5 text-text-muted text-xs">{i + 1}</td>
                <td className="py-1.5 font-mono"><span className="mr-1">{flagFor(c.creditor)}</span>{flagMap[c.creditor]?.name || c.creditor}</td>
                <td className="py-1.5 font-mono"><span className="mr-1">{flagFor(c.debtor)}</span>{flagMap[c.debtor]?.name || c.debtor}</td>
                <td className="py-1.5 text-right font-mono">{fmtUsd(c.value_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
