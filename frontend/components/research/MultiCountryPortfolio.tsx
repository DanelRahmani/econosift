"use client";

import { useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Card } from "@/components/ui";
import { api } from "@/lib/api";
import type { MultiCountryHoldingInput, MultiCountryPortfolio } from "@/lib/types";

const CURRENCIES = ["USD", "EUR", "JPY", "GBP", "CHF", "AUD", "CAD"] as const;

const DEFAULT_HOLDINGS: MultiCountryHoldingInput[] = [
  { ticker: "SPY", weight: 40, currency: "USD" },
  { ticker: "VGK", weight: 20, currency: "EUR" },
  { ticker: "EWJ", weight: 20, currency: "JPY" },
  { ticker: "EEM", weight: 20, currency: "USD" },
];

const PERIODS = ["1y", "3y", "5y"] as const;

export function MultiCountryPortfolio() {
  const [holdings, setHoldings] = useState<MultiCountryHoldingInput[]>(DEFAULT_HOLDINGS);
  const [period, setPeriod] = useState<string>("3y");
  const [data, setData] = useState<MultiCountryPortfolio | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = () => {
    const valid = holdings.filter((h) => h.ticker.trim() && h.weight > 0);
    if (valid.length === 0) return;
    setLoading(true);
    setError(null);
    api.multiCountryPortfolio(valid, period)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  const addHolding = () => {
    setHoldings([...holdings, { ticker: "", weight: 10, currency: "USD" }]);
  };

  const updateHolding = (i: number, field: keyof MultiCountryHoldingInput, value: string | number) => {
    const next = [...holdings];
    next[i] = { ...next[i], [field]: value };
    setHoldings(next);
  };

  const removeHolding = (i: number) => {
    setHoldings(holdings.filter((_, idx) => idx !== i));
  };

  return (
    <div className="space-y-6">
      {/* Input */}
      <Card>
        <h3 className="text-sm font-semibold mb-3">Multi-Country Holdings</h3>
        <div className="space-y-2 mb-4">
          {holdings.map((h, i) => (
            <div key={i} className="flex flex-wrap gap-2 items-center">
              <input
                value={h.ticker}
                onChange={(e) => updateHolding(i, "ticker", e.target.value)}
                placeholder="Ticker"
                className="w-20 px-2 py-1 text-xs rounded bg-surface-alt border border-border text-text-primary"
              />
              <input
                type="number"
                min="0"
                step="1"
                value={h.weight}
                onChange={(e) => updateHolding(i, "weight", parseFloat(e.target.value) || 0)}
                className="w-16 px-2 py-1 text-xs rounded bg-surface-alt border border-border text-text-primary"
              />
              <span className="text-xs text-text-muted">%</span>
              <select
                value={h.currency}
                onChange={(e) => updateHolding(i, "currency", e.target.value)}
                className="px-2 py-1 text-xs rounded bg-surface-alt border border-border text-text-primary"
              >
                {CURRENCIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
              <button
                onClick={() => removeHolding(i)}
                className="text-text-muted hover:text-red-500 text-xs"
              >
                ×
              </button>
            </div>
          ))}
        </div>
        <div className="flex gap-2 flex-wrap items-center">
          <button onClick={addHolding} className="px-3 py-1 text-xs rounded-lg bg-surface-alt border border-border text-text-secondary hover:text-text-primary">
            + Add Holding
          </button>
          <div className="flex gap-1">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-2 py-1 rounded text-xs font-medium ${
                  period === p ? "bg-accent text-white" : "bg-surface-alt text-text-secondary hover:text-text-primary"
                }`}
              >
                {p.toUpperCase()}
              </button>
            ))}
          </div>
          <button
            onClick={handleAnalyze}
            disabled={loading}
            className="px-3 py-1 text-xs font-medium rounded-lg bg-accent text-white hover:opacity-90 disabled:opacity-50"
          >
            {loading ? "Analyzing…" : "Analyze"}
          </button>
        </div>
      </Card>

      {error && (
        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/30 text-sm text-red-500">{error}</div>
      )}

      {/* Results */}
      {data && !data.error && (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-3 gap-3">
            <Card>
              <div className="text-xs text-text-muted">Ann. Return</div>
              <div className={`text-xl font-bold tabular-nums ${data.metrics.annReturn >= 0 ? "text-green-500" : "text-red-500"}`}>
                {data.metrics.annReturn.toFixed(2)}%
              </div>
            </Card>
            <Card>
              <div className="text-xs text-text-muted">Ann. Volatility</div>
              <div className="text-xl font-bold tabular-nums">{data.metrics.annVolatility.toFixed(2)}%</div>
            </Card>
            <Card>
              <div className="text-xs text-text-muted">Sharpe Ratio</div>
              <div className={`text-xl font-bold tabular-nums ${data.metrics.sharpe >= 1 ? "text-green-500" : ""}`}>
                {data.metrics.sharpe.toFixed(2)}
              </div>
            </Card>
          </div>

          {/* Cumulative chart */}
          {data.series.length > 0 && (
            <Card>
              <h3 className="text-sm font-semibold mb-3">FX-Adjusted Portfolio (USD)</h3>
              <div className="h-64">
                <ResponsiveContainer>
                  <LineChart data={data.series}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                    <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10 }} />
                    <Tooltip />
                    <Line type="monotone" dataKey="value" stroke="#3b82f6" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>
          )}

          {/* Holdings table */}
          <Card>
            <h3 className="text-sm font-semibold mb-3">Holdings Breakdown</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-text-muted text-xs">
                    <th className="text-left py-2 pr-3">Ticker</th>
                    <th className="text-right py-2 pr-3">Weight</th>
                    <th className="text-right py-2 pr-3">Ann. Return</th>
                    <th className="text-right py-2">Ann. Vol</th>
                  </tr>
                </thead>
                <tbody>
                  {data.holdings.map((h) => (
                    <tr key={h.ticker} className="border-b border-border/50 hover:bg-surface-alt/50">
                      <td className="py-2 pr-3 font-mono font-medium">{h.ticker}</td>
                      <td className="py-2 pr-3 text-right">{h.weight}%</td>
                      <td className={`py-2 pr-3 text-right font-medium ${(h.annReturn ?? 0) >= 0 ? "text-green-500" : "text-red-500"}`}>
                        {h.annReturn !== null ? `${h.annReturn.toFixed(2)}%` : "—"}
                      </td>
                      <td className="py-2 text-right text-text-secondary">
                        {h.annVolatility !== null ? `${h.annVolatility.toFixed(2)}%` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Allocation */}
          <div className="grid grid-cols-2 gap-3">
            <Card>
              <h3 className="text-sm font-semibold mb-2">Currency Allocation</h3>
              {Object.entries(data.countryAllocation).map(([ccy, w]) => (
                <div key={ccy} className="flex justify-between text-sm py-0.5">
                  <span className="text-text-secondary">{ccy}</span>
                  <span className="font-mono font-medium">{w.toFixed(1)}%</span>
                </div>
              ))}
            </Card>
            <Card>
              <h3 className="text-sm font-semibold mb-2">Currency Exposure</h3>
              {Object.entries(data.currencyExposure).map(([ccy, w]) => (
                <div key={ccy} className="flex justify-between text-sm py-0.5">
                  <span className="text-text-secondary">{ccy}</span>
                  <span className="font-mono font-medium">{w.toFixed(1)}%</span>
                </div>
              ))}
            </Card>
          </div>
        </>
      )}

      {!data && !loading && !error && (
        <div className="text-center py-16 text-text-muted text-sm">
          Add holdings and click Analyze to see FX-adjusted portfolio metrics.
        </div>
      )}
    </div>
  );
}
