"use client";

import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { useState, useEffect, useCallback, useRef } from "react";

/**
 * Generic hook that reads/writes URL search params for shareable deep links.
 *
 * Usage:
 *   const [state, setState] = useUrlState({ tab: "Overview", p: "1y" });
 *   // state = { tab: "Overview", p: "1y" }
 *   // setState({ tab: "Technicals" }) → URL becomes ?tab=Technicals
 *
 * Only params that differ from their defaults are included in the URL,
 * keeping bookmarked links clean.
 */
export function useUrlState<T extends Record<string, string>>(
  defaults: T,
): [T, (patch: Partial<T>) => void] {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  // Initialize state from URL search params on mount, falling back to defaults.
  const [state, setState] = useState<T>(() => {
    const init = { ...defaults };
    for (const key of Object.keys(defaults) as (keyof T)[]) {
      const v = searchParams.get(key as string);
      if (v !== null) init[key] = v as T[keyof T];
    }
    return init;
  });

  // Follow URL changes made from outside the page (the command palette jumping to another tab of
  // the page that is already open, browser back/forward). Only differing keys update state, so the
  // write-back below, which leaves the URL equal to state, cannot loop.
  useEffect(() => {
    setState((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const key of Object.keys(defaults) as (keyof T)[]) {
        const v = (searchParams.get(key as string) ?? defaults[key]) as T[keyof T];
        if (v !== prev[key]) {
          next[key] = v;
          changed = true;
        }
      }
      return changed ? next : prev;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Skip first effect fire — URL already matches the value read on mount.
  const initialized = useRef(false);

  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      return;
    }
    const params = new URLSearchParams();
    for (const [key, defaultVal] of Object.entries(defaults)) {
      const val = state[key];
      if (val !== undefined && val !== "" && val !== defaultVal) {
        params.set(key, val as string);
      }
    }
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  const updateState = useCallback((patch: Partial<T>) => {
    setState((prev) => ({ ...prev, ...patch }));
  }, []);

  return [state, updateState];
}
