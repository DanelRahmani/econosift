"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { DividendAnalysisResponse } from "@/lib/types";
import { Card, PageSkeleton } from "@/components/ui";
import { TickerSearch } from "@/components/TickerSearch";
import { useUrlState } from "@/lib/useUrlState";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";

const GRID = "rgba(255,255,255,0.08)";

function KpiCard({ label, value, sub, color }: {
  label: string; value: string; sub?: string; color?: string;
}) {
  return (
    <Card className="p-4">
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${color ?? ""}`}>{value}</div>
      {sub && <div className="text-xs text-text-secondary mt-0.5">{sub}</div>}
    </Card>
  );
}

function DividendsPageInner() {
  const [urlState, setUrlState] = useUrlState({ ticker: "" });
  const ticker = urlState.ticker;
  const [data, setData] = useState<DividendAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  const fetchAnalysis = useCallback((t: string) => {
    const trimmed = t.trim().toUpperCase();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    setSearched(true);
    api
      .dividendAnalysis(trimmed)
      .then((d) => {
        if (d.error) setError(d.error);
        else setData(d);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (ticker) {
      fetchAnalysis(ticker);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (ticker.trim()) {
      setUrlState({ ticker: ticker.trim().toUpperCase() });
      fetchAnalysis(ticker);
    }
  };

  const annualData = data?.annualDividends
    ? Object.entries(data.annualDividends)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([year, val]) => ({ year, dividend: val }))
    : [];

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Dividend Analysis</h1>
        <p className="text-sm text-text-secondary mt-1">
          Dividend yield, growth rates, payout ratio, sustainability score, and DDM fair value estimation.
        </p>
      </div>

      <div className="flex gap-2 items-start">
        <TickerSearch
          value={ticker}
          onChange={(t) => {
            setUrlState({ ticker: t });
            fetchAnalysis(t);
          }}
          placeholder="Search company name or ticker (KO, JNJ, PG)…"
        />
        <button
          onClick={handleSubmit}
          disabled={loading || !ticker.trim()}
          className="px-6 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
        >
          {loading ? "Loading…" : "Analyze"}
        </button>
      </div>

      {loading && <PageSkeleton text={`Fetching dividend data for ${ticker}…`} />}

      {error && !loading && (
        <div className="text-danger text-sm py-4 text-center bg-danger/10 rounded-lg">{error}</div>
      )}

      {data && !loading && (
        <div className="space-y-6">
          <div className="flex items-baseline justify-between">
            <div>
              <h2 className="text-xl font-semibold">{data.name}</h2>
              <p className="text-sm text-text-secondary">{data.sector || ""}</p>
            </div>
            {data.price != null && (
              <div className="text-2xl font-bold">${data.price.toFixed(2)}</div>
            )}
          </div>

          {/* KPI Row */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            <KpiCard label="Dividend Yield" value={data.dividendYield != null ? `${data.dividendYield.toFixed(2)}%` : "—"} />
            <KpiCard label="5Y CAGR" value={data.cagr5y != null ? `${data.cagr5y.toFixed(1)}%` : "—"} />
            <KpiCard label="10Y CAGR" value={data.cagr10y != null ? `${data.cagr10y.toFixed(1)}%` : "—"} />
            <KpiCard label="Payout Ratio" value={data.payoutRatio != null ? `${(data.payoutRatio * 100).toFixed(0)}%` : "—"} />
            <KpiCard
              label="Consecutive Growth"
              value={`${data.consecutiveGrowthYears}y`}
              color={data.consecutiveGrowthYears >= 25 ? "text-success" : data.consecutiveGrowthYears >= 10 ? "text-warning" : ""}
            />
          </div>

          {/* Sustainability Score */}
          <Card className="p-4">
            <h3 className="font-semibold mb-1">Dividend Sustainability</h3>
            <div className="flex items-center gap-4">
              <div className={`text-4xl font-bold ${data.sustainabilityLabel === "Strong" ? "text-success" : data.sustainabilityLabel === "Adequate" ? "text-warning" : "text-danger"}`}>
                {data.sustainabilityScore}
              </div>
              <div>
                <div className={`text-lg font-semibold ${data.sustainabilityLabel === "Strong" ? "text-success" : data.sustainabilityLabel === "Adequate" ? "text-warning" : "text-danger"}`}>
                  {data.sustainabilityLabel}
                </div>
                <p className="text-xs text-text-secondary mt-1">
                  Based on payout ratio, FCF coverage, growth stability, and consecutive growth history.
                </p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 mt-4 text-sm">
              <div className="flex justify-between"><span className="text-text-secondary">EPS Payout</span><span>{data.payoutRatio != null ? `${(data.payoutRatio * 100).toFixed(1)}%` : "—"}</span></div>
              <div className="flex justify-between"><span className="text-text-secondary">FCF Payout</span><span>{data.fcfPayoutRatio != null ? `${(data.fcfPayoutRatio * 100).toFixed(1)}%` : "—"}</span></div>
            </div>
          </Card>

          {/* Annual Dividends Chart */}
          {annualData.length > 0 && (
            <Card className="p-4">
              <h3 className="font-semibold mb-1">Annual Dividends</h3>
              <p className="text-xs text-text-secondary mb-3">
                Total dividends paid per share per year
                {data.latestYear && ` · Latest: ${data.latestYear}`}
              </p>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={annualData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                  <XAxis dataKey="year" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                  <YAxis tickFormatter={(v) => `$${v.toFixed(1)}`} tick={{ fontSize: 11 }} />
                  <Tooltip
                    formatter={(v: number) => [`$${v.toFixed(4)}`, "Dividend"]}
                    contentStyle={{ backgroundColor: "var(--color-surface-alt)", border: "1px solid var(--color-border)", borderRadius: 8, fontSize: 12 }}
                  />
                  <Bar dataKey="dividend" fill="#10b981" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* DDM Fair Value */}
          {data.ddmFairValue != null && data.price != null && (
            <Card className="p-4">
              <h3 className="font-semibold mb-1">Gordon Growth DDM Fair Value</h3>
              <p className="text-xs text-text-secondary mb-3">
                Assumed discount rate: 9.5% · Growth rate: {data.ddmGrowthRate}% (capped 5Y CAGR, min 1%)
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-text-secondary">Current Price</div>
                  <div className="text-2xl font-bold">${data.price.toFixed(2)}</div>
                </div>
                <div>
                  <div className="text-xs text-text-secondary">DDM Fair Value</div>
                  <div className="text-2xl font-bold">${data.ddmFairValue.toFixed(2)}</div>
                </div>
                <div className="col-span-2">
                  <div className="text-xs text-text-secondary">Upside/Downside</div>
                  <div className={`text-xl font-bold ${(data.ddmUpsidePct ?? 0) >= 0 ? "text-success" : "text-danger"}`}>
                    {(data.ddmUpsidePct ?? 0) >= 0 ? "+" : ""}{data.ddmUpsidePct?.toFixed(1)}%
                  </div>
                </div>
              </div>
            </Card>
          )}

          {!data.ddmFairValue && (
            <div className="text-text-muted text-sm text-center py-4">
              DDM fair value not available — insufficient dividend history or growth data.
            </div>
          )}
        </div>
      )}

      {!loading && !data && !error && !searched && (
        <div className="text-text-secondary text-sm py-12 text-center space-y-2">
          <p className="text-lg">💰</p>
          <p>Enter a dividend-paying ticker to analyze.</p>
          <p className="text-xs">Try: KO, JNJ, PG, PEP, XOM</p>
        </div>
      )}
    </div>
  );
}

export default function DividendsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-muted">Loading…</div>}>
      <DividendsPageInner />
    </Suspense>
  );
}
