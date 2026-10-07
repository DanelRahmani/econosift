"use client";

import { usePathname } from "next/navigation";
import { useRefresh } from "@/lib/refresh";

// Pages without fetched market/macro data: no Refresh button.
const NO_REFRESH = ["/wiki", "/admin"];

function fmtTime(ms: number): string {
  const d = new Date(ms);
  const sameDay = d.toDateString() === new Date().toDateString();
  const time = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return sameDay ? time : `${d.toLocaleDateString([], { month: "short", day: "numeric" })} ${time}`;
}

/** Navbar Refresh button for the open page, with when its oldest data was fetched (P1-20). */
export function RefreshBar() {
  const pathname = usePathname();
  const { refresh, refreshing, cooldownLeft, oldest } = useRefresh();
  if (NO_REFRESH.some((p) => pathname === p || pathname?.startsWith(`${p}/`))) return null;
  const disabled = refreshing || cooldownLeft > 0;
  const asOf = oldest !== null ? `Data as of ${fmtTime(oldest)}` : null;
  const title = refreshing
    ? "Fetching this page's data fresh from its sources…"
    : cooldownLeft > 0
      ? `Refreshed just now. Available again in ${cooldownLeft} s (keeps within the data providers' rate limits).`
      : "Fetch this page's data fresh from its sources instead of the cache (data is cached for up to 60 minutes)";
  return (
    <div className="flex items-center gap-2 text-xs text-text-muted">
      {asOf && (
        <span className="hidden xl:inline" title="When the oldest figures on this page were fetched from their sources">
          {asOf}
        </span>
      )}
      <button
        type="button"
        onClick={refresh}
        disabled={disabled}
        aria-label={asOf ? `Refresh page data (${asOf})` : "Refresh page data"}
        title={asOf ? `${title}\n${asOf}` : title}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border text-sm text-text-muted hover:text-text-primary hover:bg-surface-alt transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <svg
          className={`w-4 h-4${refreshing ? " animate-spin" : ""}`} fill="none" viewBox="0 0 24 24"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
        >
          <path d="M21 12a9 9 0 1 1-2.64-6.36" />
          <path d="M21 3v6h-6" />
        </svg>
        <span className="hidden lg:inline">
          {refreshing ? "Refreshing…" : cooldownLeft > 0 ? `${cooldownLeft}s` : "Refresh"}
        </span>
      </button>
    </div>
  );
}
