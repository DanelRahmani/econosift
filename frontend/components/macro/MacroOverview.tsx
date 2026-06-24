"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { Country, Indicator, MacroResponse, MacroSeries } from "@/lib/types";
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
  const [indicator, setIndicator] = useState("gdp_growth");
  const [start, setStart] = useState(2000);
  const [end, setEnd] = useState(CURRENT_YEAR);
  const [data, setData] = useState<MacroResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [showForecast, setShowForecast] = useState(false);
  const [forecast, setForecast] = useState<MacroSeries[]>([]);
  const [forecastLoading, setForecastLoading] = useState(false);

  useEffect(() => {
    api.countries().then((r) => setCountries(r.countries)).catch(() => {});
    api.indicators().then((r) => setIndicators(r.indicators)).catch(() => {});
  }, []);

  const canForecast = FORECASTABLE.has(indicator);
  const selKey = selected.join(",");

  useEffect(() => {
    if (!selected.length) { setData(null); return; }
    let active = true;
    setLoading(true);
    api.macroData(selKey, indicator, start, end)
      .then((d) => active && setData(d))
      .catch(() => active && setData(null))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [selKey, indicator, start, end]);

  useEffect(() => {
    if (!showForecast || !canForecast || !selected.length) { setForecast([]); return; }
    let active = true;
    setForecastLoading(true);
    api.forecast(selKey, indicator, CURRENT_YEAR + 5)
      .then((r) => active && setForecast(r.series))
      .catch(() => active && setForecast([]))
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
                  className="input w-full"
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
          <MacroChart data={data} forecast={showForecast ? forecast : []} />
        ) : null}
      </Card>

      {selected.length > 0 && (
        <Card>
          <h2 className="text-sm font-semibold mb-3 text-text-secondary">
            Regime Clock ·{" "}
            {countries.find((c) => c.iso2 === selected[0])?.name ?? selected[0]}
          </h2>
          <RegimeClock
            country={selected[0]}
            countryName={
              countries.find((c) => c.iso2 === selected[0])?.name ?? selected[0]
            }
          />
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <CountryComparison selected={selected} countries={countries} />
        <YieldCurve />
      </div>

      <InflationHeatmap selected={selected} countries={countries} />
    </div>
  );
}
