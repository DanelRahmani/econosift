import type { ReactNode } from "react";

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

// Theme-aware chart colors. Recharts needs concrete values, so we resolve them
// from the active theme rather than relying on CSS variables in SVG.
export function chartPalette(theme: "light" | "dark") {
  return theme === "dark"
    ? { grid: "#32171c", axis: "#c49aa0", tooltipBg: "#1a0a0c", tooltipBorder: "#c4394a", tooltipText: "#f5eeef" }
    : { grid: "#ecdcdf", axis: "#8a6770", tooltipBg: "#ffffff", tooltipBorder: "#6b0f1a", tooltipText: "#1a0a0c" };
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
