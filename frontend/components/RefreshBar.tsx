"use client";

import { useRefresh } from "@/lib/refresh";

function fmtTime(ms: number): string {
  const d = new Date(ms);
  const sameDay = d.toDateString() === new Date().toDateString();
  const time = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return sameDay ? time : `${d.toLocaleDateString([], { month: "short", day: "numeric" })} ${time}`;
}

/** "Data as of" + Refresh button for a page inside a <RefreshProvider> (P1-20). */
export function RefreshBar() {
  const { refresh, refreshing, cooldownLeft, oldest } = useRefresh();
  const disabled = refreshing || cooldownLeft > 0;
  return (
    <div className="flex items-center justify-end gap-3 text-xs text-text-muted">
      {oldest !== null && (
        <span title="When the oldest figures on this page were fetched from their sources. Data is cached for up to 60 minutes.">
          Data as of {fmtTime(oldest)}
        </span>
      )}
      <button
        type="button"
        onClick={refresh}
        disabled={disabled}
        title={cooldownLeft > 0 && !refreshing
          ? `Refreshed just now. Available again in ${cooldownLeft} s (keeps within the data providers' rate limits).`
          : "Fetch this page's data fresh from its sources instead of the cache"}
        className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface-alt px-3 h-7 text-xs font-medium text-text-primary hover:border-accent btn-press disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <svg
          viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round" aria-hidden
          className={refreshing ? "animate-spin" : undefined}
        >
          <path d="M21 12a9 9 0 1 1-2.64-6.36" />
          <path d="M21 3v6h-6" />
        </svg>
        {refreshing ? "Refreshing…" : cooldownLeft > 0 ? `Refresh (${cooldownLeft}s)` : "Refresh"}
      </button>
    </div>
  );
}
