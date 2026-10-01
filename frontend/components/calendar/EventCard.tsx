"use client";

import { useEffect, useState } from "react";
import type { CalendarEvent } from "@/lib/types";
import { fmtNum, fmtPct } from "@/lib/format";

// ─────────────────────────────────────────────
// Category style config
// ─────────────────────────────────────────────

const CATEGORY_STYLES: Record<
  CalendarEvent["category"],
  { border: string; dot: string; label: string }
> = {
  macro: {
    border: "border-l-blue-500",
    dot: "bg-blue-500",
    label: "Macro",
  },
  earnings: {
    border: "border-l-yellow-500",
    dot: "bg-yellow-500",
    label: "Earnings",
  },
  dividend: {
    border: "border-l-green-600",
    dot: "bg-green-600",
    label: "Dividend",
  },
  ipo: {
    border: "border-l-purple-500",
    dot: "bg-purple-500",
    label: "IPO",
  },
};

// Provenance map key per event category (events carry no per-row source).
const PROV_KEYS: Record<CalendarEvent["category"], string> = {
  macro: "macro",
  earnings: "earnings",
  dividend: "dividends",
  ipo: "ipos",
};

// ─────────────────────────────────────────────
// Countdown logic
// ─────────────────────────────────────────────

/** Returns ET offset as minutes from UTC (ET = UTC-5 standard, UTC-4 DST). */
function getETOffsetMinutes(): number {
  // Approximate: check if we're in DST by comparing January offset
  const jan = new Date(Date.now());
  jan.setMonth(0, 1);
  const janOffset = new Date(jan).getTimezoneOffset();
  const nowOffset = new Date().getTimezoneOffset();
  // ET is UTC-5 (300 min) standard, UTC-4 (240 min) DST
  return nowOffset < janOffset ? 240 : 300;
}

function getEventTimestamp(event: CalendarEvent): number | null {
  // Build a UTC timestamp for the event
  const [year, month, day] = event.date.split("-").map(Number);
  let etHour = 0;
  let etMinute = 0;

  if (event.category === "earnings") {
    if (event.time === "bmo") {
      etHour = 9;
      etMinute = 30;
    } else if (event.time === "amc") {
      etHour = 16;
      etMinute = 0;
    } else {
      etHour = 9;
      etMinute = 30;
    }
  }

  const etOffsetMin = getETOffsetMinutes();
  // Convert ET time to UTC
  const utcMs =
    Date.UTC(year, month - 1, day, etHour, etMinute) +
    etOffsetMin * 60 * 1000;
  return utcMs;
}

function useCountdown(event: CalendarEvent): string | null {
  const [countdown, setCountdown] = useState<string | null>(null);

  useEffect(() => {
    if (event.category !== "earnings" && event.category !== "macro") {
      return;
    }

    const targetMs = getEventTimestamp(event);
    if (targetMs === null) return;

    function compute() {
      if (targetMs === null) return;
      const now = Date.now();
      const diffMs = targetMs - now;
      const diffH = diffMs / (1000 * 60 * 60);
      if (diffH >= 0 && diffH <= 24) {
        const h = Math.floor(diffMs / (1000 * 60 * 60));
        const m = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
        setCountdown(h > 0 ? `in ${h}h ${m}m` : `in ${m}m`);
      } else {
        setCountdown(null);
      }
    }

    compute();
    const id = setInterval(compute, 60_000);
    return () => clearInterval(id);
  }, [event]);

  return countdown;
}

// ─────────────────────────────────────────────
// Beat/miss badge
// ─────────────────────────────────────────────

function BeatMissBadge({
  bm,
}: {
  bm: CalendarEvent["beatMiss"];
}) {
  if (!bm) return null;
  const styles: Record<string, string> = {
    beat: "bg-green-500/20 text-green-400",
    miss: "bg-red-500/20 text-red-400",
    inline: "bg-surface-alt text-text-muted",
  };
  return (
    <span
      className={`text-[10px] px-1.5 py-0.5 rounded font-semibold uppercase ${
        styles[bm] ?? styles.inline
      }`}
    >
      {bm}
    </span>
  );
}

// ─────────────────────────────────────────────
// EventCard
// ─────────────────────────────────────────────

export function EventCard({ event }: { event: CalendarEvent }) {
  const style = CATEGORY_STYLES[event.category];
  const countdown = useCountdown(event);

  return (
    <div
      className={`border-l-2 ${style.border} bg-surface rounded-r-md px-2 py-1.5 text-xs space-y-0.5`}
      data-prov={PROV_KEYS[event.category]}
      data-prov-ctx={event.title}
    >
      {/* Title row */}
      <div className="flex items-start justify-between gap-1">
        <span className="text-text-primary font-medium leading-tight">
          {event.title}
        </span>
        {countdown && (
          <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-accent/20 text-accent font-mono whitespace-nowrap">
            {countdown}
          </span>
        )}
      </div>

      {/* Badges row */}
      <div className="flex flex-wrap items-center gap-1">
        {event.ticker && (
          <span className="px-1.5 py-0.5 rounded bg-surface-alt text-text-secondary font-mono text-[10px]">
            {event.ticker}
          </span>
        )}
        {event.category === "earnings" && event.time && (
          <span className="px-1.5 py-0.5 rounded bg-surface-alt text-text-muted text-[10px] uppercase">
            {event.time}
          </span>
        )}
        <BeatMissBadge bm={event.beatMiss} />
        {event.impact && (
          <span className="text-yellow-400 text-[10px]">
            {"★".repeat(event.impact)}
          </span>
        )}
      </div>

      {/* Earnings detail */}
      {event.category === "earnings" &&
        (event.epsEstimate !== null || event.epsActual !== null) && (
          <div className="text-text-muted text-[10px] space-x-2">
            {event.epsEstimate !== null && (
              <span>Est: ${fmtNum(event.epsEstimate)}</span>
            )}
            {event.epsActual !== null && (
              <span
                className={
                  event.beatMiss === "beat"
                    ? "text-green-400"
                    : event.beatMiss === "miss"
                    ? "text-red-400"
                    : "text-text-secondary"
                }
              >
                Act: ${fmtNum(event.epsActual)}
              </span>
            )}
            {event.surprisePct !== null && (
              <span
                className={
                  event.beatMiss === "beat"
                    ? "text-green-400"
                    : event.beatMiss === "miss"
                    ? "text-red-400"
                    : "text-text-muted"
                }
              >
                ({event.surprisePct > 0 ? "+" : ""}
                {fmtPct(event.surprisePct)})
              </span>
            )}
          </div>
        )}

      {/* Dividend detail */}
      {event.category === "dividend" && event.amount !== null && (
        <div className="text-text-muted text-[10px]">
          Annual rate: ${fmtNum(event.amount, 4)}/sh
        </div>
      )}

      {/* IPO detail */}
      {event.category === "ipo" && (
        <div className="text-text-muted text-[10px] space-x-2">
          {event.exchange && <span>{event.exchange}</span>}
          {event.amount !== null && <span>~${fmtNum(event.amount)}</span>}
        </div>
      )}

      {/* Country */}
      {event.country && (
        <div className="text-text-muted text-[10px]">{event.country}</div>
      )}
    </div>
  );
}
