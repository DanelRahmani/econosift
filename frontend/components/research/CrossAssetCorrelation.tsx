"use client";

import { useState, useEffect } from "react";
import { Card } from "@/components/ui";
import { api } from "@/lib/api";
import type { CrossAssetCorrelation } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

const ASSET_PRESETS: Record<string, string[]> = {
  "Stocks": ["SPY", "QQQ", "IWM", "EFA", "EEM"],
  "Bonds": ["TLT", "IEF", "LQD", "HYG", "TIP"],
  "Commodities": ["GLD", "SLV", "USO", "DBA", "UNG"],
  "FX": ["EURUSD=X", "USDJPY=X", "GBPUSD=X", "AUDUSD=X", "USDCAD=X"],
};

const PERIODS = ["1y", "3y", "5y"] as const;

export function CrossAssetCorrelation() {
  const [data, setData] = useState<CrossAssetCorrelation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<string>("3y");
  const [selectedAssets, setSelectedAssets] = useState<string[]>(["SPY", "TLT", "GLD", "EURUSD=X"]);
  const scope = useSourceScope(provOf(data));

  const fetchData = () => {
    if (selectedAssets.length < 2) return;
    setLoading(true);
    setError(null);
    api.crossAssetCorrelation(selectedAssets, period)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, [period]);

  const toggleAsset = (ticker: string) => {
    setSelectedAssets((prev) =>
      prev.includes(ticker) ? prev.filter((t) => t !== ticker) : [...prev, ticker]
    );
  };

  const corrColor = (v: number | null) => {
    if (v === null) return "text-text-muted";
    const abs = Math.abs(v);
    if (abs >= 0.7) return v > 0 ? "text-red-500" : "text-green-500";
    if (abs >= 0.4) return v > 0 ? "text-orange-400" : "text-emerald-400";
    return "text-text-secondary";
  };

  const bgColor = (v: number | null) => {
    if (v === null) return "bg-surface-alt";
    const abs = Math.abs(v);
    if (abs >= 0.7) return v > 0 ? "bg-red-500/20" : "bg-green-500/20";
    if (abs >= 0.4) return v > 0 ? "bg-orange-500/10" : "bg-emerald-500/10";
    return "bg-surface-alt";
  };

  return (
    <div className="space-y-6">
      {/* Controls */}
      <Card>
        <div className="flex flex-wrap gap-3 items-center mb-3">
          <div className="flex gap-1">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                  period === p ? "bg-accent text-white" : "bg-surface-alt text-text-secondary hover:text-text-primary"
                }`}
              >
                {p.toUpperCase()}
              </button>
            ))}
          </div>
          <button
            onClick={fetchData}
            disabled={selectedAssets.length < 2}
            className="px-3 py-1 text-xs font-medium rounded-lg bg-accent text-white hover:opacity-90 disabled:opacity-50"
          >
            {loading ? "Loading…" : "Analyze"}
          </button>
        </div>

        {/* Asset selector */}
        {Object.entries(ASSET_PRESETS).map(([category, tickers]) => (
          <div key={category} className="mb-2">
            <span className="text-xs font-semibold text-text-muted mr-2">{category}:</span>
            <div className="inline-flex flex-wrap gap-1">
              {tickers.map((t) => (
                <button
                  key={t}
                  onClick={() => toggleAsset(t)}
                  className={`px-2 py-0.5 rounded text-xs font-mono transition-colors ${
                    selectedAssets.includes(t)
                      ? "bg-accent text-white"
                      : "bg-surface-alt text-text-muted hover:text-text-primary"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        ))}
      </Card>

      {error && (
        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/30 text-sm text-red-500">{error}</div>
      )}

      {/* Correlation matrix */}
      {data && data.matrix.length > 0 && (
        <Card {...scope}>
          <h3 className="text-sm font-semibold mb-3">Correlation Matrix</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr>
                  <th className="py-1 px-2 text-left text-text-muted" />
                  {data.labels.map((l, i) => (
                    <th key={i} className="py-1 px-2 text-center text-text-muted font-normal">
                      {l || data.assets[i]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.matrix.map((row, ri) => (
                  <tr key={ri}>
                    <td className="py-1 px-2 text-text-muted font-mono">{data.labels[ri] || data.assets[ri]}</td>
                    {row.map((val, ci) => (
                      <td
                        key={ci}
                        data-prov-ctx={`${data.labels[ri] || data.assets[ri]} × ${data.labels[ci] || data.assets[ci]}`}
                        className={`py-1 px-2 text-center font-mono font-medium rounded ${corrColor(val)} ${bgColor(val)}`}
                      >
                        {val !== null ? val.toFixed(2) : "—"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-text-muted mt-2">
            {period} daily returns · Green = negative correlation (diversification), Red = positive correlation
          </p>
        </Card>
      )}

      {!data && !loading && !error && (
        <div className="text-center py-16 text-text-muted text-sm">
          Select assets and click Analyze to see the correlation matrix.
        </div>
      )}
    </div>
  );
}
