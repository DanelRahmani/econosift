"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { CorporateHealthResponse } from "@/lib/types";
import { Card, PageSkeleton } from "@/components/ui";
import { TickerSearch } from "@/components/TickerSearch";
import { useUrlState } from "@/lib/useUrlState";
import { EarningsQuality } from "@/components/corporate/EarningsQuality";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { useRefreshNonce } from "@/lib/refresh";

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

function fmtNum(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v.toFixed(2);
}

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function CorporatePageInner() {
  const [urlState, setUrlState] = useUrlState({ ticker: "" });
  const ticker = urlState.ticker;
  const [data, setData] = useState<CorporateHealthResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const scope = useSourceScope(provOf(data));

  const fetchHealth = useCallback((t: string) => {
    const trimmed = t.trim().toUpperCase();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    setSearched(true);
    api
      .corporateHealth(trimmed)
      .then((d) => {
        if (d.error) setError(d.error);
        else setData(d);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to fetch data"))
      .finally(() => setLoading(false));
  }, []);

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    if (ticker) {
      fetchHealth(ticker);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshNonce]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (ticker.trim()) {
      setUrlState({ ticker: ticker.trim().toUpperCase() });
      fetchHealth(ticker);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Corporate Health Monitor</h1>
        <p className="text-sm text-text-secondary mt-1">
          Altman Z-Score, Piotroski F-Score, and Beneish M-Score — bankruptcy risk, fundamental strength, and earnings manipulation detection.
        </p>
      </div>

      {/* Ticker Search */}
      <div className="flex gap-2 items-start">
        <TickerSearch
          value={ticker}
          onChange={(t) => {
            setUrlState({ ticker: t });
            fetchHealth(t);
          }}
          placeholder="Search company name or ticker (AAPL, TSLA, GE)…"
        />
        <button
          onClick={handleSubmit}
          disabled={loading || !ticker.trim()}
          className="px-6 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
        >
          {loading ? "Loading…" : "Analyze"}
        </button>
      </div>

      {/* Loading */}
      {loading && <PageSkeleton text={`Fetching corporate health data for ${ticker}…`} />}

      {/* Error */}
      {error && !loading && (
        <div className="text-danger text-sm py-4 text-center bg-danger/10 rounded-lg">
          {error}
        </div>
      )}

      {/* Results */}
      {data && !loading && (
        <div className="space-y-6" {...scope}>
          {/* Company header */}
          <div className="flex items-baseline justify-between">
            <div>
              <h2 className="text-xl font-semibold text-text-primary">{data.name}</h2>
              <p className="text-sm text-text-secondary">{data.sector}{data.industry ? ` · ${data.industry}` : ""}</p>
            </div>
            {data.price != null && (
              <div className="text-right" data-prov="price">
                <div className="text-2xl font-bold text-text-primary">${data.price.toFixed(2)}</div>
              </div>
            )}
          </div>

          {/* Altman Z-Score */}
          <Card className="p-6" data-prov="altmanZ">
            <h3 className="font-semibold text-lg mb-4">Altman Z-Score</h3>
            {data.altmanZ.isFinancial && (
              <p className="text-xs text-warning mb-3">⚠ {data.altmanZ.note || "Altman Z-Score is not applicable to financial firms."}</p>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Gauge */}
              <div className="flex flex-col items-center justify-center">
                <div className={`text-5xl font-bold ${data.altmanZ.zone === "Safe" ? "text-success" : data.altmanZ.zone === "Distress" ? "text-danger" : "text-warning"}`}>
                  {fmtNum(data.altmanZ.zScore)}
                </div>
                <div className={`mt-2 px-3 py-1 rounded-full text-sm font-semibold ${
                  data.altmanZ.zone === "Safe" ? "bg-success/20 text-success" :
                  data.altmanZ.zone === "Distress" ? "bg-danger/20 text-danger" :
                  "bg-warning/20 text-warning"
                }`}>
                  {data.altmanZ.zone}
                  {data.altmanZ.zone === "Safe" ? " (> 2.99)" :
                   data.altmanZ.zone === "Distress" ? " (< 1.81)" :
                   data.altmanZ.zone === "Grey" ? " (1.81–2.99)" : ""}
                </div>
              </div>
              {/* Component breakdown */}
              <div className="space-y-1.5">
                {[
                  { k: "x1_workingCapitalToAssets", label: "WC / Assets" },
                  { k: "x2_retainedEarningsToAssets", label: "Retained Earn. / Assets" },
                  { k: "x3_ebitToAssets", label: "EBIT / Assets" },
                  { k: "x4_marketValueToLiabilities", label: "Market Value / Liabilities" },
                  { k: "x5_salesToAssets", label: "Sales / Assets" },
                ].map(({ k, label }) => {
                  const v = data.altmanZ.components[k as keyof typeof data.altmanZ.components];
                  return (
                    <div key={k} className="flex justify-between text-sm">
                      <span className="text-text-secondary">{label}</span>
                      <span className="font-mono">{v != null ? v.toFixed(3) : "—"}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </Card>

          {/* Piotroski F-Score */}
          <Card className="p-6" data-prov="piotroski">
            <h3 className="font-semibold text-lg mb-4">Piotroski F-Score</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="flex flex-col items-center justify-center">
                <div className={`text-5xl font-bold ${data.piotroski.score >= 7 ? "text-success" : data.piotroski.score >= 4 ? "text-warning" : "text-danger"}`}>
                  {data.piotroski.score}<span className="text-2xl text-text-secondary">/{data.piotroski.maxScore}</span>
                </div>
                <div className={`mt-2 px-3 py-1 rounded-full text-sm font-semibold ${
                  data.piotroski.interpretation === "Strong" ? "bg-success/20 text-success" :
                  data.piotroski.interpretation === "Weak" ? "bg-danger/20 text-danger" :
                  "bg-warning/20 text-warning"
                }`}>
                  {data.piotroski.interpretation}
                </div>
              </div>
              <div className="space-y-1">
                {[
                  { k: "positiveNetIncome", label: "Positive Net Income" },
                  { k: "positiveOperatingCF", label: "Positive Operating Cash Flow" },
                  { k: "roaIncreasing", label: "ROA Increasing" },
                  { k: "operatingCFGreaterThanNI", label: "Operating CF > Net Income" },
                  { k: "decreasingLeverage", label: "Decreasing Leverage" },
                  { k: "increasingCurrentRatio", label: "Increasing Current Ratio" },
                  { k: "noShareDilution", label: "No Share Dilution" },
                  { k: "increasingGrossMargin", label: "Increasing Gross Margin" },
                  { k: "increasingAssetTurnover", label: "Increasing Asset Turnover" },
                ].map(({ k, label }) => {
                  const v = data.piotroski.criteria[k];
                  return (
                    <div key={k} className="flex justify-between text-sm items-center">
                      <span className="text-text-secondary">{label}</span>
                      <span className={`text-lg ${v === true ? "text-success" : v === false ? "text-danger" : "text-text-muted"}`}>
                        {v === true ? "✓" : v === false ? "✗" : "—"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </Card>

          {/* Beneish M-Score */}
          <Card className="p-6" data-prov="beneish">
            <h3 className="font-semibold text-lg mb-4">Beneish M-Score</h3>
            {data.beneish.validComponents < 8 && (
              <p className="text-xs text-text-muted mb-3">
                Only {data.beneish.validComponents}/{data.beneish.totalComponents} indexes available (need ≥4).
              </p>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="flex flex-col items-center justify-center">
                <div className={`text-5xl font-bold ${data.beneish.mScore == null ? "text-text-muted" : data.beneish.manipulationLikely ? "text-danger" : "text-success"}`}>
                  {fmtNum(data.beneish.mScore)}
                </div>
                <div className={`mt-2 px-3 py-1 rounded-full text-sm font-semibold ${
                  data.beneish.mScore == null ? "bg-surface-alt text-text-muted" :
                  data.beneish.manipulationLikely ? "bg-danger/20 text-danger" :
                  "bg-success/20 text-success"
                }`}>
                  {data.beneish.interpretation}
                </div>
                <p className="text-xs text-text-muted mt-2 text-center">
                  M &gt; −2.22 suggests earnings manipulation
                </p>
              </div>
              <div className="space-y-1">
                {[
                  { k: "dsri", label: "DSRI (Receivables)", coeff: 0.920 },
                  { k: "gmi", label: "GMI (Gross Margin)", coeff: 0.528 },
                  { k: "aqi", label: "AQI (Asset Quality)", coeff: 0.404 },
                  { k: "sgi", label: "SGI (Sales Growth)", coeff: 0.892 },
                  { k: "depi", label: "DEPI (Depreciation)", coeff: 0.115 },
                  { k: "sgai", label: "SGAI (SGA Expense)", coeff: -0.172 },
                  { k: "tata", label: "TATA (Accruals)", coeff: 4.679 },
                  { k: "lvgi", label: "LVGI (Leverage)", coeff: -0.327 },
                ].map(({ k, label, coeff }) => {
                  const idx = data.beneish.indexes[k];
                  const contrib = data.beneish.mComponents[k];
                  return (
                    <div key={k} className="flex justify-between text-sm items-center">
                      <span className="text-text-secondary">{label}</span>
                      <span className="font-mono text-xs">
                        {idx != null ? `${idx.toFixed(3)}` : "—"}
                        {contrib != null && (
                          <span className={contrib >= 0 ? "text-danger ml-1" : "text-success ml-1"}>
                            ({contrib >= 0 ? "+" : ""}{contrib.toFixed(2)})
                          </span>
                        )}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </Card>

          {!searched && !data && (
            <div className="text-text-secondary text-sm py-8 text-center">
              Enter a ticker symbol above to analyze corporate health metrics.
            </div>
          )}
        </div>
      )}

      {!loading && !data && !error && !searched && (
        <div className="text-text-secondary text-sm py-12 text-center space-y-2">
          <p className="text-lg">🔍</p>
          <p>Enter a ticker symbol above to analyze corporate health.</p>
          <p className="text-xs">Uses yfinance data — balance sheet, income statement, and cash flow.</p>
        </div>
      )}

      {/* Earnings Quality & Accruals (Sloan) */}
      <EarningsQuality />
    </div>
  );
}

export default function CorporatePage() {
  return (
    <Suspense fallback={<div className="p-8 text-muted">Loading…</div>}>
      <CorporatePageInner />
    </Suspense>
  );
}
