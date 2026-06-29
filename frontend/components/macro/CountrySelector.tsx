"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Country } from "@/lib/types";

interface WbResult {
  iso2: string;
  iso3: string;
  name: string;
}

export function CountrySelector({
  countries, selected, onChange, max = 8,
}: {
  countries: Country[];
  selected: string[];
  onChange: (next: string[]) => void;
  max?: number;
}) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<WbResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  // Debounced typeahead against World Bank country universe
  useEffect(() => {
    if (!q.trim() || q.trim().length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/macro/search-countries?q=${encodeURIComponent(q.trim())}`);
        const data = await res.json();
        const filtered = (data.countries || []).filter(
          (r: WbResult) => !selected.includes(r.iso2) && !countries.some((c) => c.iso2 === r.iso2)
        );
        setResults(filtered);
        if (filtered.length > 0) setOpen(true);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  // Close dropdown on outside click
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function pick(iso2: string) {
    if (!selected.includes(iso2) && selected.length < max) {
      onChange([...selected, iso2]);
    }
    setQ("");
    setResults([]);
    setOpen(false);
  }

  function toggle(iso2: string) {
    if (selected.includes(iso2)) {
      onChange(selected.filter((c) => c !== iso2));
    } else if (selected.length < max) {
      onChange([...selected, iso2]);
    }
  }

  const grouped = useMemo(() => {
    const qLower = q.toLowerCase().trim();
    const filtered = qLower
      ? countries.filter(
          (c) => c.name.toLowerCase().includes(qLower) || c.iso2.toLowerCase().includes(qLower)
        )
      : countries;
    const byRegion: Record<string, Country[]> = {};
    filtered.forEach((c) => {
      (byRegion[c.region] ||= []).push(c);
    });
    return byRegion;
  }, [countries, q]);

  return (
    <div ref={boxRef} className="relative">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-text-secondary">Countries</span>
        <span className="text-xs text-text-muted">{selected.length}/{max}</span>
      </div>
      <input
        className="input w-full mb-3"
        placeholder="Search countries…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />

      {/* Typeahead dropdown */}
      {open && results.length > 0 && (
        <div className="absolute z-20 left-0 right-0 top-[68px] bg-surface border border-border rounded-lg shadow-lg max-h-48 overflow-auto">
          {loading && (
            <div className="px-3 py-2 text-xs text-text-muted">Searching…</div>
          )}
          {results.map((r) => (
            <button
              key={r.iso3}
              onClick={() => pick(r.iso2)}
              className="w-full text-left px-3 py-2 text-sm text-text-primary hover:bg-surface-alt transition-colors border-b border-border/50 last:border-b-0"
            >
              <span className="font-medium">{r.name}</span>
              <span className="text-text-muted ml-2 text-xs">{r.iso2}{r.iso2 !== r.iso3 ? ` / ${r.iso3}` : ""}</span>
            </button>
          ))}
        </div>
      )}

      {/* Predefined pills grouped by region */}
      <div className="max-h-64 overflow-auto space-y-3 pr-1">
        {Object.entries(grouped).map(([region, list]) => (
          <div key={region}>
            <div className="text-xs uppercase tracking-wide text-text-muted mb-1">{region}</div>
            <div className="flex flex-wrap gap-2">
              {list.map((c) => {
                const on = selected.includes(c.iso2);
                const disabled = !on && selected.length >= max;
                return (
                  <button
                    key={c.iso2}
                    onClick={() => toggle(c.iso2)}
                    disabled={disabled}
                    className={`px-2.5 py-1 rounded-lg text-xs transition-colors ${
                      on ? "bg-accent text-white"
                         : disabled ? "bg-surface-alt text-text-muted opacity-50 cursor-not-allowed"
                         : "bg-surface-alt text-text-secondary hover:text-text-primary"
                    }`}
                  >
                    {c.name}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
