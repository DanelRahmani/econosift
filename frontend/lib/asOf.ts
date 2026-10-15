// "As of" labels and the pending poll for stored data (Phase 69, plan §4).
// Pages read econosift.db; a response says when its data was stored
// (fetchedAt / asOf) and `status: "pending"` while the fetcher still has to
// fetch it. Kept free of imports so `node --test tests/unit` can load it.

export const PENDING_POLL_MS = 10_000;
export const PENDING_MAX_POLLS = 30; // ~5 min, then the page keeps its "pending" notice

type Stamped = {
  asOf?: unknown;
  fetchedAt?: unknown;
  provenance?: unknown;
} | null | undefined;

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function etParts(d: Date) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York", year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(d);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return { year: get("year"), month: get("month"), day: get("day"), time: `${get("hour")}:${get("minute")}` };
}

function provenanceStamp(prov: unknown): string | null {
  const star = (prov as Record<string, unknown> | null)?.["*"];
  const ref = Array.isArray(star) ? star[0] : star;
  const t = (ref as { fetchedAt?: unknown } | null)?.fetchedAt;
  return typeof t === "string" ? t : null;
}

/**
 * When a response's data was stored, for a label: "14:45 ET" today, "Oct 14, 16:00 ET" on an
 * earlier day, "Oct 14, 2026" for a stored date. Prefers fetchedAt, then asOf, then the
 * response's provenance stamp. null when none parses: never a made-up time.
 */
export function asOfLabel(data: Stamped, now: Date = new Date()): string | null {
  if (!data) return null;
  const candidates = [data.fetchedAt, data.asOf, provenanceStamp(data.provenance)];
  for (const c of candidates) {
    if (typeof c !== "string" || !c) continue;
    const ymd = DATE_ONLY.exec(c);
    if (ymd) return `${MONTHS[+ymd[2] - 1]} ${+ymd[3]}, ${ymd[1]}`;
    const d = new Date(c);
    if (Number.isNaN(d.getTime())) continue;
    const p = etParts(d);
    const today = etParts(now);
    const sameDay = p.year === today.year && p.month === today.month && p.day === today.day;
    return sameDay ? `${p.time} ET` : `${p.month} ${p.day}, ${p.time} ET`;
  }
  return null;
}

/** True when the fetcher has queued this response's data (top level or one nested panel). */
export function isPending(data: unknown): boolean {
  if (!data || typeof data !== "object" || Array.isArray(data)) return false;
  const d = data as Record<string, unknown>;
  if (d.status === "pending") return true;
  return Object.values(d).some(
    (v) => !!v && typeof v === "object" && !Array.isArray(v) && (v as Record<string, unknown>).status === "pending",
  );
}

/** react-query refetchInterval: poll while pending, at most PENDING_MAX_POLLS times. */
export function pendingRefetchInterval(data: unknown, fetches: number): number | false {
  return isPending(data) && fetches <= PENDING_MAX_POLLS ? PENDING_POLL_MS : false;
}
