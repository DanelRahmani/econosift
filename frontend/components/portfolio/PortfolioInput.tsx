"use client";

import { useState } from "react";
import type { Holding } from "@/lib/types";

interface Props {
  holdings: Holding[];
  onChange: (holdings: Holding[]) => void;
  onAnalyze: () => void;
  loading: boolean;
}

export function PortfolioInput({ holdings, onChange, onAnalyze, loading }: Props) {
  const total = holdings.reduce((s, h) => s + (h.weight || 0), 0);
  const totalOk = Math.abs(total - 100) < 0.01;

  function updateTicker(i: number, val: string) {
    const next = [...holdings];
    next[i] = { ...next[i], ticker: val.toUpperCase() };
    onChange(next);
  }

  function updateWeight(i: number, val: string) {
    const next = [...holdings];
    next[i] = { ...next[i], weight: parseFloat(val) || 0 };
    onChange(next);
  }

  function addRow() {
    onChange([...holdings, { ticker: "", weight: 0 }]);
  }

  function removeRow(i: number) {
    onChange(holdings.filter((_, idx) => idx !== i));
  }

  function rebalance() {
    if (holdings.length === 0) return;
    const equal = parseFloat((100 / holdings.length).toFixed(2));
    const next = holdings.map((h, i) =>
      i === holdings.length - 1
        ? { ...h, weight: parseFloat((100 - equal * (holdings.length - 1)).toFixed(2)) }
        : { ...h, weight: equal }
    );
    onChange(next);
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-sm text-text-primary">Holdings</h2>
        <span className={`text-xs font-mono font-medium ${totalOk ? "text-green-500" : "text-red-500"}`}>
          Total: {total.toFixed(2)}%{!totalOk && " ⚠ must sum to 100"}
        </span>
      </div>

      <div className="space-y-2">
        {holdings.map((h, i) => (
          <div key={i} className="flex items-center gap-2">
            <input
              type="text"
              value={h.ticker}
              onChange={(e) => updateTicker(i, e.target.value)}
              placeholder="AAPL"
              className="w-28 px-2 py-1.5 rounded-md border border-border bg-surface-alt text-text-primary text-sm font-mono uppercase focus:outline-none focus:border-accent"
            />
            <input
              type="number"
              value={h.weight || ""}
              onChange={(e) => updateWeight(i, e.target.value)}
              placeholder="0"
              min={0}
              max={100}
              step={0.1}
              className="w-24 px-2 py-1.5 rounded-md border border-border bg-surface-alt text-text-primary text-sm focus:outline-none focus:border-accent"
            />
            <span className="text-text-muted text-sm">%</span>
            <button
              onClick={() => removeRow(i)}
              className="text-text-muted hover:text-red-500 transition-colors text-lg leading-none px-1"
              aria-label="Remove"
            >
              ×
            </button>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 flex-wrap pt-1">
        <button
          onClick={addRow}
          className="px-3 py-1.5 rounded-lg text-xs font-medium border border-border bg-surface-alt text-text-secondary hover:text-text-primary hover:bg-surface transition-colors"
        >
          + Add Row
        </button>
        <button
          onClick={rebalance}
          className="px-3 py-1.5 rounded-lg text-xs font-medium border border-border bg-surface-alt text-text-secondary hover:text-text-primary hover:bg-surface transition-colors"
        >
          Rebalance (Equal Weight)
        </button>
        <button
          onClick={onAnalyze}
          disabled={loading || holdings.length === 0 || !totalOk}
          className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-accent text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity ml-auto"
        >
          {loading ? "Analyzing…" : "Analyze Portfolio"}
        </button>
      </div>
    </div>
  );
}
