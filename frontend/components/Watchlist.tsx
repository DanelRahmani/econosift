"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { Quote } from "@/lib/types";
import { Card } from "@/components/ui";
import { fmtPct, fmtPrice, currencySymbol } from "@/lib/format";

const STORAGE_KEY = "axiom-watchlist";

interface Props {
  onSelect?: (ticker: string) => void;
}

export function Watchlist({ onSelect }: Props) {
  const [tickers, setTickers] = useState<string[]>([]);
  const [quotes, setQuotes] = useState<Record<string, Quote | null>>({});
  const [input, setInput] = useState("");

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      if (Array.isArray(saved)) setTickers(saved);
    } catch {}
  }, []);

  const tickersKey = tickers.join(",");
  useEffect(() => {
    if (!tickers.length) return;
    let active = true;
    tickers.forEach(async (t) => {
      try {
        const q = await api.quote(t);
        if (active) setQuotes((prev) => ({ ...prev, [t]: q }));
      } catch {
        if (active) setQuotes((prev) => ({ ...prev, [t]: null }));
      }
    });
    return () => { active = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tickersKey]);

  function add() {
    const sym = input.trim().toUpperCase();
    if (!sym || tickers.includes(sym)) { setInput(""); return; }
    const next = [...tickers, sym];
    setTickers(next);
    setInput("");
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch {}
  }

  function remove(sym: string) {
    const next = tickers.filter((t) => t !== sym);
    setTickers(next);
    setQuotes((prev) => { const r = { ...prev }; delete r[sym]; return r; });
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch {}
  }

  return (
    <Card>
      <h2 className="text-sm font-semibold mb-3 text-text-secondary">Watchlist</h2>
      <div className="flex gap-2 mb-3">
        <input
          className="input flex-1 text-sm"
          placeholder="Add ticker (e.g. NVDA)"
          value={input}
          onChange={(e) => setInput(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === "Enter" && add()}
        />
        <button
          onClick={add}
          className="px-3 py-1.5 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent/80 transition-colors"
        >
          +
        </button>
      </div>
      {!tickers.length && (
        <p className="text-text-muted text-sm">No tickers — type a symbol above and press Enter or +.</p>
      )}
      <div className="space-y-0">
        {tickers.map((t) => {
          const q = quotes[t];
          const up = (q?.changePercent ?? 0) >= 0;
          return (
            <div
              key={t}
              className="flex items-center justify-between py-2 border-b border-border/40 last:border-0 group"
            >
              <button
                onClick={() => onSelect?.(t)}
                className="text-left flex-1 min-w-0 cursor-pointer"
                title={`Add ${t} to chart`}
              >
                <div className="font-mono text-sm font-semibold">{t}</div>
                {q && <div className="text-xs text-text-muted truncate">{q.name}</div>}
              </button>
              <div className="flex items-center gap-2 ml-2 shrink-0">
                <div className="text-right">
                  {q?.price != null && (
                    <div className="text-sm">{fmtPrice(q.price, currencySymbol(q.currency))}</div>
                  )}
                  {q?.changePercent != null && (
                    <div className={`text-xs font-medium ${up ? "text-success" : "text-danger"}`}>
                      {up ? "+" : ""}{fmtPct(q.changePercent)}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => remove(t)}
                  className="text-text-muted hover:text-danger opacity-0 group-hover:opacity-100 transition-opacity text-lg leading-none px-1"
                  title="Remove from watchlist"
                >
                  ×
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
