"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { EarningsQualityData } from "@/lib/types";
import { Card, PageSkeleton, ToggleChip } from "@/components/ui";

const UNIVERSES: { key: "dow" | "ndx" | "sp500"; label: string }[] = [
  { key: "dow", label: "Dow 30" },
  { key: "ndx", label: "Nasdaq 100" },
  { key: "sp500", label: "S&P 500" },
];

function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="p-4">
      <div className="text-xs text-text-secondary">{label}</div>
      <div className="text-2xl font-bold mt-1">{value}</div>
      {sub && <div className="text-xs text-text-secondary mt-0.5">{sub}</div>}
    </Card>
  );
}

function fmtNum(v: number | null | undefined, digits = 3): string {
  return v != null ? v.toFixed(digits) : "—";
}

function fmtPct(v: number | null | undefined): string {
  return v != null ? `${v.toFixed(1)}%` : "—";
}

function qualityColor(v: number | null | undefined): string {
  if (v == null) return "";
  if (v >= 70) return "text-success";
  if (v <= 40) return "text-danger";
  return "";
}

export function EarningsQuality() {
  const [universe, setUniverse] = useState<"dow" | "ndx" | "sp500">("dow");
  const [data, setData] = useState<EarningsQualityData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .corporateEarningsQuality(universe)
      .then((d) => setData(d))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to fetch data"))
      .finally(() => setLoading(false));
  }, [universe]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-semibold mb-1">Earnings Quality &amp; Accruals Monitor</h2>
        <p className="text-xs text-text-secondary mb-3">
          Sloan (1996) accruals anomaly — firms with high accruals relative to cash flow tend to
          underperform. Lower accrual ratios, cash conversion ≥ 1, and modest NOA growth indicate
          higher-quality earnings.
        </p>
        <div className="flex gap-1.5">
          {UNIVERSES.map((u) => (
            <ToggleChip key={u.key} active={universe === u.key} onClick={() => setUniverse(u.key)}>
              {u.label}
            </ToggleChip>
          ))}
        </div>
      </div>

      {loading && <PageSkeleton text="Loading earnings quality data…" />}

      {!loading && (error || !data || !data.rows || data.rows.length === 0) && (
        <Card className="p-6 text-center text-sm text-text-secondary">
          {error || "No earnings quality data available for this universe."}
        </Card>
      )}

      {!loading && data && data.kpis && data.rows && data.rows.length > 0 && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <KpiCard label="Median Accrual Ratio" value={fmtNum(data.kpis.medianAccrual)} />
            <KpiCard label="Median Cash Conversion" value={fmtNum(data.kpis.medianCashConversion)} />
            <KpiCard label="% Flagged High-Accrual" value={fmtPct(data.kpis.pctFlagged)} />
            <KpiCard label="Universe Size" value={String(data.kpis.n)} sub={data.asOf ?? undefined} />
          </div>

          <div className="p-4 bg-surface border border-border rounded-lg shadow-sm overflow-x-auto">
            <h3 className="font-semibold text-sm mb-2">Constituent Detail</h3>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-text-secondary border-b border-border">
                  <th className="py-1.5 pr-3">Ticker</th>
                  <th className="py-1.5 pr-3">Sector</th>
                  <th className="py-1.5 pr-3 text-right">Accrual Ratio</th>
                  <th className="py-1.5 pr-3 text-right">Cash Conversion</th>
                  <th className="py-1.5 pr-3 text-right">NOA Growth</th>
                  <th className="py-1.5 pr-3 text-right">Quality Score</th>
                  <th className="py-1.5 text-right">Flag</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.ticker} className="border-b border-border/50">
                    <td className="py-1.5 pr-3 font-medium">{r.ticker}</td>
                    <td className="py-1.5 pr-3 text-text-secondary">{r.sector ?? "—"}</td>
                    <td className="py-1.5 pr-3 text-right">{fmtNum(r.accrualRatio)}</td>
                    <td className="py-1.5 pr-3 text-right">{fmtNum(r.cashConversion)}</td>
                    <td className="py-1.5 pr-3 text-right">{fmtNum(r.noaGrowth)}</td>
                    <td className={`py-1.5 pr-3 text-right font-medium ${qualityColor(r.qualityScore)}`}>
                      {r.qualityScore != null ? r.qualityScore.toFixed(1) : "—"}
                    </td>
                    <td className="py-1.5 text-right">
                      {r.flag ? (
                        <span className="px-1.5 py-0.5 rounded bg-danger/20 text-danger text-[10px] font-semibold">
                          ⚠ FLAG
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
