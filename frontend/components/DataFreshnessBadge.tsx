"use client";
import { useMemo } from "react";

function timeAgo(dateStr: string): { text: string; freshness: "fresh" | "aging" | "stale" } {
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return { text: "Unknown", freshness: "stale" };
    const diffMs = Date.now() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return { text: "Just now", freshness: "fresh" };
    if (diffMin < 60) return { text: `Updated ${diffMin}m ago`, freshness: "fresh" };
    const diffHrs = Math.floor(diffMin / 60);
    if (diffHrs < 6) return { text: `Updated ${diffHrs}h ago`, freshness: "fresh" };
    if (diffHrs < 24) return { text: `Updated ${diffHrs}h ago`, freshness: "aging" };
    const diffDays = Math.floor(diffHrs / 24);
    if (diffDays === 1) return { text: "Updated yesterday", freshness: "aging" };
    if (diffDays < 7) return { text: `Updated ${diffDays}d ago`, freshness: "stale" };
    return { text: "Stale", freshness: "stale" };
  } catch {
    return { text: "Unknown", freshness: "stale" };
  }
}

const DOT_COLORS = { fresh: "bg-success", aging: "bg-warning", stale: "bg-danger" };

export function DataFreshnessBadge({ asOf, className = "" }: { asOf: string | null | undefined; className?: string }) {
  const info = useMemo(() => (asOf ? timeAgo(asOf) : { text: "No data", freshness: "stale" as const }), [asOf]);

  return (
    <span className={`inline-flex items-center gap-1 text-xs text-text-muted ${className}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${DOT_COLORS[info.freshness]}`} />
      {info.text}
    </span>
  );
}
