"use client";

import type { CalendarEvent } from "@/lib/types";
import { EventCard } from "./EventCard";

// ─────────────────────────────────────────────
// Category legend
// ─────────────────────────────────────────────

const CATEGORY_META: {
  key: CalendarEvent["category"];
  label: string;
  dot: string;
}[] = [
  { key: "macro", label: "Macro", dot: "bg-blue-500" },
  { key: "earnings", label: "Earnings", dot: "bg-yellow-500" },
  { key: "dividend", label: "Dividend", dot: "bg-green-600" },
  { key: "ipo", label: "IPO", dot: "bg-purple-500" },
];

function CategoryLegend() {
  return (
    <div className="flex flex-wrap gap-4 items-center">
      {CATEGORY_META.map((c) => (
        <div key={c.key} className="flex items-center gap-1.5">
          <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${c.dot}`} />
          <span className="text-xs text-text-muted">{c.label}</span>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** Returns YYYY-MM-DD for a given Date */
function toDateStr(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Today's date string */
function todayStr(): string {
  return toDateStr(new Date());
}

/** Generate the 7-day range [monday .. sunday] as Date objects */
function weekDates(monday: Date): Date[] {
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(d.getDate() + i);
    return d;
  });
}

/** Format a Date as "Jun 24" style */
function fmtDayHeader(d: Date): string {
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// ─────────────────────────────────────────────
// CalendarGrid
// ─────────────────────────────────────────────

interface CalendarGridProps {
  events: CalendarEvent[];
  monday: Date; // first day of the visible week
}

export function CalendarGrid({ events, monday }: CalendarGridProps) {
  const days = weekDates(monday);
  const today = todayStr();

  // Group events by date
  const byDate: Record<string, CalendarEvent[]> = {};
  for (const ev of events) {
    if (!byDate[ev.date]) byDate[ev.date] = [];
    byDate[ev.date].push(ev);
  }

  // Sort within each day: macro first, then earnings, dividends, ipos
  const ORDER: Record<CalendarEvent["category"], number> = {
    macro: 0,
    earnings: 1,
    dividend: 2,
    ipo: 3,
  };
  for (const arr of Object.values(byDate)) {
    arr.sort((a, b) => ORDER[a.category] - ORDER[b.category]);
  }

  const totalEvents = events.length;

  return (
    <div className="space-y-3">
      {/* Legend */}
      <CategoryLegend />

      {/* Grid: horizontal scroll on mobile */}
      <div className="overflow-x-auto -mx-1">
        <div className="min-w-[700px] grid grid-cols-7 gap-1.5 px-1">
          {/* Day headers */}
          {days.map((d, i) => {
            const ds = toDateStr(d);
            const isToday = ds === today;
            return (
              <div
                key={ds}
                className={`text-center py-1 rounded-md text-xs font-semibold ${
                  isToday
                    ? "bg-accent/20 text-accent ring-1 ring-accent"
                    : "text-text-muted"
                }`}
              >
                <div>{WEEKDAYS[i]}</div>
                <div className="font-normal text-[10px]">{fmtDayHeader(d)}</div>
              </div>
            );
          })}

          {/* Day columns with events */}
          {days.map((d) => {
            const ds = toDateStr(d);
            const isToday = ds === today;
            const dayEvents = byDate[ds] ?? [];

            return (
              <div
                key={`col-${ds}`}
                className={`rounded-md min-h-[120px] max-h-[480px] overflow-y-auto flex flex-col gap-1 p-1 ${
                  isToday
                    ? "bg-accent/5 ring-1 ring-accent/30"
                    : "bg-surface-alt/40"
                }`}
              >
                {dayEvents.length === 0 ? (
                  <div className="flex-1 flex items-center justify-center">
                    <span className="text-[10px] text-text-muted opacity-40">
                      —
                    </span>
                  </div>
                ) : (
                  dayEvents.map((ev, idx) => (
                    <EventCard key={`${ev.date}-${ev.category}-${ev.title}-${idx}`} event={ev} />
                  ))
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Summary */}
      {totalEvents === 0 && (
        <p className="text-center text-text-muted text-sm py-6">
          No events match the current filters for this week.
        </p>
      )}
    </div>
  );
}
