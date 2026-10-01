"use client";

import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer,
} from "recharts";
import { Card } from "@/components/ui";
import { api } from "@/lib/api";
import type { EventStudyData } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

const WINDOWS = [3, 5, 10] as const;
type WindowSize = (typeof WINDOWS)[number];

const EVENT_TYPES = [
  { key: "earnings", label: "Earnings" },
  { key: "fomc", label: "FOMC" },
] as const;
type EventType = (typeof EVENT_TYPES)[number]["key"];

const tooltipStyle = {
  backgroundColor: "var(--color-surface-alt)",
  border: "1px solid var(--color-border)",
  borderRadius: 8,
  fontSize: 12,
};

function pct(v: number | null | undefined, dp = 2): string {
  return v === null || v === undefined ? "—" : `${(v * 100).toFixed(dp)}%`;
}

function Kpi({ label, value, color, prov }: { label: string; value: string; color?: string; prov?: string }) {
  return (
    <Card className="p-4" data-prov={prov}>
      <div className="text-xs text-text-muted">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${color ?? ""}`}>{value}</div>
    </Card>
  );
}

export function EventStudyTab() {
  const [ticker, setTicker] = useState("AAPL");
  const [eventType, setEventType] = useState<EventType>("earnings");
  const [windowSize, setWindowSize] = useState<WindowSize>(5);
  const [data, setData] = useState<EventStudyData | null>(null);
  const [loading, setLoading] = useState(false);
  const scope = useSourceScope(provOf(data));

  const run = () => {
    const t = ticker.trim().toUpperCase();
    if (!t) return;
    setLoading(true);
    api.researchEventStudy({ ticker: t, eventType, window: windowSize })
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };

  const kpis = data && !data.error ? data.kpis : null;
  const carPathRows = (data?.carPath ?? []).map((p) => ({ day: p.day, avgCar: (p.avgCar ?? 0) * 100 }));
  const eventRows = [...(data?.events ?? [])].reverse();

  return (
    <div className="space-y-6" {...scope}>
      <Card>
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-xs text-text-muted mb-1">Ticker</label>
            <input
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              onKeyDown={(e) => { if (e.key === "Enter") run(); }}
              className="px-2.5 py-1.5 rounded-md text-sm font-mono bg-surface-alt border border-border w-28"
              placeholder="AAPL"
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Event Type</label>
            <div className="flex gap-1">
              {EVENT_TYPES.map((e) => (
                <button key={e.key} onClick={() => setEventType(e.key)}
                  className={`px-2.5 py-1 rounded-md text-xs ${eventType === e.key ? "bg-accent text-white" : "text-text-muted hover:text-text-primary"}`}>
                  {e.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Window (± trading days)</label>
            <div className="flex gap-1">
              {WINDOWS.map((w) => (
                <button key={w} onClick={() => setWindowSize(w)}
                  className={`px-2.5 py-1 rounded-md text-xs font-mono ${windowSize === w ? "bg-surface-alt text-text-primary" : "text-text-muted hover:text-text-primary"}`}>
                  ±{w}
                </button>
              ))}
            </div>
          </div>
          <button onClick={run} disabled={loading}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-500 text-white hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
            {loading ? "Running…" : "🟡 Run Event Study"}
          </button>
        </div>
        <p className="text-xs text-text-muted mt-2">
          Market-model CAR/AAR: abnormal return = actual − (α + β·market), with α/β estimated over a
          trailing window ending 10 trading days before each event.
        </p>
      </Card>

      {!data && !loading && (
        <Card><p className="text-sm text-text-muted">Choose a ticker and event type, then run the study.</p></Card>
      )}

      {loading && <div className="h-72 animate-pulse bg-surface-alt rounded-lg" />}

      {!loading && data?.error && (
        <Card><p className="text-sm text-text-muted">Event study unavailable: {data.error}</p></Card>
      )}

      {!loading && data && !data.error && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Kpi
              prov="kpis"
              label="Mean CAR"
              value={pct(kpis?.meanCar)}
              color={kpis?.meanCar != null ? (kpis.meanCar >= 0 ? "text-success" : "text-danger") : undefined}
            />
            <Kpi prov="kpis" label="Hit Rate" value={kpis?.hitRate != null ? `${kpis.hitRate.toFixed(1)}%` : "—"} />
            <Kpi prov="kpis" label="t-Stat" value={kpis?.tStat != null ? kpis.tStat.toFixed(2) : "—"} />
            <Kpi prov="events" label="N Events" value={String(data.nEvents ?? 0)} />
          </div>

          <Card data-prov="carPath">
            <h3 className="text-sm font-semibold text-text-secondary mb-3">Average Cumulative Abnormal Return</h3>
            {carPathRows.length === 0 ? (
              <p className="text-sm text-text-muted">No data.</p>
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={carPathRows} margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="day" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                  <YAxis tickFormatter={(v) => `${v.toFixed(1)}%`} tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                  <Tooltip formatter={(v: number) => [`${v.toFixed(2)}%`, "Avg CAR"]} labelFormatter={(d) => `Day ${d}`} contentStyle={tooltipStyle} />
                  <ReferenceLine x={0} stroke="var(--color-text-muted)" strokeDasharray="3 3" />
                  <ReferenceLine y={0} stroke="var(--color-text-muted)" strokeDasharray="3 3" />
                  <Line type="monotone" dataKey="avgCar" stroke="#6366f1" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Card>

          <Card data-prov="events">
            <h3 className="text-sm font-semibold text-text-secondary mb-3">Individual Events</h3>
            {eventRows.length === 0 ? (
              <p className="text-sm text-text-muted">No events.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-text-secondary border-b border-border">
                      <th className="py-1.5 pr-3">Date</th>
                      <th className="py-1.5 pr-3 text-right">Event-Day Return</th>
                      <th className="py-1.5 text-right">CAR</th>
                    </tr>
                  </thead>
                  <tbody>
                    {eventRows.map((ev) => (
                      <tr key={ev.date} className="border-b border-border/50">
                        <td className="py-1.5 pr-3">{ev.date}</td>
                        <td className="py-1.5 pr-3 text-right">{pct(ev.eventDayReturn)}</td>
                        <td className={`py-1.5 text-right font-medium ${ev.car != null ? (ev.car >= 0 ? "text-success" : "text-danger") : ""}`}>
                          {pct(ev.car)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
