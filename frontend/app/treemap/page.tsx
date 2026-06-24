"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { TreemapResponse } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";
import { TreemapChart } from "@/components/markets/Treemap";

// ---------------------------------------------------------------------------
// Control option definitions
// ---------------------------------------------------------------------------

const INDEX_OPTS = [
  { key: "sp500", label: "S&P 500" },
  { key: "ndx", label: "Nasdaq-100" },
  { key: "dow", label: "Dow 30" },
] as const;
type IndexKey = (typeof INDEX_OPTS)[number]["key"];

const PERIOD_OPTS = [
  { key: "1d", label: "1D" },
  { key: "1w", label: "1W" },
  { key: "1m", label: "1M" },
  { key: "3m", label: "3M" },
  { key: "ytd", label: "YTD" },
  { key: "1y", label: "1Y" },
] as const;
type PeriodKey = (typeof PERIOD_OPTS)[number]["key"];

const GROUPBY_OPTS = [
  { key: "sector-industry", label: "Sector › Industry" },
  { key: "sector", label: "Sector" },
] as const;
type GroupByKey = (typeof GROUPBY_OPTS)[number]["key"];

const COLOURBY_OPTS = [{ key: "return", label: "Return %" }] as const;
type ColourByKey = (typeof COLOURBY_OPTS)[number]["key"];

// ---------------------------------------------------------------------------
// Colour legend strip
// ---------------------------------------------------------------------------

function ColourLegend() {
  const stops = [
    { pct: -5, label: "−5%" },
    { pct: -3, label: "−3%" },
    { pct: -1, label: "−1%" },
    { pct: 0, label: "0" },
    { pct: 1, label: "+1%" },
    { pct: 3, label: "+3%" },
    { pct: 5, label: "+5%" },
  ];

  // Inline gradient mimicking the d3 scale
  const gradient =
    "linear-gradient(to right, #c4394a 0%, #d1c4c7 50%, #16a34a 100%)";

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-text-muted">Return:</span>
      <div className="relative flex items-center" style={{ width: 200 }}>
        <div
          className="rounded h-3 w-full"
          style={{ background: gradient }}
        />
        <div className="absolute inset-x-0 -bottom-4 flex justify-between">
          {stops.map((s) => (
            <span
              key={s.pct}
              className="text-[10px] text-text-muted font-mono"
              style={{ transform: "translateX(-50%)", position: "relative" }}
            >
              {s.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Segmented control (reusable within this page)
// ---------------------------------------------------------------------------

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
          className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
            value === o.key
              ? "bg-accent text-white"
              : "text-text-muted hover:bg-surface-alt"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function TreemapPage() {
  const [index, setIndex] = useState<IndexKey>("sp500");
  const [period, setPeriod] = useState<PeriodKey>("1d");
  const [groupBy, setGroupBy] = useState<GroupByKey>("sector-industry");
  const [colourBy, setColourBy] = useState<ColourByKey>("return");

  const [data, setData] = useState<TreemapResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(false);
    api
      .treemap(index, period)
      .then((r) => {
        if (alive) setData(r);
      })
      .catch(() => {
        if (alive) setError(true);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [index, period]);

  return (
    <div className="space-y-6">
      {/* Page heading */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-text-primary">Market Treemap</h1>
          <p className="text-sm text-text-muted mt-0.5">
            Area = log(market cap) · Colour = {period.toUpperCase()} return
            {data?.asOf ? ` · as of ${data.asOf}` : ""}
          </p>
        </div>
        {/* Colour legend */}
        <div className="pb-4">
          <ColourLegend />
        </div>
      </div>

      {/* Controls */}
      <Card>
        <div className="flex flex-wrap gap-x-6 gap-y-3 items-center">
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted font-medium">Index</span>
            <SegCtrl opts={INDEX_OPTS} value={index} onChange={setIndex} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted font-medium">Period</span>
            <SegCtrl opts={PERIOD_OPTS} value={period} onChange={setPeriod} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted font-medium">Group by</span>
            <SegCtrl opts={GROUPBY_OPTS} value={groupBy} onChange={setGroupBy} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted font-medium">Colour by</span>
            <SegCtrl opts={COLOURBY_OPTS} value={colourBy} onChange={setColourBy} />
          </div>
        </div>
      </Card>

      {/* Treemap body */}
      {loading && !data ? (
        <Skeleton className="h-[640px]" />
      ) : error || !data || data.stocks.length === 0 ? (
        <Card>
          <div className="text-text-muted text-sm py-10 text-center">
            {error
              ? "Treemap data unavailable — the backend may still be building the index."
              : "No stocks returned for this index."}
          </div>
        </Card>
      ) : (
        <Card className="overflow-hidden p-2">
          <TreemapChart
            stocks={data.stocks}
            groupBy={groupBy}
            period={period}
          />
        </Card>
      )}
    </div>
  );
}
