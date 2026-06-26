"use client";

import type { CalendarEvent } from "@/lib/types";

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

export type CategoryFilter = CalendarEvent["category"] | "all";
export type ImpactFilter = 0 | 1 | 2 | 3; // 0 = All
export type TzDisplay = "ET" | "Local";

export interface CalendarFilterState {
  categories: Set<CalendarEvent["category"]>;
  impact: ImpactFilter;
  country: string; // "" = all
  tz: TzDisplay;
}

interface CalendarFiltersProps {
  filters: CalendarFilterState;
  countries: string[];
  onCategoryToggle: (cat: CalendarEvent["category"]) => void;
  onImpactChange: (v: ImpactFilter) => void;
  onCountryChange: (v: string) => void;
  onTzChange: (v: TzDisplay) => void;
}

// ─────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────

function ToggleBtn({
  active,
  onClick,
  children,
  colorClass,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  colorClass?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
        active
          ? (colorClass ?? "bg-accent text-white")
          : "text-text-muted hover:bg-surface-alt"
      }`}
    >
      {children}
    </button>
  );
}

const CATEGORY_COLORS: Record<string, string> = {
  macro: "bg-blue-600 text-white",
  earnings: "bg-emerald-600 text-white",
  dividend: "bg-amber-500 text-white",
  ipo: "bg-purple-600 text-white",
};

const CATEGORIES: { key: CalendarEvent["category"]; label: string }[] = [
  { key: "macro", label: "Macro" },
  { key: "earnings", label: "Earnings" },
  { key: "dividend", label: "Dividend" },
  { key: "ipo", label: "IPO" },
];

const IMPACT_OPTS: { value: ImpactFilter; label: string }[] = [
  { value: 0, label: "All" },
  { value: 1, label: "⭐" },
  { value: 2, label: "⭐⭐" },
  { value: 3, label: "⭐⭐⭐" },
];

const TZ_OPTS: TzDisplay[] = ["ET", "Local"];

// ─────────────────────────────────────────────
// CalendarFilters (presentational)
// ─────────────────────────────────────────────

export function CalendarFilters({
  filters,
  countries,
  onCategoryToggle,
  onImpactChange,
  onCountryChange,
  onTzChange,
}: CalendarFiltersProps) {
  return (
    <div className="flex flex-wrap gap-x-6 gap-y-3 items-center">
      {/* Category multi-toggle */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-text-muted font-medium whitespace-nowrap">
          Type
        </span>
        <div className="flex flex-wrap gap-1">
          {CATEGORIES.map((c) => (
            <ToggleBtn
              key={c.key}
              active={filters.categories.has(c.key)}
              onClick={() => onCategoryToggle(c.key)}
              colorClass={CATEGORY_COLORS[c.key]}
            >
              {c.label}
            </ToggleBtn>
          ))}
        </div>
      </div>

      {/* Impact */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-text-muted font-medium whitespace-nowrap">
          Impact
        </span>
        <div className="flex flex-wrap gap-1">
          {IMPACT_OPTS.map((o) => (
            <ToggleBtn
              key={o.value}
              active={filters.impact === o.value}
              onClick={() => onImpactChange(o.value)}
            >
              {o.label}
            </ToggleBtn>
          ))}
        </div>
      </div>

      {/* Country (only render if there are options) */}
      {countries.length > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted font-medium whitespace-nowrap">
            Country
          </span>
          <select
            value={filters.country}
            onChange={(e) => onCountryChange(e.target.value)}
            className="text-xs bg-surface-alt border border-border rounded-md px-2 py-1 text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
          >
            <option value="">All</option>
            {countries.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Timezone display */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-text-muted font-medium whitespace-nowrap">
          Time
        </span>
        <div className="flex gap-1">
          {TZ_OPTS.map((tz) => (
            <ToggleBtn
              key={tz}
              active={filters.tz === tz}
              onClick={() => onTzChange(tz)}
            >
              {tz}
            </ToggleBtn>
          ))}
        </div>
      </div>
    </div>
  );
}
