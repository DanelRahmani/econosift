"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { RecessionProbabilityData } from "@/lib/types";
import { PageSkeleton, Card, chartPalette } from "@/components/ui";
import { CHART_COLORS } from "@/lib/format";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { legendProv } from "./legendProv";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ReferenceLine,
  ReferenceArea,
} from "recharts";

function fmtNum(v: number | null | undefined, decimals = 1, suffix = ""): string {
  return v != null ? `${v.toFixed(decimals)}${suffix}` : "—";
}

function RecessionKpi({ label, value, color, prov }: { label: string; value: string; color?: string; prov?: string }) {
  return (
    <Card className="p-4" data-prov={prov} data-prov-ctx={label}>
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${color ?? ""}`}>{value}</div>
    </Card>
  );
}

export function RecessionProbability() {
  const [data, setData] = useState<RecessionProbabilityData | null>(null);
  const [loading, setLoading] = useState(true);
  const scope = useSourceScope(provOf(data));
  // Use dark as default since chartPalette dark values work reasonably in both themes
  const pal = chartPalette("dark");

  useEffect(() => {
    api
      .macroRecessionProbability()
      .then(setData)
      .catch(() => setData({}))
      .finally(() => setLoading(false));
  }, []);

  const kpis = data?.kpis;
  const recessions = data?.recessions ?? [];

  // Probability chart: driven off the spread series so the x-axis stays
  // populated even when the probit fit is degenerate (probability history empty).
  const probChart = useMemo(() => {
    const spreadPts = data?.history?.spread ?? [];
    const probMap = new Map((data?.history?.probability ?? []).map((p) => [p.date, p.value]));
    const rtMap = new Map((data?.history?.probabilityRealtime ?? []).map((p) => [p.date, p.value]));
    const smoothMap = new Map((data?.history?.smoothedProb ?? []).map((p) => [p.date.slice(0, 7), p.value]));
    return spreadPts.map((p) => ({
      date: p.date,
      probability: probMap.get(p.date) ?? null,
      realtime: rtMap.get(p.date) ?? null,
      smoothed: smoothMap.get(p.date) ?? null,
    }));
  }, [data]);

  const spreadChart = useMemo(() => {
    return (data?.history?.spread ?? []).map((p) => ({ date: p.date, spread: p.value }));
  }, [data]);

  // Extended list: last 24 months, newest first
  const tableRows = useMemo(() => {
    const spreadPts = data?.history?.spread ?? [];
    const probMap = new Map((data?.history?.probability ?? []).map((p) => [p.date, p.value]));
    const sahmMap = new Map((data?.history?.sahm ?? []).map((p) => [p.date.slice(0, 7), p.value]));
    const smoothMap = new Map((data?.history?.smoothedProb ?? []).map((p) => [p.date.slice(0, 7), p.value]));
    return spreadPts
      .map((p) => ({
        date: p.date,
        spread: p.value,
        probability: probMap.get(p.date) ?? null,
        sahm: sahmMap.get(p.date) ?? null,
        smoothed: smoothMap.get(p.date) ?? null,
      }))
      .slice(-24)
      .reverse();
  }, [data]);

  if (loading) return <PageSkeleton text="Loading recession model…" />;

  if (!data || data.error || !kpis) {
    return (
      <div className="text-text-secondary text-sm py-8 text-center">
        Recession probability data unavailable — check the FRED API key in Admin, then use “Clear cache &amp; re-warm”.
      </div>
    );
  }

  const tooltipStyle = { background: pal.tooltipBg, border: `1px solid ${pal.tooltipBorder}`, fontSize: 12, color: pal.tooltipText };

  const probColor =
    kpis.prob12m != null ? (kpis.prob12m > 30 ? "text-danger" : kpis.prob12m > 15 ? "text-warning" : "text-success") : undefined;
  const sahmTriggered = kpis.sahm != null && kpis.sahm >= 0.5;

  function RecessionAreas() {
    return (
      <>
        {recessions.map((r, i) => (
          <ReferenceArea key={i} x1={r.start} x2={r.end} fill={pal.grid} fillOpacity={0.5} strokeOpacity={0} />
        ))}
      </>
    );
  }

  return (
    <div className="space-y-6" {...scope}>
      <div>
        <h2 className="font-semibold mb-1">Recession Probability Model</h2>
        <p className="text-xs text-text-secondary mb-3">
          NY-Fed-style 12-month-ahead probit: P(recession) = Φ(α + β · 10y–3m spread), fit by maximum likelihood on
          NBER recession history.
        </p>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <RecessionKpi prov="kpis.prob12m" label="12-Mo Recession Prob" value={fmtNum(kpis.prob12m, 1, "%")} color={probColor} />
          <RecessionKpi
            prov="kpis.sahm"
            label="Sahm Rule"
            value={kpis.sahm != null ? kpis.sahm.toFixed(2) : "—"}
            color={kpis.sahm != null ? (sahmTriggered ? "text-danger" : "text-success") : undefined}
          />
          <RecessionKpi prov="kpis.spreadPct" label="10y–3m Spread" value={fmtNum(kpis.spreadPct, 2, "%")} />
          <RecessionKpi prov="kpis.monthsInverted" label="Months Inverted" value={kpis.monthsInverted != null ? `${kpis.monthsInverted}` : "—"} />
          <RecessionKpi prov="kpis.smoothedProb" label="FRED Smoothed Prob" value={fmtNum(kpis.smoothedProb, 1, "%")} />
          <RecessionKpi
            prov="kpis.prob12mRealtime"
            label="Real-time P(recession)"
            value={fmtNum(kpis.prob12mRealtime, 1, "%")}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="p-4 bg-surface border border-border rounded-lg shadow-sm" data-prov="history.probability" data-prov-ctx="12-month recession probability">
          <h3 className="font-semibold text-sm mb-1">12-Month Recession Probability</h3>
          <p className="text-xs text-text-secondary mb-2">
            The solid line fits one probit over the whole history and applies it
            back across it, so every point knows about recessions that had not
            happened yet. The dashed line refits each month on data available at
            the time — what the model would actually have printed. They diverge
            sharply before the 2001 and 2008 recessions.
          </p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={probChart}>
                <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
                <XAxis dataKey="date" fontSize={10} minTickGap={40} />
                <YAxis domain={[0, 100]} width={36} fontSize={10} tickFormatter={(v) => `${v}%`} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11 }} formatter={legendProv({ "In-sample P(recession)": "history.probability", "Real-time (walk-forward)": "history.probabilityRealtime", "FRED Smoothed Prob": "history.smoothedProb" })} />
                <RecessionAreas />
                <Line type="monotone" dataKey="probability" name="In-sample P(recession)" stroke={CHART_COLORS[0]} dot={false} connectNulls />
                <Line
                  type="monotone"
                  dataKey="realtime"
                  name="Real-time (walk-forward)"
                  stroke={CHART_COLORS[3] ?? "#f59e0b"}
                  strokeDasharray="4 3"
                  dot={false}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="smoothed"
                  name="FRED Smoothed Prob"
                  stroke={CHART_COLORS[2]}
                  dot={false}
                  strokeDasharray="4 2"
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="p-4 bg-surface border border-border rounded-lg shadow-sm" data-prov="history.spread" data-prov-ctx="10y–3m Treasury spread (monthly mean)">
          <h3 className="font-semibold text-sm mb-2">10y–3m Treasury Spread (Monthly Mean)</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={spreadChart}>
                <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
                <XAxis dataKey="date" fontSize={10} minTickGap={40} />
                <YAxis domain={["auto", "auto"]} width={40} fontSize={10} tickFormatter={(v) => `${v}%`} />
                <Tooltip contentStyle={tooltipStyle} />
                <RecessionAreas />
                <ReferenceLine y={0} stroke={pal.axis} strokeDasharray="3 3" />
                <Line type="monotone" dataKey="spread" name="10y–3m Spread" stroke={CHART_COLORS[1]} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="p-4 bg-surface border border-border rounded-lg shadow-sm overflow-x-auto">
        <h3 className="font-semibold text-sm mb-2">Monthly Detail (last 24 months)</h3>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-text-secondary border-b border-border">
              <th className="py-1.5 pr-3">Month</th>
              <th className="py-1.5 pr-3 text-right">10y–3m Spread</th>
              <th className="py-1.5 pr-3 text-right">Model P(recession)</th>
              <th className="py-1.5 pr-3 text-right">Sahm</th>
              <th className="py-1.5 text-right">FRED Smoothed Prob</th>
            </tr>
          </thead>
          <tbody>
            {tableRows.map((r) => (
              <tr key={r.date} className="border-b border-border/50" data-prov-ctx={r.date}>
                <td className="py-1.5 pr-3">{r.date}</td>
                <td data-prov="history.spread" className={`py-1.5 pr-3 text-right ${r.spread != null ? (r.spread < 0 ? "text-danger" : "") : ""}`}>
                  {fmtNum(r.spread, 2, "%")}
                </td>
                <td data-prov="history.probability" className="py-1.5 pr-3 text-right">{fmtNum(r.probability, 1, "%")}</td>
                <td data-prov="history.sahm" className={`py-1.5 pr-3 text-right ${r.sahm != null && r.sahm >= 0.5 ? "text-danger" : ""}`}>
                  {r.sahm != null ? r.sahm.toFixed(2) : "—"}
                </td>
                <td data-prov="history.smoothedProb" className="py-1.5 text-right">{fmtNum(r.smoothed, 1, "%")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
