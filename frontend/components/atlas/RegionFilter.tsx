"use client";

import type { AtlasRegion } from "@/lib/types";

interface Props {
  regions: AtlasRegion[];
  active: string;
  onSelect: (id: string) => void;
}

const WORLD_OPTION = { id: "World", label: "World" };

export function RegionFilter({ regions, active, onSelect }: Props) {
  const options = [WORLD_OPTION, ...regions];

  return (
    <div className="flex gap-1 flex-wrap">
      {options.map((r) => (
        <button
          key={r.id}
          onClick={() => onSelect(r.id)}
          className={`px-2.5 py-1 rounded-md text-xs font-mono transition-colors ${
            active === r.id
              ? "bg-surface-alt text-text-primary"
              : "text-text-muted hover:text-text-primary"
          }`}
        >
          {r.label}
        </button>
      ))}
    </div>
  );
}
