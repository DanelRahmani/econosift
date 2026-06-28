"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { SearchResult } from "@/lib/types";

interface Props {
  value: string;
  onChange: (ticker: string) => void;
  placeholder?: string;
}

export function TickerSearch({ value, onChange, placeholder = "Search ticker (AAPL, MSFT)…" }: Props) {
  const [q, setQ] = useState(value);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync external value changes into local input
  useEffect(() => {
    setQ(value);
  }, [value]);

  // Debounced search
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

  // Click outside to close
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
    const s = symbol.toUpperCase();
    onChange(s);
    setQ(s);
    setResults([]);
    setOpen(false);
    inputRef.current?.blur();
  }

  return (
    <div className="relative w-full" ref={boxRef}>
      <div className="flex gap-2">
        <input
          ref={inputRef}
          className="flex-1 px-4 py-2 rounded-lg bg-surface-alt border border-border text-text-primary text-sm focus:outline-none focus:border-accent"
          placeholder={placeholder}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && results.length > 0) {
              e.preventDefault();
              pick(results[0].symbol);
            }
          }}
          onFocus={() => results.length > 0 && setOpen(true)}
          maxLength={12}
        />
      </div>
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
              <span className="font-mono text-sm text-text-primary font-semibold">{r.symbol}</span>
              <span className="text-xs text-text-secondary truncate flex-1">{r.name}</span>
              <span className="text-xs text-text-muted">{r.exchange}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
