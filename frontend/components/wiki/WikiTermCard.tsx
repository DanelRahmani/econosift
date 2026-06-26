"use client";

import type { WikiTerm } from "@/lib/wikiData";
import { CATEGORIES } from "@/lib/wikiData";

interface Props {
  term: WikiTerm;
  isExpanded: boolean;
  onToggle: () => void;
  onRelatedClick: (slug: string) => void;
}

export function WikiTermCard({ term, isExpanded, onToggle, onRelatedClick }: Props) {
  const cat = CATEGORIES.find((c) => c.key === term.category);

  return (
    <div
      onClick={onToggle}
      className={`bg-surface rounded-lg border border-border p-4 cursor-pointer
        transition-all hover:border-accent/40 ${isExpanded ? "ring-1 ring-accent/30" : ""}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-text-primary">{term.term}</h3>
            {cat && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface-alt text-text-muted">
                {cat.icon} {cat.label}
              </span>
            )}
          </div>
          {!isExpanded && (
            <p className="text-xs text-text-muted mt-1 line-clamp-2">
              {term.definition}
            </p>
          )}
        </div>
        <svg
          className={`w-4 h-4 text-text-muted flex-shrink-0 mt-1 transition-transform ${isExpanded ? "rotate-180" : ""}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </div>

      {isExpanded && (
        <div className="mt-3 pt-3 border-t border-border space-y-3">
          <p className="text-sm text-text-secondary leading-relaxed">{term.definition}</p>
          {term.related.length > 0 && (
            <div>
              <span className="text-xs font-medium text-text-muted">Related:</span>
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {term.related.map((slug) => (
                  <button
                    key={slug}
                    onClick={(e) => {
                      e.stopPropagation();
                      onRelatedClick(slug);
                    }}
                    className="text-xs px-2 py-0.5 rounded-md bg-surface-alt text-accent
                      hover:bg-accent/10 transition-colors"
                  >
                    {slug.replace(/-/g, " ")}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
