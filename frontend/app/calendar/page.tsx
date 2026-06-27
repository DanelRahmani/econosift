"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { CalendarEvent, CalendarResponse } from "@/lib/types";
import { Card, Skeleton, PageSkeleton } from "@/components/ui";
import { CalendarGrid } from "@/components/calendar/CalendarGrid";
import {
  CalendarFilters,
  type CalendarFilterState,
  type ImpactFilter,
  type TzDisplay,
} from "@/components/calendar/CalendarFilters";

// ─────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────

const INDEX_OPTS = [
  { key: "sp500", label: "S&P 500" },
  { key: "ndx", label: "Nasdaq-100" },
  { key: "dow", label: "Dow 30" },
] as const;
type IndexKey = (typeof INDEX_OPTS)[number]["key"];

// ─────────────────────────────────────────────
// Segmented control (local copy matching treemap style)
// ─────────────────────────────────────────────

function SegCtrl<T extends string>({
  opts,
  value,
  onChange,
}: {
  opts: readonly { key: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1">
      {opts.map((o) => (
        <button
          key={o.key}
          onClick={() => onChange(o.key)}
          className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
            value === o.key
              ? "bg-accent text-white"
              : "text-text-muted hover:bg-surface-alt"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────
// Week utilities
// ─────────────────────────────────────────────

/** Returns the Monday of the week containing `date` (treats Mon as day 0) */
function getWeekMonday(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay(); // 0 Sun .. 6 Sat
  const diff = day === 0 ? -6 : 1 - day; // shift to Monday
  d.setDate(d.getDate() + diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function addWeeks(monday: Date, n: number): Date {
  const d = new Date(monday);
  d.setDate(d.getDate() + n * 7);
  return d;
}

function toDateStr(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function getSunday(monday: Date): Date {
  const d = new Date(monday);
  d.setDate(d.getDate() + 6);
  return d;
}

function fmtWeekRange(monday: Date): string {
  const sunday = getSunday(monday);
  const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
  const s = monday.toLocaleDateString("en-US", opts);
  const e = sunday.toLocaleDateString("en-US", {
    ...opts,
    year: "numeric",
  });
  return `${s} – ${e}`;
}

// ─────────────────────────────────────────────
// Default filter state
// ─────────────────────────────────────────────

const ALL_CATEGORIES = new Set<CalendarEvent["category"]>([
  "macro",
  "earnings",
  "dividend",
  "ipo",
]);

function defaultFilters(): CalendarFilterState {
  return {
    categories: new Set(ALL_CATEGORIES),
    impact: 0,
    country: "",
    tz: "ET",
  };
}

// ─────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────

export default function CalendarPage() {
  // ── Navigation state ──────────────────────
  const [index, setIndex] = useState<IndexKey>("dow");
  const [monday, setMonday] = useState<Date>(() => getWeekMonday(new Date()));

  // ── Data state ────────────────────────────
  const [data, setData] = useState<CalendarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  // ── Filter state (in-memory, no refetch) ──
  const [filters, setFilters] = useState<CalendarFilterState>(defaultFilters);

  // ── Fetch ─────────────────────────────────
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(false);

    const start = toDateStr(monday);
    const end = toDateStr(getSunday(monday));

    api
      .calendar(index, start, end)
      .then((r) => {
        if (alive) setData(r);
      })
      .catch(() => {
        if (alive) setError(true);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [index, monday]);

  // ── Derived: merge + derive countries ─────
  const allEvents = useMemo<CalendarEvent[]>(() => {
    if (!data) return [];
    return [
      ...data.macro,
      ...data.earnings,
      ...data.dividends,
      ...data.ipos,
    ];
  }, [data]);

  const countries = useMemo<string[]>(() => {
    const set = new Set<string>();
    for (const ev of allEvents) {
      if (ev.country) set.add(ev.country);
    }
    return Array.from(set).sort();
  }, [allEvents]);

  // ── Derived: apply filters ─────────────────
  const visibleEvents = useMemo<CalendarEvent[]>(() => {
    return allEvents.filter((ev) => {
      if (!filters.categories.has(ev.category)) return false;
      if (filters.impact !== 0) {
        if (ev.impact === null || ev.impact < filters.impact) return false;
      }
      if (filters.country && ev.country !== filters.country) return false;
      return true;
    });
  }, [allEvents, filters]);

  // ── Filter handlers ────────────────────────
  const handleCategoryToggle = useCallback(
    (cat: CalendarEvent["category"]) => {
      setFilters((prev) => {
        const next = new Set(prev.categories);
        if (next.has(cat)) {
          next.delete(cat);
        } else {
          next.add(cat);
        }
        return { ...prev, categories: next };
      });
    },
    []
  );

  const handleImpactChange = useCallback((v: ImpactFilter) => {
    setFilters((prev) => ({ ...prev, impact: v }));
  }, []);

  const handleCountryChange = useCallback((v: string) => {
    setFilters((prev) => ({ ...prev, country: v }));
  }, []);

  const handleTzChange = useCallback((v: TzDisplay) => {
    setFilters((prev) => ({ ...prev, tz: v }));
  }, []);

  // ── Week navigation ────────────────────────
  const isCurrentWeek =
    toDateStr(monday) === toDateStr(getWeekMonday(new Date()));

  // ── Render ─────────────────────────────────
  return (
    <div className="space-y-6">
      {/* Heading */}
      <div>
        <h1 className="text-xl font-bold text-text-primary">
          Economic Calendar
        </h1>
        <p className="text-sm text-text-muted mt-0.5">
          Week of {fmtWeekRange(monday)}
        </p>
      </div>

      {/* Controls */}
      <Card>
        <div className="space-y-4">
          {/* Row 1: index + week nav */}
          <div className="flex flex-wrap gap-x-6 gap-y-3 items-center">
            <div className="flex items-center gap-2">
              <span className="text-xs text-text-muted font-medium">Index</span>
              <SegCtrl opts={INDEX_OPTS} value={index} onChange={setIndex} />
            </div>

            {/* Week navigation */}
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setMonday((m) => addWeeks(m, -1))}
                className="px-2.5 py-1 rounded-md text-xs font-medium text-text-muted hover:bg-surface-alt transition-colors"
                aria-label="Previous week"
              >
                ◀ Prev
              </button>
              <button
                onClick={() => setMonday(getWeekMonday(new Date()))}
                disabled={isCurrentWeek}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  isCurrentWeek
                    ? "text-text-muted opacity-40 cursor-default"
                    : "text-text-muted hover:bg-surface-alt"
                }`}
              >
                This Week
              </button>
              <button
                onClick={() => setMonday((m) => addWeeks(m, 1))}
                className="px-2.5 py-1 rounded-md text-xs font-medium text-text-muted hover:bg-surface-alt transition-colors"
                aria-label="Next week"
              >
                Next ▶
              </button>
            </div>
          </div>

          {/* Row 2: filters */}
          <CalendarFilters
            filters={filters}
            countries={countries}
            onCategoryToggle={handleCategoryToggle}
            onImpactChange={handleImpactChange}
            onCountryChange={handleCountryChange}
            onTzChange={handleTzChange}
          />

          {/* API key notices */}
          {data && (!data.sources.finnhub || !data.sources.fred) && (
            <div className="flex flex-wrap gap-3">
              {!data.sources.finnhub && (
                <p className="text-[11px] text-text-muted">
                  IPOs require a Finnhub API key.
                </p>
              )}
              {!data.sources.fred && (
                <p className="text-[11px] text-text-muted">
                  FRED release calendar requires a FRED API key.
                </p>
              )}
            </div>
          )}
        </div>
      </Card>

      {/* Body */}
      {loading && !data ? (
        <PageSkeleton text="Loading calendar…" />
      ) : error || !data ? (
        <Card>
          <div className="text-text-muted text-sm py-10 text-center">
            {error
              ? "Calendar data unavailable — the backend may be loading or unreachable."
              : "No calendar data returned."}
          </div>
        </Card>
      ) : (
        <Card>
          <CalendarGrid events={visibleEvents} monday={monday} />
        </Card>
      )}
    </div>
  );
}
