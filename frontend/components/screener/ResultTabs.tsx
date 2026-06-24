"use client";

export type ResultTab =
  | "Overview"
  | "Performance"
  | "Technicals"
  | "Valuation"
  | "Profitability"
  | "Dividends"
  | "All Columns";

export const RESULT_TABS: ResultTab[] = [
  "Overview",
  "Performance",
  "Technicals",
  "Valuation",
  "Profitability",
  "Dividends",
  "All Columns",
];

interface ResultTabsProps {
  active: ResultTab;
  onChange: (t: ResultTab) => void;
}

export function ResultTabs({ active, onChange }: ResultTabsProps) {
  return (
    <div className="flex flex-wrap gap-1" role="tablist">
      {RESULT_TABS.map((t) => (
        <button
          key={t}
          role="tab"
          aria-selected={active === t}
          onClick={() => onChange(t)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            active === t
              ? "bg-accent text-white"
              : "text-text-secondary hover:bg-surface-alt hover:text-text-primary"
          }`}
        >
          {t}
        </button>
      ))}
    </div>
  );
}
