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

  const grouped = useMemo(() => {
    const filtered = countries.filter(
      (c) => c.name.toLowerCase().includes(q.toLowerCase()) ||
             c.iso2.toLowerCase().includes(q.toLowerCase()));
    const byRegion: Record<string, Country[]> = {};
    filtered.forEach((c) => {
      (byRegion[c.region] ||= []).push(c);
    });
    return byRegion;
  }, [countries, q]);

  function toggle(iso2: string) {
    if (selected.includes(iso2)) {
      onChange(selected.filter((c) => c !== iso2));
    } else if (selected.length < max) {
      onChange([...selected, iso2]);
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
        placeholder="Filter countries…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
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
