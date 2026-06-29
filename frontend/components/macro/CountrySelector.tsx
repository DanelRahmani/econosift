"use client";

import { useMemo, useState, useCallback } from "react";
import type { Country } from "@/lib/types";
import { api } from "@/lib/api";

export function CountrySelector({
  countries, selected, onChange, max = 8,
}: {
  countries: Country[];
  selected: string[];
  onChange: (next: string[]) => void;
  max?: number;
}) {
  const [q, setQ] = useState("");
  const [searchResults, setSearchResults] = useState<{ iso2: string; name: string; region: string }[]>([]);
  const [searching, setSearching] = useState(false);

  // Merge backend search results as pseudo-Country objects (shown in "Search Results" group)
  const allCountries: Country[] = useMemo(() => {
    const extras: Country[] = searchResults
      .filter((r) => !countries.some((c) => c.iso2 === r.iso2))
      .map((r) => ({ iso2: r.iso2, name: r.name, region: "Search Results" }));
    return [...countries, ...extras];
  }, [countries, searchResults]);

  const grouped = useMemo(() => {
    const filtered = allCountries.filter(
      (c) => c.name.toLowerCase().includes(q.toLowerCase()) ||
             c.iso2.toLowerCase().includes(q.toLowerCase()));
    const byRegion: Record<string, Country[]> = {};
    filtered.forEach((c) => {
      (byRegion[c.region] ||= []).push(c);
    });
    return byRegion;
  }, [allCountries, q]);

  function toggle(iso2: string) {
    if (selected.includes(iso2)) {
      onChange(selected.filter((c) => c !== iso2));
    } else if (selected.length < max) {
      onChange([...selected, iso2]);
    }
  }

  async function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key !== "Enter") return;
    const val = q.trim();
    if (!val) return;

    // If matches an existing country in the local list, toggle it
    const match = countries.find(
      (c) => c.name.toLowerCase() === val.toLowerCase() || c.iso2.toLowerCase() === val.toLowerCase()
    );
    if (match) {
      if (!selected.includes(match.iso2) && selected.length >= max) return;
      toggle(match.iso2);
      setQ("");
      return;
    }

    // Query the World Bank country database
    if (selected.length >= max) return;
    setSearching(true);
    try {
      const res = await fetch(`/api/macro/search-countries?q=${encodeURIComponent(val)}`);
      const data = await res.json();
      const found = data.countries?.[0];
      if (found && found.iso2) {
        // Add to our search results so it appears as a pill
        setSearchResults((prev) => {
          if (prev.some((r) => r.iso2 === found.iso2)) return prev;
          return [...prev, { iso2: found.iso2, name: found.name, region: "Search Results" }];
        });
        // Add to selection
        if (!selected.includes(found.iso2)) {
          onChange([...selected, found.iso2]);
        }
        setQ("");
      }
    } catch {
      // silent fail
    } finally {
      setSearching(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-text-secondary">Countries</span>
        <span className="text-xs text-text-muted">{selected.length}/{max}</span>
      </div>
      <input
        className="input w-full mb-3"
        placeholder={searching ? "Searching World Bank data…" : "Search for countries…"}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={searching}
      />
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
