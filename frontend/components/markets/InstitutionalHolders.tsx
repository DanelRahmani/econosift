"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Holders13FResponse, Holder13F } from "@/lib/types";
import { Card } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { useRefreshNonce } from "@/lib/refresh";

function fmt(v: number | null, decimals = 0): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`;
  if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(0)}M`;
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return v.toFixed(decimals);
}

function fmtShares(v: number | null): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return v.toFixed(0);
}

function ChangeCell({ v, pct }: { v: number | null; pct: number | null }) {
  if (v == null && pct == null) return <td className="py-2 pr-4 text-right text-text-secondary" data-prov="change">—</td>;
  const isPos = (pct ?? v ?? 0) >= 0;
  const arrow = isPos ? "▲" : "▼";
  const color = isPos ? "text-success" : "text-danger";
  return (
    <td className={`py-2 pr-4 text-right font-mono text-sm ${color}`} data-prov="change">
      {arrow} {fmtShares(v != null ? Math.abs(v) : null)}{pct != null ? ` (${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%)` : " (new)"}
    </td>
  );
}

export function InstitutionalHolders({ ticker }: { ticker: string }) {
  const [data, setData] = useState<Holders13FResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadingPrev, setLoadingPrev] = useState(false);
  const [prevError, setPrevError] = useState<string | null>(null);
  const scope = useSourceScope(provOf(data));

  // `silent` re-fetches (polling the previous-quarter download) keep the table on screen.
  const load = useCallback((silent: boolean) => {
    if (!silent) setLoading(true);
    setError(null);
    api
      .market13f(ticker)
      .then((d) => {
        setError(d.error ?? null);
        setData(d);
      })
      .catch(() => setError("Failed to load institutional holders"))
      .finally(() => setLoading(false));
  }, [ticker]);

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    if (ticker) load(false);
  }, [load, refreshNonce]);

  // While the previous quarter downloads, check back every 15 s.
  useEffect(() => {
    if (!data?.change?.loading) return;
    const id = setTimeout(() => load(true), 15_000);
    return () => clearTimeout(id);
  }, [data, load]);

  // 🟡 the ~100 MB download runs only when asked (P2-37).
  async function loadPrevious() {
    setLoadingPrev(true);
    setPrevError(null);
    try {
      const r = await api.market13fLoadPrevious();
      if (r.error) setPrevError(r.error);
      else load(true);
    } catch {
      setPrevError("Could not start the download");
    } finally {
      setLoadingPrev(false);
    }
  }

  return (
    <Card className="p-4" {...scope} data-prov-ctx={ticker}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">Institutional Holders (13F)</h3>
        <span className="text-xs bg-warning/20 text-warning px-2 py-0.5 rounded">
          45-day reporting lag
        </span>
      </div>

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-8 animate-pulse bg-surface-alt rounded" />
          ))}
        </div>
      ) : error ? (
        <p className="text-text-secondary text-sm">{error}</p>
      ) : !data || data.holders.length === 0 ? (
        <p className="text-text-secondary text-sm">No 13F data available for {ticker}.</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-text-secondary border-b border-border">
                  <th className="pb-2 pr-4">Fund</th>
                  <th className="pb-2 pr-4 text-right">Shares</th>
                  <th className="pb-2 pr-4 text-right">Value</th>
                  <th className="pb-2 pr-4 text-right" title="13F shares ÷ shares outstanding">% Shs Out</th>
                  <th className="pb-2 text-right">QoQ Change</th>
                </tr>
              </thead>
              <tbody>
                {data.holders.map((h: Holder13F, i: number) => (
                  <tr
                    key={i}
                    className="border-b border-border/40 hover:bg-surface-alt/30 transition-colors"
                    data-prov-ctx={h.name}
                  >
                    <td className="py-2 pr-4 font-medium">{h.name}</td>
                    <td className="py-2 pr-4 text-right font-mono">
                      {fmtShares(h.shares)}
                    </td>
                    <td className="py-2 pr-4 text-right font-mono">
                      {h.value != null ? fmt(h.value) : "—"}
                    </td>
                    <td className="py-2 pr-4 text-right" data-prov="pctFloat">
                      {h.pctFloat != null ? `${h.pctFloat.toFixed(2)}%` : "—"}
                    </td>
                    <ChangeCell v={h.changeShares} pct={h.changePct} />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.asOf && (
            <p className="text-xs text-text-secondary mt-3">
              Quarter ending {data.asOf} · {data.reportingLag}
              {data.filers != null && data.totalShares != null &&
                ` · ${data.filers.toLocaleString()} filers hold ${fmtShares(data.totalShares)} shares`}
            </p>
          )}
          {data.change && (
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-text-secondary">
              {data.change.available ? (
                <span>QoQ change vs the quarter ending {data.change.previousAsOf}</span>
              ) : data.change.loading ? (
                <span role="status">Downloading the previous quarter&rsquo;s 13F data set — about a minute or two…</span>
              ) : (
                <>
                  <span>QoQ change: n/a — {data.change.reason}</span>
                  {data.change.canLoad && (
                    <button type="button" className="btn px-2.5 py-1 text-xs" onClick={loadPrevious} disabled={loadingPrev}>
                      {loadingPrev ? "Starting…" : "🟡 Load previous quarter (~100 MB)"}
                    </button>
                  )}
                </>
              )}
              {prevError && <span className="text-danger">{prevError}</span>}
            </div>
          )}
        </>
      )}
    </Card>
  );
}
