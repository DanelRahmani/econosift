"use client";
import { useEffect, useRef } from "react";

export interface ShortcutHandlers {
  onTabSwitch?: (index: number) => void;   // 1-9
  onTabPrev?: () => void;                  // [
  onTabNext?: () => void;                  // ]
  onPeriodPrev?: () => void;
  onPeriodNext?: () => void;
}

/** True when the key belongs to whatever has focus: a text field, a select, an editable element. */
function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/**
 * Page keyboard shortcuts (P2-07): 1–9 pick the page's Nth tab, [ / ] step to the
 * previous / next tab (P2-42: reaches tabs past the ninth), ←/→ step its period
 * control. Only the handlers a page passes are bound, so Ctrl+K stays with the global
 * command palette. Keys typed into a field, or pressed with a modifier, are left alone.
 */
export function useKeyboardShortcuts(handlers: ShortcutHandlers) {
  const ref = useRef(handlers);
  ref.current = handlers;

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      // AltGr (reported as Ctrl+Alt on Windows) is how many layouts type "[" and "]", so it is not a
      // shortcut modifier here (P3-40); a real Ctrl, Alt or Meta chord is left alone.
      const altGr = e.getModifierState?.("AltGraph") ?? false;
      if (e.defaultPrevented || e.metaKey || (!altGr && (e.ctrlKey || e.altKey)) || isTyping(e.target)) return;
      const h = ref.current;
      if (e.key >= "1" && e.key <= "9" && h.onTabSwitch) {
        e.preventDefault();
        h.onTabSwitch(Number(e.key));
      } else if (e.key === "[" && h.onTabPrev) {
        e.preventDefault();
        h.onTabPrev();
      } else if (e.key === "]" && h.onTabNext) {
        e.preventDefault();
        h.onTabNext();
      } else if (e.key === "ArrowLeft" && h.onPeriodPrev) {
        e.preventDefault();
        h.onPeriodPrev();
      } else if (e.key === "ArrowRight" && h.onPeriodNext) {
        e.preventDefault();
        h.onPeriodNext();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);
}

/** Handlers for a tab list: key N selects ``tabs[N - 1]`` when it exists. */
export function tabKeys<T>(tabs: readonly T[], select: (tab: T) => void) {
  return (n: number) => {
    const t = tabs[n - 1];
    if (t !== undefined) select(t);
  };
}

/**
 * Handlers for `[` / `]` on a tab list: step one tab, clamped at both ends. A page
 * whose current tab isn't in the list (it shows its default) counts as on the first.
 */
export function tabStepKeys<T>(tabs: readonly T[], isCurrent: (tab: T) => boolean, select: (tab: T) => void) {
  const i = Math.max(tabs.findIndex(isCurrent), 0);
  return {
    onTabPrev: () => { if (i > 0) select(tabs[i - 1]); },
    onTabNext: () => { if (i < tabs.length - 1) select(tabs[i + 1]); },
  };
}

/** Handlers for a period list: step one place, clamped at both ends. */
export function periodKeys<T>(periods: readonly T[], current: T, select: (p: T) => void) {
  const i = periods.indexOf(current);
  return {
    onPeriodPrev: () => { if (i > 0) select(periods[i - 1]); },
    onPeriodNext: () => { if (i >= 0 && i < periods.length - 1) select(periods[i + 1]); },
  };
}
