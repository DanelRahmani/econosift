"use client";
import { useEffect, useCallback, type RefObject } from "react";

export interface ShortcutHandlers {
  onSearch?: () => void;
  onTabSwitch?: (index: number) => void;   // 1-9
  onPeriodPrev?: () => void;
  onPeriodNext?: () => void;
  onHelp?: () => void;
}

export function useKeyboardShortcuts(handlers: ShortcutHandlers, deps: unknown[] = []) {
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Don't intercept when typing in inputs
    const tag = (e.target as HTMLElement)?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

    // Ctrl+K / Cmd+K → search
    if ((e.ctrlKey || e.metaKey) && e.key === "k") {
      e.preventDefault();
      handlers.onSearch?.();
      return;
    }

    // ? → help overlay
    if (e.key === "?" && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      handlers.onHelp?.();
      return;
    }

    // 1-9 → tab switch
    if (e.key >= "1" && e.key <= "9" && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      handlers.onTabSwitch?.(parseInt(e.key));
      return;
    }

    // Left/Right arrows → period navigation
    if (e.key === "ArrowLeft" && !e.ctrlKey && !e.metaKey) {
      handlers.onPeriodPrev?.();
    }
    if (e.key === "ArrowRight" && !e.ctrlKey && !e.metaKey) {
      handlers.onPeriodNext?.();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handlers, ...deps]);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);
}
