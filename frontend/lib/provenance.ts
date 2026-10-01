// Data provenance: where each number on screen came from.
//
// Backend responses carry an additive top-level `provenance` map (see
// backend/backend/provenance.py). A <SourceScope> registers that map for the
// subtree it wraps; datapoints inside name their key with `data-prov`, and the
// right-click "Source" panel resolves the key here.

export type SourceFlag = "fallback" | "estimate" | "stale" | "partial" | "delayed" | "proxy";

export interface SourceRef {
  provider: string;
  providerName?: string;
  series?: string;
  title?: string;
  units?: string;
  frequency?: string;
  /** Observation date/period the value describes. */
  observed?: string;
  /** UTC time the data was fetched (survives cache hits). */
  fetchedAt?: string;
  transform?: string;
  url?: string;
  flags?: SourceFlag[];
  note?: string;
  /** Computed metrics only. */
  formula?: string;
  /** Computed metrics only: other keys in the same map, or inline refs. */
  inputs?: (string | SourceRef)[];
}

/** A value is a ref, a list of refs, or another key's name ("same source as"). */
export type Provenance = Record<string, SourceRef | SourceRef[] | string>;

export const FLAG_LABELS: Record<SourceFlag, string> = {
  fallback: "Fallback value",
  estimate: "Estimate / projection",
  stale: "Stale",
  partial: "Partial period",
  delayed: "Delayed quote",
  proxy: "Proxy series",
};

// scope id -> provenance map, maintained by <SourceScope>.
const scopes = new Map<string, Provenance>();

export function registerScope(id: string, prov: Provenance | null | undefined): void {
  if (prov) scopes.set(id, prov);
  else scopes.delete(id);
}

export function unregisterScope(id: string): void {
  scopes.delete(id);
}

export function getScope(id: string): Provenance | undefined {
  return scopes.get(id);
}

/** The `provenance` map of an API response, if it carries one. */
export function provOf(data: unknown): Provenance | undefined {
  if (data && typeof data === "object" && "provenance" in data) {
    return (data as { provenance?: Provenance }).provenance ?? undefined;
  }
  return undefined;
}

/**
 * Look a datapoint key up in a provenance map: the exact key, then each parent
 * (dropping the last `.segment`), then the `"*"` default. Returns [] when the
 * map has no answer — callers show "Source not annotated" rather than guess.
 */
export function resolveRefs(prov: Provenance | undefined, key: string | null | undefined, depth = 0): SourceRef[] {
  if (!prov || depth > 5) return [];
  const expand = (hit: SourceRef | SourceRef[] | string): SourceRef[] =>
    typeof hit === "string" ? resolveRefs(prov, hit, depth + 1) : Array.isArray(hit) ? hit : [hit];
  let k = key ?? "";
  while (k) {
    const hit = prov[k];
    if (hit) return expand(hit);
    const cut = k.lastIndexOf(".");
    k = cut > 0 ? k.slice(0, cut) : "";
  }
  const dflt = prov["*"];
  return dflt ? expand(dflt) : [];
}

/** Resolve a computed metric's inputs (keys or inline refs) to refs. */
export function resolveInputs(prov: Provenance | undefined, ref: SourceRef): { label: string; refs: SourceRef[] }[] {
  return (ref.inputs ?? []).map((input) =>
    typeof input === "string"
      ? { label: input, refs: prov?.[input] ? resolveRefs(prov, input) : [] }
      : { label: input.title ?? input.series ?? input.providerName ?? input.provider, refs: [input] },
  );
}

/** Open a source link in the system browser (desktop) or a new tab (web). */
export async function openExternal(url: string): Promise<void> {
  if (!/^https:\/\//i.test(url)) return;
  if (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window) {
    try {
      const { open } = await import("@tauri-apps/plugin-shell");
      await open(url);
      return;
    } catch {
      // fall through to window.open
    }
  }
  window.open(url, "_blank", "noopener,noreferrer");
}
