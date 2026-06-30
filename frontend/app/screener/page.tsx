"use client";

import { useCallback, useEffect, useRef, useState, Suspense } from "react";
import { api } from "@/lib/api";
import type { PresetDef, ScreenerCacheRow, ScreenerUniverseResponse, SnowflakeBatchResponse } from "@/lib/types";
import { Card, Skeleton, PageSkeleton } from "@/components/ui";
import { useUrlState } from "@/lib/useUrlState";
import { PresetPills } from "@/components/screener/PresetPills";
import { ResultTabs, RESULT_TABS } from "@/components/screener/ResultTabs";
import type { ResultTab } from "@/components/screener/ResultTabs";
import { ScreenerTable } from "@/components/screener/ScreenerTable";
import { Sparkline } from "@/components/screener/Sparkline";
import { fmtNum, fmtPct, fmtLarge } from "@/lib/format";
import { SnowflakeMini } from "@/components/markets/SnowflakeMini";

// ─── Constants ────────────────────────────────────────────────────────────

const INDEX_OPTS = [
  { key: "dow",   label: "Dow 30" },
  { key: "ndx",   label: "Nasdaq-100" },
  { key: "sp500", label: "S&P 500" },
] as const;
type IndexKey = (typeof INDEX_OPTS)[number]["key"];

// ─── Helpers ──────────────────────────────────────────────────────────────

