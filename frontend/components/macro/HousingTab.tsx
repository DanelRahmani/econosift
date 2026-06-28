"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { HousingData, GlobalHousingData } from "@/lib/types";
import { Card } from "@/components/ui";
import { shortCountryName } from "@/lib/format";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
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

export function HousingTab() {
  const [data, setData] = useState<HousingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [globalHousing, setGlobalHousing] = useState<GlobalHousingData | null>(null);

  useEffect(() => {
    api
      .macroHousing()
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
    api.macroHousingGlobal().then(setGlobalHousing).catch(() => {});
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-40 animate-pulse bg-surface-alt rounded" />
        ))}
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-text-secondary text-sm py-8 text-center">
        Housing data unavailable — backend endpoint not yet implemented.
      </div>
    );
  }

  const { kpis, history, recessionPeriods } = data;
  const rp = recessionPeriods ?? [];

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

  const csData = (history.caseShillerYoY ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    "Case-Shiller YoY %": pt.value,
  }));

  const startsData = (history.housingStarts ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    "Housing Starts (K)": pt.value,
  }));

  const mortgageData = (history.mortgageRate ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    "30Y Mortgage Rate %": pt.value,
  }));

  const salesData = (history.existingHomeSales ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    "Existing Home Sales (M)": pt.value != null ? pt.value / 1_000_000 : null,
  }));

  return (
    <div className="space-y-6">
      {/* KPI Row */}
      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          label="Case-Shiller HPI YoY"
          value={kpis.caseShillerYoY}
          color={kpis.caseShillerYoY != null && kpis.caseShillerYoY < 0 ? "text-danger" : "text-success"}
        />
        <KpiCard
          label="Housing Starts (K)"
          value={kpis.housingStarts}
          unit="K"
        />
        <KpiCard
          label="30Y Mortgage Rate"
          value={kpis.mortgageRate}
          color={kpis.mortgageRate != null && kpis.mortgageRate > 7 ? "text-danger" : "text-text-primary"}
        />
        <KpiCard
          label="Existing Home Sales (M)"
          value={kpis.existingHomeSales != null ? kpis.existingHomeSales / 1_000_000 : null}
          unit="M"
        />
      </div>

      {/* Case-Shiller HPI */}
      {csData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">
            S&P/Case-Shiller Home Price Index (YoY %)
          </h3>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={csData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <RecessionAreas />
              <Line
                type="monotone"
                dataKey="Case-Shiller YoY %"
                stroke="#3b82f6"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
          <p className="text-xs text-text-secondary mt-2">Grey bands = NBER recessions</p>
        </Card>
      )}

      {/* Housing Starts */}
      {startsData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">Housing Starts (thousands, SAAR)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={startsData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(0)}K`]} />
              <RecessionAreas />
              <Line
                type="monotone"
                dataKey="Housing Starts (K)"
                stroke="#10b981"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* 30Y Mortgage Rate */}
      {mortgageData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">30-Year Mortgage Rate (%)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={mortgageData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <Line
                type="monotone"
                dataKey="30Y Mortgage Rate %"
                stroke="#f59e0b"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Existing Home Sales */}
      {salesData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">
            Existing Home Sales (millions, SAAR)
          </h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={salesData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}M`} domain={[3, 5]} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}M`]} />
              <RecessionAreas />
              <Line
                type="monotone"
                dataKey="Existing Home Sales (M)"
                stroke="#8b5cf6"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Global Property Prices (BIS) */}
      {globalHousing && globalHousing.countries.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">
            🌍 Global Real House Price Index (2010=100)
          </h3>
          <p className="text-xs text-text-secondary mb-3">
            BIS residential property prices, inflation-adjusted. YoY% change shown.
          </p>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart
              data={globalHousing.countries.map((c) => ({
                name: c.name,
                yoy: c.yoyChange ?? 0,
              }))}
              layout="vertical"
              margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={90} tickFormatter={shortCountryName} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`, "YoY Change"]} />
              <Bar dataKey="yoy" radius={[0, 4, 4, 0]}>
                {(globalHousing.countries.map((c) => (
                  <Cell
                    key={c.iso2}
                    fill={(c.yoyChange ?? 0) >= 0 ? "#10b981" : "#ef4444"}
                    fillOpacity={0.8}
                  />
                )) as any)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
            {globalHousing.countries.slice(0, 8).map((c) => (
              <div key={c.iso2} className="text-xs">
                <span className="text-text-secondary">{c.name}</span>{" "}
                <span className={(c.yoyChange ?? 0) >= 0 ? "text-success font-medium" : "text-danger font-medium"}>
                  {c.yoyChange != null ? `${c.yoyChange > 0 ? "+" : ""}${c.yoyChange.toFixed(1)}%` : "—"}
                </span>
              </div>
            ))}
          </div>
          <p className="text-xs text-text-secondary mt-2">
            Source: {globalHousing.source}. {globalHousing.note}
          </p>
        </Card>
      )}
    </div>
  );
}
