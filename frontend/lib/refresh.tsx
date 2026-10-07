"use client";

// Page Refresh button (P1-20). The backend serves cached data for up to 60
// minutes, so re-running a request is not enough: a refresh sends
// X-Cache-Refresh, which makes the backend recompute the cached entries the
// request reads (an entry fetched in the last minute is served as is). Panels
// re-run their requests when the nonce from <RefreshProvider> changes;
// react-query panels are invalidated. Effects that run a "Calculate"/"Run
// Analysis" computation must NOT depend on the nonce (compute tiers yellow/red).
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { queryClient } from "./queryClient";

export const REFRESH_HEADER = "X-Cache-Refresh";
export const COOLDOWN_MS = 60_000; // matches the backend's minimum entry age
// Requests started this long after a click carry the header; panels re-run
// theirs as soon as the nonce changes.
const WINDOW_MS = 10_000;

let refreshUntil = 0;
let lastRefresh = 0; // module-level, so the cooldown survives navigation
let oldest: number | null = null; // oldest fetchedAt among responses since reset
let pending = 0; // requests sent with the refresh header, still in flight
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

/** Record a GET being sent; returns whether it is part of a refresh (then it
 *  carries the refresh header). */
export function requestStarted(): boolean {
  const refreshing = Date.now() < refreshUntil;
  if (refreshing) {
    pending += 1;
    emit();
  }
  return refreshing;
}

/** Record a finished GET; `data` may carry provenance refs with `fetchedAt`. */
export function requestDone(refreshing: boolean, data?: unknown) {
  if (refreshing) pending = Math.max(0, pending - 1);
  const prov = (data as { provenance?: Record<string, unknown> } | null)?.provenance;
  if (prov && typeof prov === "object") {
    for (const v of Object.values(prov)) {
      for (const r of Array.isArray(v) ? v : [v]) {
        const t = Date.parse((r as { fetchedAt?: string } | null)?.fetchedAt ?? "");
        if (!Number.isNaN(t) && (oldest === null || t < oldest)) oldest = t;
      }
    }
  }
  emit();
}

function useStore() {
  const [, setTick] = useState(0);
  useEffect(() => {
    const l = () => setTick((n) => n + 1);
    listeners.add(l);
    return () => { listeners.delete(l); };
  }, []);
  return { oldest, pending, lastRefresh };
}

const RefreshContext = createContext<{ nonce: number; refresh: () => void }>({
  nonce: 0,
  refresh: () => {},
});

/** App-wide: the Navbar's Refresh button re-fetches the open page. */
export function RefreshProvider({ children }: { children: ReactNode }) {
  const [nonce, setNonce] = useState(0);
  const pathname = usePathname();
  useEffect(() => {
    oldest = null; // the label covers the open page's responses only
    emit();
  }, [pathname]);
  const refresh = useCallback(() => {
    const now = Date.now();
    if (now - lastRefresh < COOLDOWN_MS) return;
    lastRefresh = now;
    refreshUntil = now + WINDOW_MS;
    oldest = null;
    emit();
    setNonce((n) => n + 1);
    void queryClient.invalidateQueries({ type: "active" });
  }, []);
  return <RefreshContext.Provider value={{ nonce, refresh }}>{children}</RefreshContext.Provider>;
}

/** Add to a panel's effect dependencies so it re-fetches on Refresh. 0 outside a provider. */
export function useRefreshNonce(): number {
  return useContext(RefreshContext).nonce;
}

export function useRefresh() {
  const { refresh } = useContext(RefreshContext);
  const store = useStore();
  const [now, setNow] = useState(() => Date.now());
  const cooling = now - store.lastRefresh < COOLDOWN_MS;
  useEffect(() => {
    if (!cooling) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [cooling]);
  return {
    refresh: () => { refresh(); setNow(Date.now()); },
    refreshing: store.pending > 0,
    cooldownLeft: cooling ? Math.ceil((COOLDOWN_MS - (now - store.lastRefresh)) / 1000) : 0,
    oldest: store.oldest,
  };
}
