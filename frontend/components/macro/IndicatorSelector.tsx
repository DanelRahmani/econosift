"use client";

import type { Indicator } from "@/lib/types";

export function IndicatorSelector({
  indicators, value, onChange,
}: {
  indicators: Indicator[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div>
      <label className="text-sm font-medium text-text-secondary block mb-2">Indicator</label>
      <select
        className="input w-full"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {indicators.map((i) => (
          <option key={i.id} value={i.id} className="bg-surface">
            {i.label}
          </option>
        ))}
      </select>
    </div>
  );
}
