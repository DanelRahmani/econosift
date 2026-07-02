"use client";
import { useRef, useState, useEffect, type ReactNode } from "react";
import { RadialBarChart, RadialBar, PolarAngleAxis, ResponsiveContainer } from "recharts";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>;
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

// ── Scrollable tab bar with auto-show left/right arrows ─────────────────────

export function ScrollableTabBar({ children, className = "" }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [overflow, setOverflow] = useState<"left" | "right" | "both" | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const check = () => {
      const canScrollLeft = el.scrollLeft > 1;
      const canScrollRight = el.scrollLeft + el.clientWidth < el.scrollWidth - 1;
      if (canScrollLeft && canScrollRight) setOverflow("both");
      else if (canScrollLeft) setOverflow("left");
      else if (canScrollRight) setOverflow("right");
      else setOverflow(null);
    };
    check();
    const ro = new ResizeObserver(check);
    ro.observe(el);
    el.addEventListener("scroll", check, { passive: true });
    return () => { ro.disconnect(); el.removeEventListener("scroll", check); };
  }, []);

  function scroll(amount: number) {
    ref.current?.scrollBy({ left: amount, behavior: "smooth" });
  }

  return (
    <div className={`relative ${className}`}>
      {overflow && (overflow === "left" || overflow === "both") && (
        <button onClick={() => scroll(-200)}
          className="absolute left-0 top-1/2 -translate-y-1/2 z-10 w-7 h-7 flex items-center justify-center rounded-full bg-surface border border-border shadow hover:bg-surface-alt transition-colors"
          aria-label="Scroll tabs left">
          <svg className="w-3.5 h-3.5 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" /></svg>
        </button>
      )}
      <div ref={ref} className="flex overflow-x-auto no-scrollbar gap-0">
        {children}
      </div>
      {overflow && (overflow === "right" || overflow === "both") && (
        <button onClick={() => scroll(200)}
          className="absolute right-0 top-1/2 -translate-y-1/2 z-10 w-7 h-7 flex items-center justify-center rounded-full bg-surface border border-border shadow hover:bg-surface-alt transition-colors"
          aria-label="Scroll tabs right">
          <svg className="w-3.5 h-3.5 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
        </button>
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
      className={`px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
        active ? "border-accent text-accent" : "border-transparent text-text-secondary hover:text-text-primary"
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
      className={`px-2 py-0.5 rounded text-xs font-mono transition-colors border ${
        active ? "bg-accent/20 text-accent border-accent/40" : "text-text-muted border-border hover:text-text-primary"
      } ${className}`}
    >
      {children}
    </button>
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
    <div className={`${height} w-full animate-pulse bg-surface-alt rounded-xl`} />
  );
}

// Theme-aware chart colors. Recharts needs concrete values, so we resolve them
// from the active theme rather than relying on CSS variables in SVG.
export function chartPalette(theme: "light" | "dark") {
  return theme === "dark"
    ? { grid: "#2a2a30", axis: "#aeaeba", tooltipBg: "#1a1a1e", tooltipBorder: "#c4394a", tooltipText: "#f2f2f7" }
    : { grid: "#e4e4ea", axis: "#8c8c96", tooltipBg: "#ffffff", tooltipBorder: "#6b0f1a", tooltipText: "#0f0f14" };
}

export function chartTooltipStyle(theme: "light" | "dark" = "dark") {
  const p = chartPalette(theme);
  return {
    contentStyle: {
      backgroundColor: p.tooltipBg,
      border: `1px solid ${p.tooltipBorder}`,
      borderRadius: "8px",
      color: p.tooltipText,
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
