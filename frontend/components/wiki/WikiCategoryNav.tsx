"use client";

import type { WikiCategory } from "@/lib/wikiData";

interface Props {
  categories: (WikiCategory & { count: number })[];
  activeCategory: string;
  onSelect: (key: string) => void;
  totalCount: number;
}

export function WikiCategoryNav({ categories, activeCategory, onSelect, totalCount }: Props) {
  return (
    <>
      {/* Desktop: vertical sidebar */}
      <nav className="hidden md:block space-y-0.5">
        <button
          onClick={() => onSelect("all")}
          className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors
            ${activeCategory === "all"
              ? "bg-accent text-white"
              : "text-text-secondary hover:text-text-primary hover:bg-surface-alt"
            }`}
        >
          <span className="flex items-center justify-between">
            <span>All Terms</span>
            <span className="text-xs opacity-70">{totalCount}</span>
          </span>
        </button>
        {categories.map((cat) => (
          <button
            key={cat.key}
            onClick={() => onSelect(cat.key)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors
              ${activeCategory === cat.key
                ? "bg-accent text-white"
                : "text-text-secondary hover:text-text-primary hover:bg-surface-alt"
              }`}
          >
            <span className="flex items-center justify-between">
              <span className="truncate">
                <span className="mr-1.5">{cat.icon}</span>
                {cat.label}
              </span>
              <span className="text-xs opacity-70 ml-2 flex-shrink-0">{cat.count}</span>
            </span>
          </button>
        ))}
      </nav>

      {/* Mobile: horizontal scrollable pills */}
      <div className="md:hidden flex gap-1.5 overflow-x-auto pb-2 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
        <button
          onClick={() => onSelect("all")}
          className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors
            ${activeCategory === "all"
              ? "bg-accent text-white"
              : "bg-surface border border-border text-text-secondary hover:text-text-primary"
            }`}
        >
          All ({totalCount})
        </button>
        {categories.map((cat) => (
          <button
            key={cat.key}
            onClick={() => onSelect(cat.key)}
            className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors
              ${activeCategory === cat.key
                ? "bg-accent text-white"
                : "bg-surface border border-border text-text-secondary hover:text-text-primary"
              }`}
          >
            {cat.icon} {cat.label} ({cat.count})
          </button>
        ))}
      </div>
    </>
  );
}
