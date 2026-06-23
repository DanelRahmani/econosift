"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Country, Indicator, MacroResponse } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";
import { CountrySelector } from "@/components/macro/CountrySelector";
import { IndicatorSelector } from "@/components/macro/IndicatorSelector";
import { MacroChart } from "@/components/macro/MacroChart";
import { MacroDashboard } from "@/components/macro/MacroDashboard";
import { FxWidget } from "@/components/macro/FxWidget";

const CURRENT_YEAR = new Date().getFullYear();

export default function MacroPage() {
  const [countries, setCountries] = useState<Country[]>([]);
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [selected, setSelected] = useState<string[]>(["US", "DE", "JP"]);
  const [indicator, setIndicator] = useState("gdp_growth");
  const [start, setStart] = useState(2000);
  const [end, setEnd] = useState(CURRENT_YEAR);

  const [data, setData] = useState<MacroResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.countries().then((r) => setCountries(r.countries)).catch(() => {});
    api.indicators().then((r) => setIndicators(r.indicators)).catch(() => {});
  }, []);

  const selKey = selected.join(",");
  useEffect(() => {
    if (!selected.length) {
      setData(null);
      return;
    }
    let active = true;
    setLoading(true);
    api.macroData(selKey, indicator, start, end)
      .then((d) => active && setData(d))
      .catch(() => active && setData(null))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [selKey, indicator, start, end]);

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
                <label className="text-sm font-medium text-text-secondary block mb-2">Start Year</label>
                <input
                  type="number" min={2000} max={end}
                  className="input w-full"
                  value={start}
                  onChange={(e) => setStart(parseInt(e.target.value) || 2000)}
                />
              </div>
              <div>
                <label className="text-sm font-medium text-text-secondary block mb-2">End Year</label>
                <input
                  type="number" min={start} max={CURRENT_YEAR}
                  className="input w-full"
                  value={end}
                  onChange={(e) => setEnd(parseInt(e.target.value) || CURRENT_YEAR)}
                />
              </div>
            </div>
          </Card>

          {data && <MacroDashboard data={data} />}
        </div>
      </div>

      <Card>
        <h2 className="text-sm font-semibold mb-4 text-text-secondary">
          {indicators.find((i) => i.id === indicator)?.label ?? indicator}
        </h2>
        {loading && !data ? <Skeleton className="h-96" /> : data && <MacroChart data={data} />}
      </Card>
    </div>
  );
}
