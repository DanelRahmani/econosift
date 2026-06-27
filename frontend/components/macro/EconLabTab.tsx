"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Country, RegressResponse } from "@/lib/types";
import { Card } from "@/components/ui";
import { CountrySelector } from "./CountrySelector";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { TaylorRuleWidget } from "./TaylorRuleWidget";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const GRID = "rgba(255,255,255,0.08)";

const LAB_INDICATORS: { id: string; label: string }[] = [
  { id: "gdp_growth",    label: "GDP Growth (%)" },
  { id: "inflation",     label: "Inflation, CPI (%)" },
  { id: "unemployment",  label: "Unemployment Rate (%)" },
  { id: "debt_gdp",      label: "Government Debt (% GDP)" },
  { id: "current_account", label: "Current Account (% GDP)" },
  { id: "gdp_per_capita", label: "GDP per Capita (US$)" },
];

const DEFAULT_COUNTRIES = ["US", "DE", "JP", "GB", "FR", "CN", "IN", "BR"];

const CURRENT_YEAR = new Date().getFullYear();

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function KpiCard({
  label,
  value,
  unit = "",
}: {
  label: string;
  value: number | null | undefined;
  unit?: string;
}) {
  return (
    <Card className="p-4">
      <div className="text-xs text-text-secondary">{label}</div>
      <div className="text-xl font-bold mt-1 text-text-primary">
        {value != null ? `${value.toFixed(4)}${unit}` : "—"}
      </div>
    </Card>
  );
}

function StarsSpan({ stars }: { stars: string }) {
  if (!stars) return null;
  return <span className="text-accent font-bold ml-1">{stars}</span>;
}

