"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CountryRate } from "@/lib/types";
import { Card } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf, type Provenance } from "@/lib/provenance";
import { ValuationEngine } from "@/components/markets/ValuationEngine";
import { DcfPanel } from "@/components/markets/DcfPanel";

/**
 * Valuation tab: shared discount rate selector at the top, then the Phase 1
 * valuation engine (8 models + EconoSift composite + fundamentals + analyst data)
 * and interactive two-stage DCF panel below.
 */
export function ValuationTab({
  tickers,
  onNavigateTab,
}: {
  tickers: string[];
  period?: string;
  onNavigateTab?: (tab: string) => void;
}) {
  const [countryRates, setCountryRates] = useState<CountryRate[]>([]);
  const [selectedCountry, setSelectedCountry] = useState("");
  const [customWacc, setCustomWacc] = useState<number | null>(null);
  const [showInfo, setShowInfo] = useState(false);
  const [ratesProv, setRatesProv] = useState<Provenance | undefined>(undefined);
  const ratesScope = useSourceScope(ratesProv);

  useEffect(() => {
    api.riskFreeRates().then((r) => {
      if (r.rates?.length) { setCountryRates(r.rates); setRatesProv(provOf(r)); }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    setSelectedCountry("");
    setCustomWacc(null);
  }, [tickers]);

  function handleCountryChange(name: string) {
    setSelectedCountry(name);
    if (name) {
      const c = countryRates.find((r) => r.name === name);
      if (c) {
        setCustomWacc(Math.round((c.riskFreeRate + c.erp) * 10000) / 10000);
        return;
      }
    }
    setCustomWacc(null);
  }

  if (!tickers.length) return null;

  const selected = countryRates.find((r) => r.name === selectedCountry);
  // Get active ticker currency from tickers (simplified - use first ticker)
  const activeTicker = tickers[0];

  return (
    <div className="space-y-8">
      {/* Global Discount Rate Selector */}
      <Card className="p-4" {...ratesScope}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-text-secondary">Discount Rate &amp; Currency</h3>
          <button
            onClick={() => setShowInfo(!showInfo)}
            className="text-xs text-text-muted hover:text-accent transition-colors flex items-center gap-1"
            title="How rates are calculated"
          >
            <span className="w-5 h-5 rounded-full border border-border flex items-center justify-center text-[11px] leading-none">?</span>
            {showInfo ? "Hide" : "How?"}
          </button>
        </div>

        {showInfo && (
          <div className="mb-4 p-3 rounded-lg bg-surface-alt border border-border text-xs text-text-secondary space-y-2">
            <p><strong className="text-text-primary">Risk-Free Rate</strong> — Retrieved live from the <em>Federal Reserve Economic Data (FRED)</em> API. For the United States, the 10-year Treasury yield (DGS10) is used as the standard risk-free benchmark. For other countries, OECD 3-month interbank rates (IR3TIB01*) or central bank policy rates (IRSTCI01*) serve as the local-currency risk-free proxy. Rates update every 60 minutes with the FRED data cache. If FRED is unreachable, stored fallback estimates are used.</p>
            <p><strong className="text-text-primary">Equity Risk Premium (ERP)</strong> — Country-specific premium above the risk-free rate, reflecting the additional return investors demand for equity exposure. Pulled from Aswath Damodaran&apos;s annual country ERP dataset (<code>damodaran_erp_2026.json</code>) which covers ~200 countries. The file is updated annually each January from Damodaran&apos;s public Excel spreadsheet. Mature market ERP is ~4.46%; emerging markets and high-inflation economies have higher premiums.</p>
            <p><strong className="text-text-primary">Cost of equity (β = 1)</strong> — Shown here as <em>risk-free rate + equity risk premium</em>, i.e. the CAPM cost of equity of a stock with beta 1. It is <em>not</em> a WACC: it ignores the stock&apos;s own beta and its debt. Each ticker&apos;s own WACC (CAPM cost of equity blended with after-tax cost of debt) is the default of the DCF panel below; picking a region here overrides that discount rate with this beta-1 figure, and choosing Auto-detect restores the ticker&apos;s WACC.</p>
            <p className="text-text-muted italic">Source: FRED (Federal Reserve Bank of St. Louis), OECD, Damodaran Online. Data refreshed automatically — no manual updates needed.</p>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-xs text-text-muted">Region (override discount rate):</label>
            <select
              value={selectedCountry}
              onChange={(e) => handleCountryChange(e.target.value)}
              className="rounded-md bg-surface-alt border border-border px-2 py-1 text-xs"
            >
              <option value="">Auto-detect (ticker WACC)</option>
              {countryRates.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name} ({(c.riskFreeRate * 100).toFixed(1)}%)
                </option>
              ))}
            </select>
          </div>
          {selected && (
            <div className="flex items-center gap-4 text-xs text-text-secondary" data-prov-ctx={selected.name}>
              <span data-prov={`rates.${selected.name}`}>
                Risk-free: <span className="font-mono text-text-primary">{(selected.riskFreeRate * 100).toFixed(2)}%</span>
                {selected.tenor && <span className="text-text-muted"> ({selected.tenor}{selected.asOf ? `, ${selected.asOf.slice(0, 7)}` : ""})</span>}
                {(selected.basis === "fallback" || selected.stale) && (
                  <span className="ml-1 text-warning">{selected.basis === "fallback" ? "estimate, no live data" : "stale"}</span>
                )}
              </span>
              <span data-prov={`rates.${selected.name}.erp`}>ERP: <span className="font-mono text-text-primary">{(selected.erp * 100).toFixed(2)}%</span></span>
              <span>Cost of equity (β = 1): <span className="font-mono text-accent font-semibold">{customWacc ? `${(customWacc * 100).toFixed(2)}%` : "—"}</span></span>
            </div>
          )}
        </div>
      </Card>

      <ValuationEngine tickers={tickers} onNavigateTab={onNavigateTab} />
      <div>
        <h2 className="text-sm font-semibold mb-3 text-text-secondary">
          Interactive Two-Stage DCF
        </h2>
        <p className="text-xs text-text-muted mb-3">
          Starts from the same assumptions as the DCF model above (the ticker&apos;s WACC and growth); move the sliders to stress them.
        </p>
        <DcfPanel tickers={tickers} sharedWacc={customWacc} />
      </div>
    </div>
  );
}
