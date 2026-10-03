"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { Country, Indicator, MacroResponse, MacroSeries } from "@/lib/types";
import { provOf, type Provenance } from "@/lib/provenance";
import { Card, Skeleton } from "@/components/ui";
import { FxWidget } from "./FxWidget";
import { YieldCurve } from "./YieldCurve";
import { RegimeClock } from "./RegimeClock";
import { RegimeDetector } from "./RegimeDetector";
import { CountryComparison } from "./CountryComparison";
import { InflationHeatmap } from "./InflationHeatmap";
import { MacroDashboard } from "./MacroDashboard";
import { CountrySelector } from "./CountrySelector";
import { IndicatorSelector } from "./IndicatorSelector";
import { MacroChart } from "./MacroChart";
import { AiSummaryPanel } from "@/components/AiSummaryPanel";
import { useRefreshNonce } from "@/lib/refresh";

const CURRENT_YEAR = new Date().getFullYear();
const FORECASTABLE = new Set([
  "gdp_growth",
  "inflation",
  "unemployment",
  "debt_gdp",
  "current_account",
  "gdp_per_capita",
]);

export function MacroOverview() {
  const [countries, setCountries] = useState<Country[]>([]);
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [selected, setSelected] = useState<string[]>(["US", "DE", "JP"]);
  const [regimeCountry, setRegimeCountry] = useState("US");
  const [indicator, setIndicator] = useState("gdp_growth");
  const [start, setStart] = useState(2000);
  const [end, setEnd] = useState(CURRENT_YEAR);
  const [data, setData] = useState<MacroResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [showForecast, setShowForecast] = useState(false);
  const [forecast, setForecast] = useState<MacroSeries[]>([]);
  const [forecastProv, setForecastProv] = useState<Provenance | undefined>(undefined);
  const [forecastLoading, setForecastLoading] = useState(false);

  useEffect(() => {
    api.countries().then((r) => setCountries(r.countries)).catch(() => {});
    api.indicators().then((r) => setIndicators(r.indicators)).catch(() => {});
  }, []);

  // Keep regime country in sync with selected countries
  useEffect(() => {
    if (!selected.includes(regimeCountry) && selected.length > 0) {
      setRegimeCountry(selected[0]);
    }
  }, [selected, regimeCountry]);

  const canForecast = FORECASTABLE.has(indicator);
  const selKey = selected.join(",");

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    if (!selected.length) { setData(null); return; }
    let active = true;
    setLoading(true);
    api.macroData(selKey, indicator, start, end)
      .then((d) => active && setData(d))
      .catch(() => active && setData(null))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [selKey, indicator, start, end, refreshNonce]);

  useEffect(() => {
    if (!showForecast || !canForecast || !selected.length) { setForecast([]); setForecastProv(undefined); return; }
    let active = true;
    setForecastLoading(true);
    api.forecast(selKey, indicator, CURRENT_YEAR + 5)
      .then((r) => { if (active) { setForecast(r.series); setForecastProv(provOf(r)); } })
      .catch(() => { if (active) { setForecast([]); setForecastProv(undefined); } })
      .finally(() => active && setForecastLoading(false));
    return () => { active = false; };
  }, [showForecast, canForecast, selKey, indicator]);

  return (
    <div className="space-y-6">
      <FxWidget />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-1">
          <CountrySelector
            countries={countries}
            selected={selected}
            onChange={setSelected}
          />
        </Card>

        <div className="lg:col-span-2 space-y-4">
          <Card>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <IndicatorSelector
                indicators={indicators}
                value={indicator}
                onChange={setIndicator}
              />
              <div>
                <label className="text-sm font-medium text-text-secondary block mb-2">
                  Start Year
                </label>
                <input
                  type="number"
                  min={2000}
                  max={end}
                  className="input w-full min-w-[80px]"
                  value={start}
                  onChange={(e) => setStart(parseInt(e.target.value) || 2000)}
                />
              </div>
              <div>
                <label className="text-sm font-medium text-text-secondary block mb-2">
                  End Year
                </label>
                <input
                  type="number"
                  min={start}
                  max={CURRENT_YEAR}
                  className="input w-full"
                  value={end}
                  onChange={(e) => setEnd(parseInt(e.target.value) || CURRENT_YEAR)}
                />
              </div>
            </div>
          </Card>

          {data && <MacroDashboard data={data} />}

          {selected.length > 0 && countries.length > 0 && (
            <Card>
              <h2 className="text-sm font-semibold mb-3 text-text-secondary">
                Macro Regime
              </h2>
              <div className="space-y-2">
                {selected.map((iso) => {
                  const c = countries.find((x) => x.iso2 === iso);
                  return c ? (
                    <RegimeDetector key={iso} country={iso} countryName={c.name} />
                  ) : null;
                })}
              </div>
            </Card>
          )}
        </div>
      </div>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h2 className="text-sm font-semibold text-text-secondary">
            {indicators.find((i) => i.id === indicator)?.label ?? indicator}
          </h2>
          {canForecast && (
            <button
              onClick={() => setShowForecast((v) => !v)}
              className={`px-3 py-1 rounded-md text-xs font-medium border transition-colors ${
                showForecast
                  ? "bg-accent/10 border-accent/40 text-accent"
                  : "border-border text-text-secondary hover:text-text-primary hover:bg-surface-alt"
              }`}
            >
              {forecastLoading ? "Loading forecast…" : "IMF Forecast"}
            </button>
          )}
        </div>
        {loading && !data ? (
          <Skeleton className="h-96" />
        ) : data ? (
          <MacroChart data={data} forecast={showForecast ? forecast : []} forecastProv={showForecast ? forecastProv : undefined} />
        ) : null}
      </Card>

      {selected.length > 0 && (
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-text-secondary">
              Regime Clock
            </h2>
            <select
              value={regimeCountry}
              onChange={(e) => setRegimeCountry(e.target.value)}
              className="input max-w-[180px] text-xs"
            >
              {countries.filter(c => selected.includes(c.iso2)).map(c => (
                <option key={c.iso2} value={c.iso2}>{c.name}</option>
              ))}
            </select>
          </div>
          <RegimeClock
            country={regimeCountry}
            countryName={
              countries.find((c) => c.iso2 === regimeCountry)?.name ?? regimeCountry
            }
          />
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <CountryComparison selected={selected} countries={countries} />
        <YieldCurve />
      </div>

      <InflationHeatmap selected={selected} countries={countries} />

      <AiSummaryPanel
        summaryType="macro"
        title="AI Macro Summary"
        options={countries.map((c) => ({ key: c.iso2, label: c.name }))}
        searchPlaceholder="Search for countries…"
        onGenerate={(model, force, sel) => api.aiMacro(sel.length ? sel : selected, model, force)}
      />
    </div>
  );
}