function fmt(v: number | null | undefined, dp = 4): string {
  if (v == null) return "—";
  return v.toFixed(dp);
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function EconLabTab() {
  const [dep, setDep]               = useState("gdp_growth");
  const [indep, setIndep]           = useState<string[]>(["inflation"]);
  const [countries, setCountries]   = useState<string[]>(DEFAULT_COUNTRIES);
  const [start, setStart]           = useState(2000);
  const [end, setEnd]               = useState(CURRENT_YEAR);
  const [result, setResult]         = useState<RegressResponse | null>(null);
  const [loading, setLoading]       = useState(false);

  const [allCountries, setAllCountries] = useState<Country[]>([]);

  useEffect(() => {
    api.countries().then((r) => setAllCountries(r.countries)).catch(() => {});
  }, []);
  // Available indep = all indicators except the chosen dep
  const availableIndep = LAB_INDICATORS.filter((ind) => ind.id !== dep);

  function toggleIndep(id: string) {
    setIndep((prev) =>
      prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id]
    );
  }

  function toggleCountry(iso2: string) {
    setCountries((prev) =>
      prev.includes(iso2) ? prev.filter((c) => c !== iso2) : [...prev, iso2]
    );
  }

  async function runRegression() {
    const cleanIndep = indep.filter((v) => v !== dep);
    if (!cleanIndep.length || !countries.length) return;
    setLoading(true);
    setResult(null);
    try {
      const r = await api.macroRegress(dep, cleanIndep, countries, start, end);
      setResult(r);
    } finally {
      setLoading(false);
    }
  }

  const depLabel = LAB_INDICATORS.find((i) => i.id === dep)?.label ?? dep;

  // Scatter data: {x: fitted, y: residual}
  const scatterData = result?.residuals
    ?.filter((r) => r.fitted != null && r.residual != null)
    .map((r) => ({ x: r.fitted as number, y: r.residual as number })) ?? [];

  return (
    <div className="space-y-6">
      <TaylorRuleWidget />

      {/* Controls */}
      <Card className="p-5 space-y-5">
        <h2 className="text-base font-semibold text-text-primary">Econometric Lab — Pooled OLS</h2>

        {/* Dependent variable */}
        <div>
          <label className="text-xs text-text-secondary block mb-1">Dependent Variable (Y)</label>
          <select
            className="input w-full max-w-xs"
            value={dep}
            onChange={(e) => {
              setDep(e.target.value);
              setIndep((prev) => prev.filter((v) => v !== e.target.value));
            }}
          >
            {LAB_INDICATORS.map((ind) => (
              <option key={ind.id} value={ind.id}>{ind.label}</option>
            ))}
          </select>
        </div>

        {/* Independent variables */}
        <div>
          <label className="text-xs text-text-secondary block mb-2">
            Independent Variables (X) — select 1–5
          </label>
          <div className="flex flex-wrap gap-2">
            {availableIndep.map((ind) => {
              const on = indep.includes(ind.id);
              const disabled = !on && indep.filter((v) => v !== dep).length >= 5;
              return (
                <button
                  key={ind.id}
                  onClick={() => toggleIndep(ind.id)}
                  disabled={disabled}
                  className={`px-3 py-1 rounded-lg text-xs transition-colors ${
                    on
                      ? "bg-accent text-white"
                      : disabled
                      ? "bg-surface-alt text-text-muted opacity-50 cursor-not-allowed"
                      : "bg-surface-alt text-text-secondary hover:text-text-primary"
                  }`}
                >
                  {ind.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Countries */}
        <CountrySelector
          countries={allCountries}
          selected={countries}
          onChange={setCountries}
          max={20}
        />

        {/* Year range */}
        <div className="flex gap-4 items-end">
          <div>
            <label className="text-xs text-text-secondary block mb-1">Start Year</label>
            <input
              type="number"
              className="input w-28"
              value={start}
              min={1990}
              max={end}
              onChange={(e) => setStart(Number(e.target.value))}
            />
          </div>
          <div>
            <label className="text-xs text-text-secondary block mb-1">End Year</label>
            <input
              type="number"
              className="input w-28"
              value={end}
              min={start}
              max={CURRENT_YEAR}
              onChange={(e) => setEnd(Number(e.target.value))}
            />
          </div>
        </div>

        {/* Run button */}
        <button
          onClick={runRegression}
          disabled={loading || !indep.filter((v) => v !== dep).length || !countries.length}
          className="btn-danger flex items-center gap-2 px-5 py-2 text-sm font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <span className="animate-spin inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
          ) : (
            "🔴"
          )}
          Run Regression
        </button>
      </Card>

      {/* Error / warning banners */}
      {result?.error && (
        <div className="rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm p-4">
          {result.error}
        </div>
      )}
      {result?.warning && !result.error && (
        <div className="rounded-lg bg-warning/10 border border-warning/30 text-warning text-sm p-4">
          Warning: {result.warning}
        </div>
      )}

      {/* Results */}
      {result && !result.error && (
        <>
          {/* KPI strip */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <KpiCard label="R²" value={result.rSquared} />
            <KpiCard label="Adj R²" value={result.adjRSquared} />
            <KpiCard label="AIC" value={result.aic} />
            <KpiCard label="BIC" value={result.bic} />
          </div>

          {/* Summary */}
          <Card className="p-4 text-xs text-text-secondary">
            <span className="font-medium text-text-primary">Model:</span>{" "}
            {depLabel} ~ {result.indep.map((v) => LAB_INDICATORS.find((i) => i.id === v)?.label ?? v).join(" + ")}
            {" "}·{" "}
            <span className="font-medium text-text-primary">N = {result.nObs}</span>
            {" "}·{" "}
            Countries: {result.countries.join(", ")}
            {" "}·{" "}
            {result.start}–{result.end}
            {result.asOf && <span className="ml-2 text-text-muted">(as of {result.asOf})</span>}
          </Card>

          {/* Coefficient table */}
          <Card className="p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3">Regression Coefficients</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-text-secondary border-b border-border">
                    <th className="text-left py-2 pr-4">Variable</th>
                    <th className="text-right py-2 pr-4">Coef</th>
                    <th className="text-right py-2 pr-4">Std Err</th>
                    <th className="text-right py-2 pr-4">t-stat</th>
                    <th className="text-right py-2">p-value</th>
                  </tr>
                </thead>
                <tbody>
                  {result.coefficients.map((c) => (
                    <tr key={c.name} className="border-b border-border/40 hover:bg-surface-alt/30">
                      <td className="py-2 pr-4 font-medium text-text-primary">
                        {c.name}
                        <StarsSpan stars={c.stars} />
                      </td>
                      <td className="text-right py-2 pr-4 font-mono">{fmt(c.coef)}</td>
                      <td className="text-right py-2 pr-4 font-mono text-text-secondary">{fmt(c.stdErr)}</td>
                      <td className="text-right py-2 pr-4 font-mono">{fmt(c.tStat)}</td>
                      <td className="text-right py-2 font-mono text-text-secondary">{fmt(c.pValue)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="text-xs text-text-muted mt-2">
              Significance: *** p&lt;0.01 · ** p&lt;0.05 · * p&lt;0.10
            </div>
          </Card>

          {/* Residual scatter */}
          {scatterData.length > 0 && (
            <Card className="p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-4">
                Residuals vs Fitted
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <ScatterChart>
                  <CartesianGrid stroke={GRID} />
                  <XAxis
                    dataKey="x"
                    name="Fitted"
                    tick={{ fill: "var(--color-text-secondary)", fontSize: 11 }}
                    label={{ value: "Fitted", position: "insideBottom", offset: -5, fill: "var(--color-text-secondary)", fontSize: 11 }}
                  />
                  <YAxis
                    dataKey="y"
                    name="Residual"
                    tick={{ fill: "var(--color-text-secondary)", fontSize: 11 }}
                    label={{ value: "Residual", angle: -90, position: "insideLeft", fill: "var(--color-text-secondary)", fontSize: 11 }}
                  />
                  <Tooltip
                    cursor={{ strokeDasharray: "3 3" }}
                    contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", fontSize: 12 }}
                    formatter={(value: number) => value.toFixed(4)}
                  />
                  <ReferenceLine y={0} stroke="var(--color-accent)" strokeDasharray="4 4" />
                  <Scatter
                    data={scatterData}
                    fill="var(--color-accent)"
                    fillOpacity={0.6}
                    r={3}
                  />
                </ScatterChart>
              </ResponsiveContainer>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
