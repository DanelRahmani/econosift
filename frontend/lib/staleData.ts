// Tracks API responses the backend served from a cache entry past its 60-min
// TTL while it refreshes that entry in the background (X-Data-Stale header).
// The queries that received such data are re-run a few times until the
// backend answers with fresh data; meanwhile the Navbar shows a badge.
import { queryClient } from "./queryClient";

export const STALE_HEADER = "X-Data-Stale";

const RETRY_MS = 20_000;
const MAX_ROUNDS = 6; // give up after ~2 min; the data stays truthfully dated

const stalePaths = new Map<string, string>(); // path -> fetchedAt (ISO, UTC)
const staleData = new WeakSet<object>();
const rounds = new Map<string, number>();
const listeners = new Set<() => void>();
let timer: ReturnType<typeof setTimeout> | null = null;
let snapshot: string | null = null;

function emit() {
  snapshot = stalePaths.size ? [...stalePaths.values()].sort()[0] : null;
  listeners.forEach((l) => l());
}

function schedule() {
  if (timer || !stalePaths.size) return;
  timer = setTimeout(() => {
    timer = null;
    for (const path of [...stalePaths.keys()]) {
      const n = (rounds.get(path) ?? 0) + 1;
      rounds.set(path, n);
      if (n > MAX_ROUNDS) stalePaths.delete(path);
    }
    emit();
    void queryClient.invalidateQueries({
      predicate: (q) => typeof q.state.data === "object" && q.state.data !== null && staleData.has(q.state.data),
    });
    schedule();
  }, RETRY_MS);
}

/** Record one GET response. `fetchedAt` is the header value, or null when fresh. */
export function noteResponse(path: string, fetchedAt: string | null, data: unknown) {
  if (fetchedAt) {
    if (typeof data === "object" && data !== null) staleData.add(data);
    if (!stalePaths.has(path) && (rounds.get(path) ?? 0) <= MAX_ROUNDS) {
      stalePaths.set(path, fetchedAt);
      emit();
      schedule();
    }
  } else {
    rounds.delete(path);
    if (stalePaths.delete(path)) emit();
  }
}

export function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Oldest fetch time among responses still being refreshed, or null. */
export function getOldestStale(): string | null {
  return snapshot;
}
