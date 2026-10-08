"use client";
import { useRef, useState, useEffect, type HTMLAttributes, type ReactNode } from "react";
import { RadialBarChart, RadialBar, PolarAngleAxis, ResponsiveContainer } from "recharts";

export function Card({
  children,
  className = "",
  ...rest
}: { children: ReactNode; className?: string } & HTMLAttributes<HTMLDivElement>) {
  return <div className={`card ${className}`} {...rest}>{children}</div>;
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

export function SignalBadge({ signal }: { signal: string }) {
  const map: Record<string, string> = {
    BUY: "bg-success/20 text-success",
    OVERVALUED: "bg-danger/20 text-danger",
    "FAIR VALUE": "bg-text-muted/20 text-text-secondary",
    INCOMPLETE: "bg-warning/20 text-warning",
  };
  return (
    <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${map[signal] || map.INCOMPLETE}`}>
      {signal}
    </span>
  );
}

export function ZScoreBadge({ z }: { z: number | null }) {
  if (z === null || Number.isNaN(z)) {
    return <span className="px-2 py-0.5 rounded-md text-xs font-semibold bg-text-muted/20 text-text-secondary">—</span>;
  }
  let cls = "bg-danger/20 text-danger";
  let label = "Distress";
  if (z > 2.99) {
    cls = "bg-success/20 text-success";
    label = "Safe";
  } else if (z >= 1.81) {
    cls = "bg-warning/20 text-warning";
    label = "Grey Zone";
  }
  return (
    <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${cls}`}>
      {z.toFixed(2)} · {label}
    </span>
  );
}

export function PageSkeleton({ text = "Loading…" }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-3">
      <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      <span className="text-sm text-text-muted">{text}</span>
    </div>
  );
}

// ── Scrollable tab bar: arrows + edge fades appear only where there is overflow ──

const SCROLL_FADE_PX = 40;

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Horizontal tab strip. The scrollbar is hidden, so overflow is signalled with
 * an edge fade + arrow button on each overflowing side. Also: vertical mouse
 * wheel scrolls it sideways (only while it can still move in that direction),
 * and the active tab (child marked `data-active="true"` or `aria-selected="true"`)
 * is kept in view. Pass sticky/background classes via `className`, tab gap via `innerClassName`.
 */
export function ScrollableTabBar({ children, className = "", innerClassName = "gap-0" }: { children: ReactNode; className?: string; innerClassName?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const lastActive = useRef<Element | null>(null);
  const [canLeft, setCanLeft] = useState(false);
  const [canRight, setCanRight] = useState(false);

  const check = () => {
    const el = ref.current;
    if (!el) return;
    setCanLeft(el.scrollLeft > 1);
    setCanRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
  };

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    check();
    const ro = new ResizeObserver(check);
    ro.observe(el);
    Array.from(el.children).forEach((c) => ro.observe(c));
    const onWheel = (e: WheelEvent) => {
      if (Math.abs(e.deltaX) >= Math.abs(e.deltaY) || e.ctrlKey) return; // native horizontal gesture / pinch-zoom
      const max = el.scrollWidth - el.clientWidth;
      if (max <= 1) return; // no overflow: leave page scroll alone
      const dy = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
      if ((dy < 0 && el.scrollLeft <= 0) || (dy > 0 && el.scrollLeft >= max - 1)) return; // at the end: let page scroll
      e.preventDefault();
      el.scrollLeft += dy;
    };
    el.addEventListener("scroll", check, { passive: true });
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      ro.disconnect();
      el.removeEventListener("scroll", check);
      el.removeEventListener("wheel", onWheel);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // After every render: tabs may have changed width, and the active tab may have changed.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    check();
    const active = el.querySelector('[data-active="true"], [aria-selected="true"]');
    if (!active || active === lastActive.current) return;
    const first = lastActive.current === null;
    lastActive.current = active;
    const box = el.getBoundingClientRect();
    const r = active.getBoundingClientRect();
    const pad = SCROLL_FADE_PX;
    let delta = 0;
    if (r.left < box.left + pad) delta = r.left - box.left - pad;
    else if (r.right > box.right - pad) delta = r.right - box.right + pad;
    if (delta) {
      el.scrollBy({ left: delta, behavior: first || prefersReducedMotion() ? "auto" : "smooth" });
    }
  });

  function scrollByPage(dir: -1 | 1) {
    const el = ref.current;
    if (!el) return;
    el.scrollBy({ left: dir * el.clientWidth * 0.8, behavior: prefersReducedMotion() ? "auto" : "smooth" });
  }

  const arrowCls =
    "absolute top-1/2 -translate-y-1/2 z-10 w-7 h-7 flex items-center justify-center rounded-full bg-surface border border-border shadow hover:bg-surface-alt transition-colors";

  return (
    <div className={`relative min-w-0 ${className}`}>
      {canLeft && (
        <>
          <div aria-hidden className="pointer-events-none absolute left-0 inset-y-0 z-10 w-10 bg-gradient-to-r from-background to-transparent" />
          <button type="button" tabIndex={-1} onClick={() => scrollByPage(-1)} className={`${arrowCls} left-0`} aria-label="Scroll tabs left">
            <svg className="w-3.5 h-3.5 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" /></svg>
          </button>
        </>
      )}
      <div ref={ref} className={`flex overflow-x-auto no-scrollbar ${innerClassName}`}>
        {children}
      </div>
      {canRight && (
        <>
          <div aria-hidden className="pointer-events-none absolute right-0 inset-y-0 z-10 w-10 bg-gradient-to-l from-background to-transparent" />
          <button type="button" tabIndex={-1} onClick={() => scrollByPage(1)} className={`${arrowCls} right-0`} aria-label="Scroll tabs right">
            <svg className="w-3.5 h-3.5 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
          </button>
        </>
      )}
    </div>
  );
}

