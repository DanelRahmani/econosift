"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ScenarioTab } from "@/components/portfolio/ScenarioTab";
import type { Holding } from "@/lib/types";

function ScenarioPageInner() {
  const searchParams = useSearchParams();
  const tickerParam = searchParams.get("tickers") || "";

  const [tickers, setTickers] = useState(tickerParam);
  const [holdings, setHoldings] = useState<Holding[]>([]);

  function handleTickerSubmit() {
    const syms = tickers
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
    if (!syms.length) return;
    const h = syms.map((ticker) => ({
      ticker,
      name: ticker,
      weight: +(100 / syms.length).toFixed(2),
      price: null as number | null,
      shares: 0,
    }));
    setHoldings(h);
  }

  return (
    <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-display font-bold text-text-primary">Scenario Lab</h1>
        <p className="text-sm text-text-secondary mt-1">
          Stress-test portfolios against historical crises and custom macro shocks.
        </p>
      </div>

      <div className="flex gap-3 items-end flex-wrap">
        <div>
          <label className="text-xs text-text-secondary block mb-1">
            Tickers (comma-separated)
          </label>
          <input
            type="text"
            className="input w-64"
            placeholder="AAPL, MSFT, GOOGL"
            value={tickers}
            onChange={(e) => setTickers(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleTickerSubmit(); }}
          />
        </div>
        <button
          onClick={handleTickerSubmit}
          className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors"
        >
          Load
        </button>
      </div>

      {holdings.length > 0 ? (
        <ScenarioTab holdings={holdings} />
      ) : (
        <div className="text-text-muted text-sm py-12 text-center">
          Enter ticker symbols above to run scenario analysis.
        </div>
      )}
    </main>
  );
}

export default function ScenarioPage() {
  return (
    <Suspense fallback={<div className="p-8 text-text-muted">Loading…</div>}>
      <ScenarioPageInner />
    </Suspense>
  );
}
