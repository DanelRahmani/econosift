"use client";

import { useSyncExternalStore } from "react";
import { getOldestStale, subscribe } from "@/lib/staleData";

function age(iso: string): string {
  const min = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  return min < 60 ? `${min} min` : `${Math.floor(min / 60)} h ${min % 60} min`;
}

/** Shown while some figures on screen come from a cache entry past its
 *  60-minute lifetime that the backend is refreshing in the background. */
export function RefreshingBadge() {
  const oldest = useSyncExternalStore(subscribe, getOldestStale, () => null);
  if (!oldest) return null;
  const when = new Date(oldest).toLocaleString();
  return (
    <span
      role="status"
      title={`Some figures were fetched ${when} (${age(oldest)} ago). Fresh data is loading in the background and will replace them.`}
      className="inline-flex items-center gap-1 rounded-lg border border-border bg-surface-alt px-2 h-6 text-xs text-text-muted"
    >
      <span className="w-1.5 h-1.5 rounded-full bg-warning animate-pulse" aria-hidden />
      Refreshing
    </span>
  );
}
