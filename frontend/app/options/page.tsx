"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useTheme } from "@/components/ThemeProvider";
import { Skeleton, TabButton } from "@/components/ui";
import { SearchBar } from "@/components/SearchBar";
import { useUrlState } from "@/lib/useUrlState";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { IVKPIRow } from "@/components/options/IVKPIRow";
import { ChainTable } from "@/components/options/ChainTable";
import { IVTermStructure } from "@/components/options/IVTermStructure";
import { IVSmile } from "@/components/options/IVSmile";
import { OIProfileChart } from "@/components/options/OIProfileChart";
import { MonteCarloOptions } from "@/components/options/MonteCarloOptions";
import type {
  OptionsKPIs,
  OptionsChain,
  IVTermPoint,
  IVSmilePoint,
  OIProfile,
} from "@/lib/types";
import { useRefreshNonce } from "@/lib/refresh";

const TABS = ["Chain", "Volatility", "OI Profile", "Monte Carlo"] as const;
type Tab = (typeof TABS)[number];

function computeDTE(exp: string): number {
  return Math.max(0, Math.round((new Date(exp).getTime() - Date.now()) / 86_400_000));
}

function OptionsPageInner() {
  const { theme } = useTheme();

  const [urlState, setUrlState] = useUrlState({
    t: "AAPL",
    e: "",
    tab: "Chain",
  });

  const ticker = urlState.t.toUpperCase();
  const expiry = urlState.e;
  const tab = (TABS as readonly string[]).includes(urlState.tab) ? (urlState.tab as Tab) : "Chain";
  const [showOTMOnly, setShowOTMOnly] = useState(false);

  // Data
  const [kpis, setKpis] = useState<OptionsKPIs | null>(null);
  const [expiries, setExpiries] = useState<string[]>([]);
  const [chain, setChain] = useState<OptionsChain | null>(null);
  const [termStructure, setTermStructure] = useState<IVTermPoint[]>([]);
  const [smile, setSmile] = useState<IVSmilePoint[]>([]);
  const [oiProfile, setOiProfile] = useState<OIProfile | null>(null);

  // Expiries, term structure and smile are bare lists with no map of their own; they sit under the
  // ivmetrics scope (same Yahoo option-chain source). The chain response has its own scope for the spot line.
  const kpisScope = useSourceScope(provOf(kpis));
  const chainScope = useSourceScope(provOf(chain));

  // Loading states
  const [kpisLoading, setKpisLoading] = useState(false);
  const [expiriesLoading, setExpiriesLoading] = useState(false);
  const [chainLoading, setChainLoading] = useState(false);
  const [termLoading, setTermLoading] = useState(false);
  const [smileLoading, setSmileLoading] = useState(false);
  const [oiLoading, setOiLoading] = useState(false);

  // Fetch KPIs, expiries, and term structure when ticker changes
  const fetchTickerData = useCallback(async () => {
    if (!ticker.trim()) return;

    // Reset expiry-dependent data
    setChain(null);
    setSmile([]);
    setOiProfile(null);
    setUrlState({ e: "" });
    setExpiries([]);

    // Parallel fetches
    setKpisLoading(true);
    setExpiriesLoading(true);
    setTermLoading(true);

    const [kpisResult, expiriesResult, termResult] = await Promise.allSettled([
      api.optionsKPIs(ticker),
      api.optionsExpiries(ticker),
      api.optionsTermStructure(ticker),
    ]);

    setKpisLoading(false);
    setExpiriesLoading(false);
    setTermLoading(false);

    if (kpisResult.status === "fulfilled") {
      setKpis(kpisResult.value);
    } else {
      setKpis(null);
    }

    if (expiriesResult.status === "fulfilled") {
      const exps = expiriesResult.value ?? [];
      setExpiries(exps);
      if (exps.length > 0) {
        setUrlState({ e: exps[0] });
      }
    } else {
      setExpiries([]);
    }

    if (termResult.status === "fulfilled") {
      setTermStructure(termResult.value ?? []);
    } else {
      setTermStructure([]);
    }
  }, [ticker]);

  // Fetch chain, smile, and OI profile when expiry changes
  const fetchExpiryData = useCallback(async () => {
    if (!ticker.trim() || !expiry) return;

    setChainLoading(true);
    setSmileLoading(true);
    setOiLoading(true);

    const [chainResult, smileResult, oiResult] = await Promise.allSettled([
      api.optionsChain(ticker, expiry),
      api.optionsSmile(ticker, expiry),
      api.optionsOIProfile(ticker, expiry),
    ]);

    setChainLoading(false);
    setSmileLoading(false);
    setOiLoading(false);

    if (chainResult.status === "fulfilled") {
      setChain(chainResult.value);
    } else {
      setChain(null);
    }

    if (smileResult.status === "fulfilled") {
      setSmile(smileResult.value ?? []);
    } else {
      setSmile([]);
    }

    if (oiResult.status === "fulfilled") {
      setOiProfile(oiResult.value);
    } else {
      setOiProfile(null);
    }
  }, [ticker, expiry]);

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    fetchTickerData();
  }, [fetchTickerData, refreshNonce]);

  useEffect(() => {
    if (expiry) fetchExpiryData();
  }, [fetchExpiryData, expiry, refreshNonce]);

  function handleSearch(sym: string) {
    setUrlState({ t: sym.toUpperCase(), e: "" });
  }

  return (
    <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row gap-2 items-start sm:items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">Options Analytics</h1>
            <span className="px-2 py-0.5 rounded-md text-xs font-semibold bg-warning/20 text-warning">
              ~15min delay
            </span>
          </div>
          <p className="text-sm text-text-muted mt-0.5">
            IV surface, options chain, Greeks, and Monte Carlo pricing
          </p>
        </div>
      </div>

      {/* Ticker input */}
      <div className="flex flex-wrap items-center gap-3">
        <SearchBar onAdd={handleSearch} />
        <div className="px-3 py-1.5 bg-surface-alt border border-border rounded-full text-sm font-mono font-semibold text-text-primary">
          {ticker}
        </div>
      </div>

      {/* KPI Row */}
      <IVKPIRow kpis={kpis} loading={kpisLoading} />

      {/* Expiry selector */}
      <div className="flex items-center gap-3 flex-wrap" {...kpisScope}>
        <span className="text-sm text-text-muted font-medium">Expiry:</span>
        {expiriesLoading ? (
          <Skeleton className="h-9 w-40 rounded-lg" />
        ) : expiries.length > 0 ? (
          <select
            value={expiry}
            onChange={(e) => setUrlState({ e: e.target.value })}
            className="px-3 py-1.5 rounded-lg border border-border bg-surface text-sm font-mono focus:outline-none focus:ring-1 focus:ring-accent"
          >
            {expiries.map((exp) => (
              <option key={exp} value={exp}>
                {exp} ({computeDTE(exp)}d)
              </option>
            ))}
          </select>
        ) : (
          <span className="text-sm text-text-muted italic">
            No expiries available — enter a valid ticker above
          </span>
        )}

        {expiry && (
          <span className="text-xs text-text-muted">
            {computeDTE(expiry)} days to expiry
          </span>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border overflow-x-auto pb-0.5">
        {TABS.map((t) => (
          <TabButton key={t} active={tab === t} onClick={() => setUrlState({ tab: t })}>
            {t === "Monte Carlo" ? <>🔴 {t}</> : t}
          </TabButton>
        ))}
      </div>

      {/* Tab content */}
      <div className="min-h-[400px]">
        {/* Chain Tab */}
        {tab === "Chain" && (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={showOTMOnly}
                  onChange={(e) => setShowOTMOnly(e.target.checked)}
                  className="rounded border-border accent-accent"
                />
                OTM only
              </label>
              {chain && (
                <span className="text-xs text-text-muted" data-prov="spot" {...chainScope}>
                  {chain.calls.length} calls · {chain.puts.length} puts ·
                  Spot {chain.spot ? `$${chain.spot.toFixed(2)}` : "—"}
                </span>
              )}
            </div>
            <ChainTable chain={chain} loading={chainLoading} showOTMOnly={showOTMOnly} />
          </div>
        )}

        {/* Volatility Tab */}
        {tab === "Volatility" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" {...kpisScope}>
            <IVTermStructure data={termStructure} loading={termLoading} theme={theme} />
            <IVSmile data={smile} loading={smileLoading} theme={theme} />
          </div>
        )}

        {/* OI Profile Tab */}
        {tab === "OI Profile" && (
          <OIProfileChart data={oiProfile} loading={oiLoading} theme={theme} />
        )}

        {/* Monte Carlo Tab */}
        {tab === "Monte Carlo" && (
          <div className="space-y-4">
            <div className="p-3 rounded-md bg-danger/10 border border-danger/30 text-xs text-danger font-medium">
              Compute-intensive · 10,000 GBM paths per option · Results are not cached and vary
              between runs · Not financial advice
            </div>
            {expiry ? (
              <MonteCarloOptions ticker={ticker} expiry={expiry} theme={theme} />
            ) : (
              <div className="flex items-center justify-center h-40 text-text-muted text-sm">
                Select an expiry date above to enable Monte Carlo pricing
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

export default function OptionsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-text-muted">Loading…</div>}>
      <OptionsPageInner />
    </Suspense>
  );
}
