"use client";

import type { PresetDef } from "@/lib/types";

// Categories that are deferred / coming soon
const DEFERRED_IDS = new Set(["insider_buying", "activist_target", "earnings_this_week"]);

interface PresetPillsProps {
  presets: PresetDef[];
  selected: Set<string>;
  onToggle: (id: string) => void;
}

export function PresetPills({ presets, selected, onToggle }: PresetPillsProps) {
  if (!presets.length) return null;

  // Group by category
  const grouped = presets.reduce<Record<string, PresetDef[]>>((acc, p) => {
    (acc[p.category] ??= []).push(p);
    return acc;
  }, {});

  return (
    <div className="space-y-3">
      {Object.entries(grouped).map(([category, items]) => (
        <div key={category} className="flex items-center gap-1.5">
          <span className="text-xs text-text-muted font-medium w-24 shrink-0 capitalize">{category}</span>
          <div className="flex flex-wrap gap-1.5">
          {items.map((p) => {
            const deferred = DEFERRED_IDS.has(p.id);
            const active = selected.has(p.id);
            return (
              <button
                key={p.id}
                disabled={deferred}
                onClick={() => !deferred && onToggle(p.id)}
                title={deferred ? "Coming soon" : p.description}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors border ${
                  deferred
                    ? "border-border/50 text-text-muted/50 cursor-not-allowed opacity-50"
                    : active
                    ? "bg-accent text-white border-accent"
                    : "border-border text-text-secondary hover:bg-surface-alt hover:text-text-primary"
                }`}
              >
                {p.label}
                {deferred && <span className="ml-1 text-[10px]">soon</span>}
              </button>
            );
          })}
          </div>
        </div>
      ))}
    </div>
  );
}