function SegCtrl<T extends string>({
  opts,
  value,
  onChange,
}: {
  opts: readonly { key: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1">
      {opts.map((o) => (
        <button
          key={o.key}
          onClick={() => onChange(o.key)}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            value === o.key
              ? "bg-accent text-white"
              : "text-text-secondary hover:bg-surface-alt hover:text-text-primary"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ─── Charts gallery card ──────────────────────────────────────────────────

function SparkCard({
  row,
  snowflake,
}: {
  row: ScreenerCacheRow;
  snowflake?: SnowflakeBatchResponse[string];
}) {
  const positive = (row.changePercent ?? 0) >= 0;
  return (
    <div className="bg-surface border border-border rounded-lg p-3 flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-1">
        <span className="font-semibold text-sm text-text-primary truncate">{row.symbol}</span>
        <span
          className={`text-xs font-medium px-1.5 py-0.5 rounded ${
            positive ? "bg-success/10 text-success" : "bg-danger/10 text-danger"
          }`}
        >
          {row.changePercent !== null ? `${row.changePercent >= 0 ? "+" : ""}${fmtPct(row.changePercent)}` : "—"}
        </span>
      </div>
      <div className="text-xs text-text-muted truncate">{row.name}</div>
      <div className="flex gap-2 items-start">
        <Sparkline
          data={row.spark ?? []}
          positive={positive}
          width={200}
          height={72}
          className="flex-1"
        />
        {snowflake && (
          <SnowflakeMini
            scores={snowflake.scores}
            overallScore={snowflake.overallScore}
            size={72}
          />
        )}
      </div>
      <div className="flex items-center justify-between text-xs text-text-secondary">
        <span>${fmtNum(row.price)}</span>
        <span className="text-text-muted">{fmtLarge(row.marketCap)}</span>
      </div>
      {row.sector && (
        <span className="text-[10px] text-text-muted bg-surface-alt px-1.5 py-0.5 rounded self-start">
          {row.sector}
        </span>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────

function ScreenerPageInner() {
  const [urlState, setUrlState] = useUrlState({
    index: "sp500",
    presets: "",
    tab: "Overview",
  });

  const index = (INDEX_OPTS.map((o) => o.key) as readonly string[]).includes(urlState.index)
    ? (urlState.index as IndexKey)
    : "sp500";
  const activePresets = new Set<string>(
    urlState.presets ? urlState.presets.split(",").filter(Boolean) : [],
  );
  const [viewMode, setViewMode] = useState<"table" | "charts">("table");

  const [sortKey, setSortKey] = useState("marketCap");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const resultTab = urlState.tab as ResultTab;

  const [presetDefs, setPresetDefs] = useState<PresetDef[]>([]);
  const [data, setData] = useState<ScreenerUniverseResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [snowflakeScores, setSnowflakeScores] = useState<SnowflakeBatchResponse>({});
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Load preset definitions once
  useEffect(() => {
    let alive = true;
    api.screenerPresets().then((r) => {
      if (alive) setPresetDefs(r.presets);
    }).catch(() => {});
    return () => { alive = false; };
  }, []);

  // Fetch universe whenever parameters change
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);

    const presetsStr = [...activePresets].join(",");
    api.screenerUniverse(index, presetsStr, "", sortKey, sortDir, 500)
      .then((r) => {
        if (!alive) return;
        setData(r);
      })
      .catch((e) => {
        if (!alive) return;
        setError(e?.message ?? "Failed to load screener data");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => { alive = false; };
  }, [index, activePresets, sortKey, sortDir]);

  const handleSetIndex = useCallback((v: IndexKey) => {
    setUrlState({ index: v });
  }, [setUrlState]);

  const handleTogglePreset = useCallback((id: string) => {
    const current = urlState.presets ? urlState.presets.split(",").filter(Boolean) : [];
    const next = current.includes(id)
      ? current.filter((p) => p !== id)
      : [...current, id];
    setUrlState({ presets: next.join(",") });
  }, [urlState.presets, setUrlState]);

  const handleSort = useCallback((key: string) => {
    setSortKey((prev) => {
      if (prev === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
        return key;
      }
      setSortDir("desc");
      return key;
    });
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await api.screenerRefresh(index);
    } finally {
      setRefreshing(false);
    }
  };

  const results = data?.results ?? [];

  // Fetch snowflake batch scores when switching to charts view
  useEffect(() => {
    if (viewMode !== "charts" || results.length === 0) return;
    const tickers = results.map((r) => r.symbol).slice(0, 100); // cap at 100
    api.snowflakeBatch(tickers)
      .then(setSnowflakeScores)
      .catch(() => setSnowflakeScores({}));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode, data]);

  return (
    <main className="max-w-screen-2xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-text-primary">Stock Screener</h1>
          <p className="text-sm text-text-muted mt-0.5">
            Filter and rank stocks by fundamentals, technicals, and signals.
            Cache refreshed nightly.
          </p>
        </div>
        <SegCtrl opts={INDEX_OPTS} value={index} onChange={handleSetIndex} />
      </div>

      {/* Stale cache banner */}
      {data?.stale && (
        <div className="flex items-center gap-3 px-4 py-2.5 rounded-lg border border-warning/40 bg-warning/5 text-sm text-warning">
          <svg className={`w-4 h-4 shrink-0 ${refreshing ? "animate-spin" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>{refreshing ? "Refresh triggered — data will update shortly." : "Data may be stale. Cache is being refreshed in the background."}</span>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="ml-auto text-xs px-2 py-1 rounded border border-warning/40 hover:bg-warning/10 transition-colors disabled:opacity-50"
          >
            Refresh now
          </button>
        </div>
      )}

      {/* Preset pills */}
      <Card className="p-4">
        <div className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-3">
          Signal presets
        </div>
        <PresetPills
          presets={presetDefs}
          selected={activePresets}
          onToggle={handleTogglePreset}
        />
        {activePresets.size > 0 && (
          <button
            onClick={() => setUrlState({ presets: "" })}
            className="mt-3 text-xs text-text-muted hover:text-text-primary underline"
          >
            Clear all filters
          </button>
        )}
      </Card>

      {/* Results */}
      <Card className="p-4">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div className="text-sm text-text-secondary">
            {loading ? (
              <span className="text-text-muted">Loading…</span>
            ) : (
              <>
                <span className="font-semibold text-text-primary">{results.length}</span>
                {data && data.count !== data.screened && (
                  <span className="text-text-muted"> of {data.screened}</span>
                )}{" "}
                stocks
                {data?.asOf && (
                  <span className="text-text-muted ml-2 text-xs">
                    as of {new Date(data.asOf).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                  </span>
                )}
              </>
            )}
          </div>

          {/* View mode toggle */}
          <div className="flex items-center gap-1 rounded-lg border border-border p-0.5">
            <button
              onClick={() => setViewMode("table")}
              title="Table view"
              className={`p-1.5 rounded-md transition-colors ${viewMode === "table" ? "bg-accent text-white" : "text-text-muted hover:text-text-primary"}`}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18"/>
              </svg>
            </button>
            <button
              onClick={() => setViewMode("charts")}
              title="Charts view"
              className={`p-1.5 rounded-md transition-colors ${viewMode === "charts" ? "bg-accent text-white" : "text-text-muted hover:text-text-primary"}`}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="3" width="6" height="18" rx="1"/><rect x="9" y="8" width="6" height="13" rx="1"/><rect x="16" y="5" width="6" height="16" rx="1"/>
              </svg>
            </button>
          </div>
        </div>

        {error && (
          <div className="text-sm text-danger py-6 text-center">{error}</div>
        )}

        {loading && !data ? (
          <PageSkeleton text="Loading screener data…" />
        ) : null}

        {!loading && !error && viewMode === "table" && (
          <div className="space-y-3">
            <ResultTabs active={resultTab} onChange={(t) => setUrlState({ tab: t })} />
            <ScreenerTable
              rows={results}
              tab={resultTab}
              sort={sortKey}
              dir={sortDir}
              onSort={handleSort}
            />
          </div>
        )}

        {!loading && !error && viewMode === "charts" && (
          <div>
            {results.length === 0 ? (
              <div className="py-12 text-center text-text-muted text-sm">
                No results match the current filters.
              </div>
            ) : (
              <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
                {results.map((row) => (
                  <SparkCard key={row.symbol} row={row} snowflake={snowflakeScores[row.symbol]} />
                ))}
              </div>
            )}
          </div>
        )}
      </Card>
    </main>
  );
}

export default function ScreenerPage() {
  return (
    <Suspense fallback={<PageSkeleton text="Loading screener…" />}>
      <ScreenerPageInner />
    </Suspense>
  );
}
