"use client";

import { useMemo, useState } from "react";
import type { Country } from "@/lib/types";

export function CountrySelector({
  countries, selected, onChange, max = 8,
}: {
  countries: Country[];
  selected: string[];
  onChange: (next: string[]) => void;
  max?: number;
}) {
  const [q, setQ] = useState("");
  const [custom, setCustom] = useState<string[]>([]);

  // Merge custom entries as pseudo-Country objects
  const allCountries: Country[] = useMemo(() => {
    const extras: Country[] = custom
      .filter((n) => !countries.some((c) => c.iso2 === n || c.name.toLowerCase() === n.toLowerCase()))
      .map((n) => ({ iso2: n, name: n, region: "Custom" }));
    return [...countries, ...extras];
  }, [countries, custom]);

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

  function removeCustom(name: string) {
    setCustom((prev) => prev.filter((n) => n !== name));
    onChange(selected.filter((c) => c !== name));
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key !== "Enter") return;
    const val = q.trim();
    if (!val) return;
    // If matches an existing country, toggle it
    const match = allCountries.find(
      (c) => c.name.toLowerCase() === val.toLowerCase() || c.iso2.toLowerCase() === val.toLowerCase()
    );
    if (match) {
      if (!selected.includes(match.iso2) && selected.length >= max) return;
      toggle(match.iso2);
      setQ("");
      return;
    }
    // Not in list — add as custom if under limit
    if (selected.length >= max) return;
    if (!custom.includes(val)) setCustom((prev) => [...prev, val]);
    onChange([...selected, val]);
    setQ("");
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-text-secondary">Countries</span>
        <span className="text-xs text-text-muted">{selected.length}/{max}</span>
      </div>
      <input
        className="input w-full mb-3"
        placeholder="Search for countries…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={handleKeyDown}
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
