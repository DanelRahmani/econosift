"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiQuery } from "@/lib/queries";
import { useTheme } from "@/components/ThemeProvider";
import { Skeleton, TabButton } from "@/components/ui";
import { SearchBar } from "@/components/SearchBar";
import { useUrlState } from "@/lib/useUrlState";
import { SourceScope, useSourceScope } from "@/components/provenance/SourceScope";
import { provOf, type Provenance } from "@/lib/provenance";
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
import { useKeyboardShortcuts, tabKeys, tabStepKeys } from "@/lib/useKeyboardShortcuts";
import { ErrorBoundary } from "@/components/ErrorBoundary";

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
  useKeyboardShortcuts({
    onTabSwitch: tabKeys(TABS, (t) => setUrlState({ tab: t })),
    ...tabStepKeys(TABS, (t) => t === tab, (t) => setUrlState({ tab: t })),
  }); // P2-07
  const [showOTMOnly, setShowOTMOnly] = useState(false);

  // Data: KPIs, expiries and term structure per ticker; chain, smile and OI profile per expiry.
  const hasTicker = !!ticker.trim();
  const kpisQ = useQuery({ ...apiQuery("optionsKPIs", ticker), enabled: hasTicker });
  const expiriesQ = useQuery({ ...apiQuery("optionsExpiries", ticker), enabled: hasTicker });
  const termQ = useQuery({ ...apiQuery("optionsTermStructure", ticker), enabled: hasTicker });
  const hasExpiry = hasTicker && !!expiry;
  const chainQ = useQuery({ ...apiQuery("optionsChain", ticker, expiry), enabled: hasExpiry });
  const smileQ = useQuery({ ...apiQuery("optionsSmile", ticker, expiry), enabled: hasExpiry });
  const oiQ = useQuery({ ...apiQuery("optionsOIProfile", ticker, expiry), enabled: hasExpiry });

  const kpis: OptionsKPIs | null = kpisQ.data ?? null;
  const expiries = useMemo<string[]>(() => expiriesQ.data?.expiries ?? [], [expiriesQ.data]);
  const termStructure: IVTermPoint[] = termQ.data?.points ?? [];
  const chain: OptionsChain | null = hasExpiry ? chainQ.data ?? null : null;
  const smile: IVSmilePoint[] = (hasExpiry && smileQ.data?.points) || [];
  const oiProfile: OIProfile | null = hasExpiry ? oiQ.data ?? null : null;
  // Expiries, term structure and smile each carry their own map (P2-32).
  const expiriesProv: Provenance | undefined = expiriesQ.data ? provOf(expiriesQ.data) : undefined;
  const termProv: Provenance | undefined = termQ.data ? provOf(termQ.data) : undefined;
  const smileProv: Provenance | undefined = hasExpiry && smileQ.data ? provOf(smileQ.data) : undefined;

  // The chain response has its own scope for the spot line.
  const expiriesScope = useSourceScope(expiriesProv);
  const chainScope = useSourceScope(provOf(chain));

  // Loading states
  const kpisLoading = kpisQ.isLoading;
  const expiriesLoading = expiriesQ.isLoading;
  const chainLoading = chainQ.isLoading;
  const termLoading = termQ.isLoading;
  const smileLoading = smileQ.isLoading;
  const oiLoading = oiQ.isLoading;

  // Once a ticker's expiries are known, select the nearest one unless the URL names a listed one.
  useEffect(() => {
    if (!expiriesQ.data) return;
    if (expiries.length > 0 && !expiries.includes(expiry)) setUrlState({ e: expiries[0] });
    else if (expiries.length === 0 && expiry) setUrlState({ e: "" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiriesQ.data, expiries, expiry]);

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
      <div className="flex items-center gap-3 flex-wrap" {...expiriesScope}>
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
        <ErrorBoundary key={tab}>
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
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <SourceScope prov={termProv}>
              <IVTermStructure data={termStructure} loading={termLoading} theme={theme} />
            </SourceScope>
            <SourceScope prov={smileProv}>
              <IVSmile data={smile} loading={smileLoading} theme={theme} />
            </SourceScope>
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
        </ErrorBoundary>
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
