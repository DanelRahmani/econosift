"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { LeadingData, MacroTimeSeries } from "@/lib/types";
import { Card } from "@/components/ui";
import { RecessionProbability } from "@/components/macro/RecessionProbability";
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
  ScatterChart,
  Scatter,
  ZAxis,
} from "recharts";

const GRID = "rgba(255,255,255,0.08)";

function KpiCard({
  label,
  value,
  unit = "",
  color,
  sub,
}: {
  label: string;
  value: number | null;
  unit?: string;
  color?: string;
  sub?: string;
}) {
  return (
    <Card className="p-4">
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${color ?? ""}`}>
        {value != null ? `${value.toFixed(2)}${unit}` : "—"}
      </div>
      {sub && <div className="text-xs text-text-secondary mt-0.5">{sub}</div>}
    </Card>
  );
}

export function LeadingIndicators() {
  const [data, setData] = useState<LeadingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [baseYear, setBaseYear] = useState(2020);

  useEffect(() => {
    setLoading(true);
    api
      .macroLeading(baseYear)
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [baseYear]);

  if (loading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-40 animate-pulse bg-surface-alt rounded" />
        ))}
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-text-secondary text-sm py-8 text-center">
        Leading indicators data unavailable — backend endpoint not yet
        implemented.
      </div>
    );
  }

  const { kpis, history, islmpc } = data;

  const leiData = (history.lei ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    "LEI YoY %": pt.value,
  }));

  const cfnaiData = (history.cfnai ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    CFNAI: pt.value,
  }));

  const ismData = (history.ismPmi ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    "ISM PMI": pt.value,
  }));

  const gscpiData = (history.gscpi ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    GSCPI: pt.value,
  }));

  // Phillips Curve: scatter of unemployment vs CPI (last 10Y of annual data)
  const unrate = islmpc?.unrate ?? [];
  const cpi = islmpc?.cpi ?? [];
  // Build last ~10 years monthly data pairs, sample every 12 points for annual-ish
  const phillipsPath: { x: number; y: number; date: string }[] = [];
  const step = Math.max(1, Math.floor(unrate.length / 40));
  for (let i = 0; i < unrate.length; i += step) {
    const u = unrate[i];
    const c = cpi[i];
    if (u?.value != null && c?.value != null) {
      phillipsPath.push({ x: u.value, y: c.value, date: u.date.slice(0, 7) });
    }
  }
  const phillipsCurrent = phillipsPath[phillipsPath.length - 1];

  // IS Curve: Fed Funds rate (x) vs Real GDP (y)
  const fedFunds = islmpc?.fedFunds ?? [];
  const gdp = islmpc?.gdp ?? [];
  const isData: { x: number; y: number }[] = [];
  const step2 = Math.max(1, Math.floor(fedFunds.length / 40));
  for (let i = 0; i < fedFunds.length; i += step2) {
    const f = fedFunds[i];
    const g = gdp[i];
    if (f?.value != null && g?.value != null) {
      isData.push({ x: f.value, y: g.value });
    }
  }

  // LM Curve: M2 growth (x) vs Nominal GDP (y)
  const m2 = islmpc?.m2 ?? [];
  const gdpNom = islmpc?.gdp ?? [];
  const lmData: { x: number; y: number }[] = [];
  const step3 = Math.max(1, Math.floor(m2.length / 40));
  for (let i = 0; i < m2.length; i += step3) {
    const m = m2[i];
    const g = gdpNom[i];
    if (m?.value != null && g?.value != null) {
      lmData.push({ x: m.value, y: g.value });
    }
  }

  return (
    <div className="space-y-6">
      {/* Recession Probability Model */}
      <RecessionProbability />

      {/* Base Year Selector */}
      <div className="flex items-center gap-3">
        <span className="text-xs text-text-secondary">IS-LM-PC Base Year:</span>
        <select
          value={baseYear}
          onChange={(e) => setBaseYear(Number(e.target.value))}
          className="text-xs bg-surface border border-border rounded px-2 py-1 text-text-primary"
        >
          {[2024, 2023, 2022, 2021, 2020, 2019, 2015, 2010, 2005, 2000].map(y => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
        <span className="text-[10px] text-text-muted">Normalizes IS-LM-PC data to 100 at selected year</span>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          label="CB LEI (YoY %)"
          value={kpis.lei}
          sub="Conference Board Leading Economic Index"
          color={kpis.lei != null && kpis.lei < 0 ? "text-danger" : "text-success"}
        />
        <KpiCard
          label="CFNAI"
          value={kpis.cfnai}
          sub="Chicago Fed National Activity Index"
          color={
            kpis.cfnai != null && kpis.cfnai < -0.7
              ? "text-danger"
              : kpis.cfnai != null && kpis.cfnai > 0
              ? "text-success"
              : "text-text-primary"
          }
        />
        <KpiCard
          label="ISM Manufacturing PMI"
          value={kpis.ismPmi}
          sub={kpis.ismPmi != null ? (kpis.ismPmi >= 50 ? "Expanding" : "Contracting") : undefined}
          color={kpis.ismPmi != null && kpis.ismPmi < 50 ? "text-danger" : "text-success"}
        />
        <KpiCard
          label="GSCPI"
          value={kpis.gscpi}
          sub="Global Supply Chain Pressure Index"
        />
      </div>

      {/* LEI */}
      {leiData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">
            Conference Board LEI (YoY % Change)
          </h3>
          <p className="text-xs text-text-secondary mb-3">
            Leads business cycle turns by ~6 months. Sustained below 0 = recession signal.
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={leiData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.3)" />
              <Line type="monotone" dataKey="LEI YoY %" stroke="#3b82f6" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* CFNAI */}
      {cfnaiData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">CFNAI — Chicago Fed National Activity Index</h3>
          <p className="text-xs text-text-secondary mb-3">
            0 = trend growth. Below −0.70 (3-month avg) = recession signal.
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={cfnaiData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [v?.toFixed(3), "CFNAI"]} />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.35)" strokeDasharray="4 4" />
              <ReferenceLine y={-0.7} stroke="#ef4444" strokeDasharray="4 4"
                label={{ value: "−0.70", fill: "#ef4444", fontSize: 11 }} />
              <Line type="monotone" dataKey="CFNAI" stroke="#10b981" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* ISM PMI */}
      {ismData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">ISM Manufacturing PMI</h3>
          <p className="text-xs text-text-secondary mb-3">
            Above 50 = expanding. Below 50 = contracting. Leading indicator for industrial activity.
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={ismData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis domain={[30, 70]} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [v?.toFixed(1), "ISM PMI"]} />
              <ReferenceLine y={50} stroke="#f59e0b" strokeDasharray="4 4"
                label={{ value: "50 = neutral", fill: "#f59e0b", fontSize: 11 }} />
              <Line type="monotone" dataKey="ISM PMI" stroke="#8b5cf6" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* GSCPI */}
      {gscpiData.length > 0 ? (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">
            Global Supply Chain Pressure Index (GSCPI)
          </h3>
          <p className="text-xs text-text-secondary mb-3">
            Composite of freight rates, air cargo, PMI delivery times. Above 0 = above-average pressure.
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={gscpiData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [v?.toFixed(2), "GSCPI"]} />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.3)" />
              <Line type="monotone" dataKey="GSCPI" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      ) : (
        <Card className="p-4">
          <h3 className="font-semibold mb-2">
            Global Supply Chain Pressure Index (GSCPI)
          </h3>
          <p className="text-text-secondary text-sm">Data unavailable</p>
        </Card>
      )}

      {/* IS-LM-PC Panel */}
      <div>
        <h3 className="font-semibold mb-1">IS-LM-Phillips Curve Framework</h3>
        <p className="text-xs text-text-secondary mb-1">
          Normalized to base year = 100. Dots show historical over time; <span className="text-red-400 font-semibold">● current</span>.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* IS Curve */}
          <Card className="p-4">
            <h4 className="text-sm font-semibold mb-1">IS Curve</h4>
            <p className="text-xs text-text-secondary mb-3">
              Fed Funds Rate vs GDP (index, {baseYear ?? "?"} = 100)
            </p>
            {isData.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <ScatterChart>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                  <XAxis dataKey="x" name="Fed Funds" tick={{ fontSize: 10 }} label={{ value: "Fed Funds (index)", position: "insideBottom", offset: -5, fontSize: 10 }} />
                  <YAxis dataKey="y" name="GDP" tick={{ fontSize: 10 }} label={{ value: "GDP (index)", angle: -90, position: "insideLeft", fontSize: 10 }} />
                  <Tooltip cursor={{ strokeDasharray: "3 3" }} formatter={(v: number) => [v?.toFixed(1)]} />
                  <Scatter data={isData.slice(0, -1)} fill="#3b82f6" fillOpacity={0.4} name="Historical" />
                  {isData.length > 0 && (
                    <Scatter data={[isData[isData.length - 1]]} fill="#ef4444" fillOpacity={1} name="Current" />
                  )}
                </ScatterChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-text-secondary text-xs">Data unavailable</p>
            )}
          </Card>

          {/* LM Curve */}
          <Card className="p-4">
            <h4 className="text-sm font-semibold mb-1">LM Curve</h4>
            <p className="text-xs text-text-secondary mb-3">
              M2 vs GDP (index, {baseYear ?? "?"} = 100)
            </p>
            {lmData.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <ScatterChart>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                  <XAxis dataKey="x" name="M2" tick={{ fontSize: 10 }} label={{ value: "M2 (index)", position: "insideBottom", offset: -5, fontSize: 10 }} />
                  <YAxis dataKey="y" name="GDP" tick={{ fontSize: 10 }} label={{ value: "GDP (index)", angle: -90, position: "insideLeft", fontSize: 10 }} />
                  <Tooltip cursor={{ strokeDasharray: "3 3" }} formatter={(v: number) => [v?.toFixed(1)]} />
                  <Scatter data={lmData.slice(0, -1)} fill="#10b981" fillOpacity={0.4} name="Historical" />
                  {lmData.length > 0 && (
                    <Scatter data={[lmData[lmData.length - 1]]} fill="#ef4444" fillOpacity={1} name="Current" />
                  )}
                </ScatterChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-text-secondary text-xs">Data unavailable</p>
            )}
          </Card>

          {/* Phillips Curve */}
          <Card className="p-4">
            <h4 className="text-sm font-semibold mb-1">Phillips Curve</h4>
            <p className="text-xs text-text-secondary mb-3">
              Unemployment vs CPI (index, {baseYear ?? "?"} = 100)
            </p>
            {phillipsPath.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <ScatterChart>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                  <XAxis dataKey="x" name="Unemployment" tick={{ fontSize: 10 }} label={{ value: "Unemployment (index)", position: "insideBottom", offset: -5, fontSize: 10 }} />
                  <YAxis dataKey="y" name="CPI" tick={{ fontSize: 10 }} label={{ value: "CPI (index)", angle: -90, position: "insideLeft", fontSize: 10 }} />
                  <Tooltip cursor={{ strokeDasharray: "3 3" }} formatter={(v: number) => [v?.toFixed(1)]} />
                  <Scatter data={phillipsPath} fill="#8b5cf6" fillOpacity={0.4} name="Historical" />
                </ScatterChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-text-secondary text-xs">Data unavailable</p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
