"use client";

import type { AtlasIndicator } from "@/lib/types";

interface Props {
  indicators: AtlasIndicator[];
  active: string;
  onSelect: (id: string) => void;
}

export function IndicatorSelector({ indicators, active, onSelect }: Props) {
  if (!indicators.length) {
    return (
      <div className="flex gap-2 flex-wrap">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="skeleton h-8 w-28 rounded-full" />
        ))}
      </div>
    );
  }

  return (
    <div className="flex gap-2 flex-wrap">
      {indicators.map((ind) => (
        <button
          key={ind.id}
          onClick={() => onSelect(ind.id)}
          className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
            active === ind.id
              ? "bg-accent text-white border-accent"
              : "bg-surface-alt border-border text-text-secondary hover:text-text-primary hover:border-border"
          }`}
        >
          {ind.label}
        </button>
      ))}
    </div>
  );
}