// ── Shared tab / toggle primitives ──────────────────────────────────────────

export function TabButton({
  active,
  onClick,
  children,
  className = "",
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <button
      onClick={onClick}
      data-active={active}
      className={`relative px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 border-transparent transition-colors duration-200 after:absolute after:inset-x-3 after:-bottom-0.5 after:h-0.5 after:rounded-full after:bg-accent-light after:shadow-[0_0_12px_rgb(var(--primary-light)/0.8)] after:transition-transform after:duration-300 after:ease-[cubic-bezier(0.22,1,0.36,1)] ${
        active ? "text-text-primary after:scale-x-100" : "text-text-secondary hover:text-text-primary after:scale-x-0 hover:after:scale-x-50 hover:after:opacity-40"
      } ${className}`}
    >
      {children}
    </button>
  );
}

export function ToggleChip({
  active,
  onClick,
  children,
  className = "",
  title,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={`px-2 py-0.5 rounded-md text-xs font-mono transition-all duration-200 border ${
        active
          ? "bg-accent-light/15 text-accent-light border-accent-light/40 shadow-[0_0_14px_-4px_rgb(var(--primary-light)/0.6)]"
          : "text-text-muted border-border hover:text-text-primary hover:border-text-muted/40"
      } ${className}`}
    >
      {children}
    </button>
  );
}

/**
 * One KPI card: small label, big value, optional sub-line. Renders "—" for a
 * null/undefined/empty value. `tone` colours the value with the theme success/danger
 * token. `prov` / `ctx` become `data-prov` / `data-prov-ctx` so right-click → Source
 * works on the tile. Group tiles in a `KpiStrip`.
 */
