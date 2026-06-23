"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { SearchResult } from "@/lib/types";

export function SearchBar({ onAdd }: { onAdd: (symbol: string) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const r = await api.search(q.trim());
        setResults(r.results);
        setOpen(true);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function pick(symbol: string) {
    onAdd(symbol.toUpperCase());
    setQ("");
    setResults([]);
    setOpen(false);
  }

  return (
    <div className="relative w-full max-w-md" ref={boxRef}>
      <input
        className="input w-full"
        placeholder="Search ticker (AAPL, MSFT, SAP.DE, 7203.T)…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && q.trim()) pick(q.trim());
        }}
        onFocus={() => results.length && setOpen(true)}
      />
      {open && (results.length > 0 || loading) && (
        <div className="absolute z-50 mt-1 w-full rounded-lg bg-surface border border-border shadow-xl max-h-72 overflow-auto">
          {loading && (
            <div className="px-3 py-2 text-text-muted text-sm">Searching…</div>
          )}
          {results.map((r) => (
            <button
              key={r.symbol}
              onClick={() => pick(r.symbol)}
              className="w-full text-left px-3 py-2 hover:bg-surface-alt flex items-center justify-between gap-2"
            >
              <span className="font-mono text-sm text-text-primary">{r.symbol}</span>
              <span className="text-xs text-text-secondary truncate max-w-[60%]">{r.name}</span>
              <span className="text-xs text-text-muted">{r.exchange}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
