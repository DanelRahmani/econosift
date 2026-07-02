"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark";

/** User-chosen brand colours (hex). `primary` drives the accent (buttons,
 *  active nav, highlights); `accent` drives the lighter accent (hover/light). */
export interface ThemeColors {
  primary: string;
  accent: string;
}

/** Built-in brand defaults, shown in the picker when nothing is customised. */
export const DEFAULT_COLORS: ThemeColors = { primary: "#6b0f1a", accent: "#c4394a" };

interface ThemeCtx {
  theme: Theme;
  toggle: () => void;
  colors: ThemeColors | null; // null = using the built-in palette
  setColors: (c: ThemeColors) => void;
  resetColors: () => void;
}

const Ctx = createContext<ThemeCtx>({
  theme: "dark",
  toggle: () => {},
  colors: null,
  setColors: () => {},
  resetColors: () => {},
});

const COLORS_KEY = "axiom-colors";

/** "#6b0f1a" → "107 15 26" (the RGB-triplet form the CSS variables expect). */
function hexToTriplet(hex: string): string | null {
  const m = /^#?([0-9a-fA-F]{6})$/.exec(String(hex).trim());
  if (!m) return null;
  const int = parseInt(m[1], 16);
  return `${(int >> 16) & 255} ${(int >> 8) & 255} ${int & 255}`;
}

function applyColors(colors: ThemeColors | null) {
  const root = document.documentElement;
  if (!colors) {
    root.style.removeProperty("--primary");
    root.style.removeProperty("--primary-light");
    return;
  }
  const p = hexToTriplet(colors.primary);
  const a = hexToTriplet(colors.accent);
  if (p) root.style.setProperty("--primary", p);
  if (a) root.style.setProperty("--primary-light", a);
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>("dark");
  const [colors, setColorsState] = useState<ThemeColors | null>(null);

  // Sync with whatever the no-FOUC script already applied to <html>.
  useEffect(() => {
    const current = document.documentElement.classList.contains("dark") ? "dark" : "light";
    setTheme(current);
    try {
      const raw = localStorage.getItem(COLORS_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && parsed.primary && parsed.accent) {
          setColorsState(parsed);
          applyColors(parsed); // init script also applies this pre-paint
        }
      }
    } catch {
      /* ignore */
    }
  }, []);

  const apply = useCallback((next: Theme) => {
    const root = document.documentElement;
    root.classList.toggle("dark", next === "dark");
    try {
      localStorage.setItem("axiom-theme", next);
    } catch {
      /* ignore */
    }
    setTheme(next);
  }, []);

  const toggle = useCallback(() => {
    apply(theme === "dark" ? "light" : "dark");
  }, [theme, apply]);

  const setColors = useCallback((c: ThemeColors) => {
    setColorsState(c);
    applyColors(c);
    try {
      localStorage.setItem(COLORS_KEY, JSON.stringify(c));
    } catch {
      /* ignore */
    }
  }, []);

  const resetColors = useCallback(() => {
    setColorsState(null);
    applyColors(null);
    try {
      localStorage.removeItem(COLORS_KEY);
    } catch {
      /* ignore */
    }
  }, []);

  return (
    <Ctx.Provider value={{ theme, toggle, colors, setColors, resetColors }}>
      {children}
    </Ctx.Provider>
  );
}

export function useTheme() {
  return useContext(Ctx);
}

// Runs before paint to avoid a flash of the wrong theme / brand colours.
export const themeInitScript = `
(function() {
  try {
    var t = localStorage.getItem('axiom-theme');
    if (!t) t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    if (t === 'dark') document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
  } catch (e) {
    document.documentElement.classList.add('dark');
  }
  try {
    var c = localStorage.getItem('axiom-colors');
    if (c) {
      var o = JSON.parse(c);
      var trip = function (h) {
        if (!h) return null;
        var m = /^#?([0-9a-fA-F]{6})$/.exec(('' + h).trim());
        if (!m) return null;
        var i = parseInt(m[1], 16);
        return ((i >> 16) & 255) + ' ' + ((i >> 8) & 255) + ' ' + (i & 255);
      };
      var p = trip(o.primary), a = trip(o.accent);
      if (p) document.documentElement.style.setProperty('--primary', p);
      if (a) document.documentElement.style.setProperty('--primary-light', a);
    }
  } catch (e) {}
})();
`;