export function KpiTile({
  label,
  value,
  sub,
  tone = "neutral",
  prov,
  ctx,
  title,
}: {
  label: ReactNode;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "up" | "down" | "neutral";
  prov?: string;
  ctx?: string;
  title?: string;
}) {
  const toneClass = tone === "up" ? "text-success" : tone === "down" ? "text-danger" : "";
  const empty = value === null || value === undefined || value === "";
  return (
    <Card className="p-4" data-prov={prov} data-prov-ctx={ctx} title={title}>
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${toneClass}`}>{empty ? "—" : value}</div>
      {sub != null && sub !== "" && <div className="text-xs text-text-secondary mt-0.5">{sub}</div>}
    </Card>
  );
}

/**
 * Responsive grid for a row of `KpiTile`s (2 columns on mobile, `cols` from the sm
 * breakpoint up; default 4, allowed 3-6).
 */
export function KpiStrip({ children, cols = 4 }: { children: ReactNode; cols?: 3 | 4 | 5 | 6 }) {
  const colClass = {
    3: "sm:grid-cols-3",
    4: "sm:grid-cols-4",
    5: "sm:grid-cols-3 lg:grid-cols-5",
    6: "sm:grid-cols-3 lg:grid-cols-6",
  }[cols];
  return <div className={`grid grid-cols-2 ${colClass} gap-3`}>{children}</div>;
}

/**
 * The row that holds a page's controls (selects, toggle chips, buttons): wraps on
 * narrow screens, items centred, with a bottom margin. Renders `role="toolbar"`.
 */
export function ControlBar({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div role="toolbar" className={`flex flex-wrap items-center gap-2 mb-4 ${className}`}>
      {children}
    </div>
  );
}

// ── Export PDF button ───────────────────────────────────────────────────────
export function ExportPdfButton({ className = "" }: { className?: string }) {
  return (
    <button
      onClick={() => window.print()}
      data-hide-print
      className={`px-3 py-1.5 rounded-lg text-xs font-medium border border-border text-text-secondary hover:text-text-primary hover:bg-surface-alt transition-colors ${className}`}
      title="Export page as PDF"
    >
      <span className="flex items-center gap-1.5">
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        PDF
      </span>
    </button>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <span className="text-3xl mb-3 opacity-40">—</span>
      <h3 className="text-sm font-medium text-text-secondary">{title}</h3>
      {description && <p className="text-xs text-text-muted mt-1 max-w-xs">{description}</p>}
    </div>
  );
}

export function ChartSkeleton({ height = "h-80" }: { height?: string }) {
  return (
    <div className={`${height} w-full skeleton rounded-xl`} />
  );
}

// Theme-aware chart colors. Recharts needs concrete values, so we resolve them
// from the active theme rather than relying on CSS variables in SVG.
export function chartPalette(theme: "light" | "dark") {
  return theme === "dark"
    ? { grid: "#24242a", axis: "#aeaeba", tooltipBg: "#131317", tooltipBorder: "#2F8F83", tooltipText: "#f4f4f7" }
    : { grid: "#e4e4ea", axis: "#8c8c96", tooltipBg: "#ffffff", tooltipBorder: "#142A43", tooltipText: "#0f0f14" };
}

export function chartTooltipStyle(theme: "light" | "dark" = "dark") {
  const p = chartPalette(theme);
  return {
    contentStyle: {
      backgroundColor: p.tooltipBg,
      border: `1px solid ${p.tooltipBorder}`,
      borderRadius: "10px",
      color: p.tooltipText,
      boxShadow: "0 12px 32px -12px rgb(0 0 0 / 0.45)",
    },
    labelStyle: { color: p.axis },
  };
}

// ── Semicircular gauge ───────────────────────────────────────────────────────
// A single smooth 0–100 progress arc with a rounded cap and background track,
// built on Recharts' RadialBarChart (already a dependency). Replaces the old
// hand-drawn multi-segment-arc-plus-needle SVGs, whose banded colors and
// needle pivot text tended to collide. Pass `children` for the centered
// readout (big number / label) — absolutely positioned under the arc since
// Recharts lays out only the SVG, not HTML overlays.
export function SemiGauge({
  value,
  color,
  trackColor,
  size = 200,
  strokeWidth = 16,
  children,
}: {
  value: number; // 0–100
  color: string;
  trackColor: string;
  size?: number;
  strokeWidth?: number;
  children?: ReactNode;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const height = size / 2 + strokeWidth / 2 + 4;

  return (
    <div className="relative mx-auto" style={{ width: size, height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadialBarChart
          cx="50%"
          cy="100%"
          innerRadius={size / 2 - strokeWidth}
          outerRadius={size / 2}
          barSize={strokeWidth}
          startAngle={180}
          endAngle={0}
          data={[{ value: clamped, fill: color }]}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} tick={false} axisLine={false} />
          <RadialBar
            dataKey="value"
            cornerRadius={strokeWidth / 2}
            background={{ fill: trackColor }}
            isAnimationActive={false}
          />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="absolute inset-x-0 bottom-0 pb-1 pointer-events-none">
        {children}
      </div>
    </div>
  );
}
