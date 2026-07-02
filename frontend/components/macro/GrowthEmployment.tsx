"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { EmploymentData } from "@/lib/types";
import { Card } from "@/components/ui";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
  BarChart,
  Bar,
  Cell,
} from "recharts";

const GRID = "rgba(255,255,255,0.08)";
const RECESSION_FILL = "rgba(120,120,120,0.18)";

function KpiCard({
  label,
  value,
  unit = "%",
  color,
}: {
  label: string;
  value: number | null;
  unit?: string;
  color?: string;
}) {
  return (
    <Card className="p-4">
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${color ?? ""}`}>
        {value != null ? `${value.toFixed(2)}${unit}` : "—"}
      </div>
    </Card>
  );
}

function fmt(v: number | null, decimals = 1) {
  return v != null ? v.toFixed(decimals) : "—";
}

export function GrowthEmployment() {
  const [data, setData] = useState<EmploymentData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [nfpRange, setNfpRange] = useState<"5Y" | "All">("5Y");

  useEffect(() => {
    api
      .macroEmployment()
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-40 animate-pulse bg-surface-alt rounded" />
        ))}
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-text-secondary text-sm py-8 text-center">
        Employment data unavailable — check the FRED API key in Admin, then use “Clear cache &amp; re-warm”.
      </div>
    );
  }

  const { kpis, history, recessionPeriods } = data;
  const rp = recessionPeriods ?? [];

  // Helper: recession reference areas for a chart
  function RecessionAreas() {
    return (
      <>
        {rp.map((r, i) => (
          <ReferenceArea
            key={i}
            x1={r.start.slice(0, 7)}
            x2={r.end.slice(0, 7)}
            fill={RECESSION_FILL}
            strokeOpacity={0}
          />
        ))}
      </>
    );
  }

  const gdpData = (history.gdpYoY ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    "GDP YoY": pt.value,
  }));

  const unrateData = (history.unemploymentRate ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    "Unemployment %": pt.value,
  }));

  const sahmData = (history.sahmRule ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    "Sahm Index": pt.value,
  }));

  const nfpData = (history.nfp ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    NFP: pt.value,
  }));

  const joltsData = (history.joltsOpenings ?? []).map((pt, i) => ({
    date: pt.date.slice(0, 7),
    "Job Openings (M)": pt.value != null ? pt.value / 1000 : null,
    "Quit Rate %": history.joltsQuits?.[i]?.value ?? null,
  }));

  const ipData = (history.indProd ?? []).map((pt, i) => ({
    date: pt.date.slice(0, 7),
    "Industrial Production (YoY %)": pt.value,
    "Capacity Utilization %": history.capUtil?.[i]?.value ?? null,
  }));

  return (
    <div className="space-y-6">
      {/* KPI Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <KpiCard
          label="Real GDP YoY"
          value={kpis.gdpYoY}
          color={kpis.gdpYoY != null && kpis.gdpYoY < 0 ? "text-danger" : "text-success"}
        />
        <KpiCard
          label="Unemployment Rate"
          value={kpis.unemploymentRate}
          color={kpis.unemploymentRate != null && kpis.unemploymentRate > 6 ? "text-danger" : "text-text-primary"}
        />
        <KpiCard
          label="NFP (thousands)"
          value={kpis.nfpLatest}
          unit="K"
          color={kpis.nfpLatest != null && kpis.nfpLatest < 0 ? "text-danger" : "text-success"}
        />
        <KpiCard
          label="Initial Claims"
          value={kpis.joblessClaims != null ? kpis.joblessClaims / 1_000 : null}
          unit="K"
        />
        <KpiCard label="Labor Participation" value={kpis.laborParticipation} />
      </div>

      {/* GDP YoY + recession shading */}
      {gdpData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">Real GDP Growth (YoY %)</h3>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={gdpData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.3)" />
              <RecessionAreas />
              <Line type="monotone" dataKey="GDP YoY" stroke="#3b82f6" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
          <p className="text-xs text-text-secondary mt-2">Grey bands = NBER recessions</p>
        </Card>
      )}

      {/* Unemployment Rate + recession shading */}
      {unrateData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">Unemployment Rate (%)</h3>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={unrateData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <RecessionAreas />
              <Line type="monotone" dataKey="Unemployment %" stroke="#ef4444" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Sahm Rule */}
      {sahmData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">Sahm Rule Recession Indicator</h3>
          <p className="text-xs text-text-secondary mb-3">
            Reading ≥ 0.50 signals early-stage recession (red zone)
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={sahmData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [v?.toFixed(3), "Sahm Index"]} />
              <ReferenceLine y={0.5} stroke="#ef4444" strokeDasharray="4 4"
                label={{ value: "0.50 threshold", fill: "#ef4444", fontSize: 11 }} />
              <RecessionAreas />
              <Line type="monotone" dataKey="Sahm Index" stroke="#f59e0b" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* NFP bar chart */}
      {nfpData.length > 0 && (() => {
        const cutoff = nfpRange === "5Y" ? new Date(new Date().setFullYear(new Date().getFullYear() - 5)).toISOString().slice(0, 7) : null;
        const filtered = cutoff ? nfpData.filter((d: any) => d.date >= cutoff) : nfpData;
        return (
        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold">Non-Farm Payrolls (Monthly Change, thousands)</h3>
            <div className="flex gap-1">
              <button onClick={() => setNfpRange("5Y")}
                className={`px-2 py-1 text-xs rounded border transition-colors ${nfpRange === "5Y" ? "border-accent bg-accent/10 text-accent" : "border-border text-text-muted hover:text-text-primary"}`}>5Y</button>
              <button onClick={() => setNfpRange("All")}
                className={`px-2 py-1 text-xs rounded border transition-colors ${nfpRange === "All" ? "border-accent bg-accent/10 text-accent" : "border-border text-text-muted hover:text-text-primary"}`}>All</button>
            </div>
          </div>
          <p className="text-xs text-text-secondary mb-2">{nfpRange === "5Y" ? "Last 5 years — pandemic extremes excluded." : "Full history including pandemic."}</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={filtered}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} domain={["auto", "auto"]} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(0)}K`, "NFP"]} />
              <Bar dataKey="NFP" radius={[2, 2, 0, 0]}>
                {filtered.map((entry: any, i: number) => (
                  <Cell key={i} fill={entry.NFP != null && entry.NFP >= 0 ? "#10b981" : "#ef4444"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
        );
      })()}

      {/* JOLTS */}
      {joltsData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">JOLTS: Job Openings & Quit Rate</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={joltsData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis yAxisId="left" tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}M`} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}%`} />
              <Tooltip />
              <Legend />
              <Line yAxisId="left" type="monotone" dataKey="Job Openings (M)" stroke="#3b82f6" dot={false} strokeWidth={1.5} />
              <Line yAxisId="right" type="monotone" dataKey="Quit Rate %" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Industrial Production + Capacity Utilization */}
      {ipData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">
            Industrial Production (YoY %) & Capacity Utilization
          </h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={ipData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis yAxisId="left" tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}%`} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}%`} />
              <Tooltip />
              <Legend />
              <ReferenceLine yAxisId="left" y={0} stroke="rgba(255,255,255,0.2)" />
              <Line yAxisId="left" type="monotone" dataKey="Industrial Production (YoY %)" stroke="#10b981" dot={false} strokeWidth={1.5} />
              <Line yAxisId="right" type="monotone" dataKey="Capacity Utilization %" stroke="#8b5cf6" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
}
