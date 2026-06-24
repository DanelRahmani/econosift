"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui";
import { SectorReturnsChart } from "@/components/sectors/SectorReturnsChart";
import { SectorFundamentalsTable } from "@/components/sectors/SectorFundamentalsTable";
import { SectorRotationClock } from "@/components/sectors/SectorRotationClock";
import { SectorIndustryDrillDown } from "@/components/sectors/SectorIndustryDrillDown";
import type {
  SectorReturnsResponse,
  SectorFundamentalsResponse,
  SectorRotationResponse,
  SectorDrillResponse,
  SectorReturn,
} from "@/lib/types";

const PERIODS = ["1d", "1w", "1m", "3m", "ytd", "1y"] as const;
type Period = (typeof PERIODS)[number];

const PERIOD_LABELS: Record<Period, string> = {
  "1d": "1D",
  "1w": "1W",
  "1m": "1M",
  "3m": "3M",
  "ytd": "YTD",
  "1y": "1Y",
};

export default function SectorsPage() {
  const [returns, setReturns] = useState<SectorReturnsResponse | null>(null);
  const [fundamentals, setFundamentals] = useState<SectorFundamentalsResponse | null>(null);
  const [rotation, setRotation] = useState<SectorRotationResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const [activePeriod, setActivePeriod] = useState<Period>("1d");
  const [selectedSector, setSelectedSector] = useState<string | null>(null);
  const [drillData, setDrillData] = useState<SectorDrillResponse | null>(null);
  const [drillLoading, setDrillLoading] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([
      api.sectorReturns(),
      api.sectorFundamentals(),
      api.sectorRotation(),
    ])
      .then(([r, f, rot]) => {
        if (!active) return;
        setReturns(r);
        setFundamentals(f);
        setRotation(rot);
      })
      .catch(() => {/* errors surfaced as null state */})
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!selectedSector) { setDrillData(null); return; }
    let active = true;
    setDrillLoading(true);
    api.sectorDrill(selectedSector)
      .then((d) => active && setDrillData(d))
      .catch(() => active && setDrillData(null))
      .finally(() => active && setDrillLoading(false));
    return () => { active = false; };
  }, [selectedSector]);

  const kpiData: SectorReturn[] = returns?.periods["1d"] ?? [];
  const chartData: SectorReturn[] = returns?.periods[activePeriod] ?? [];

  return (
    <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <h1 className="text-2xl font-display font-bold text-text-primary">Sector Performance</h1>

      {/* KPI strip */}
      <Card>
        <h2 className="text-sm font-semibold text-text-secondary mb-3">Today&apos;s Returns</h2>
        {loading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
            {Array.from({ length: 11 }).map((_, i) => (
              <div key={i} className="animate-pulse bg-surface-alt rounded-lg h-14" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
            {[...kpiData]
              .sort((a, b) => (b.changePercent ?? 0) - (a.changePercent ?? 0))
              .map((s) => (
                <button
                  key={s.ticker}
                  onClick={() => setSelectedSector(s.sector === selectedSector ? null : s.sector)}
                  className={`rounded-lg p-2.5 border text-left transition-colors ${
                    selectedSector === s.sector
                      ? "border-accent bg-accent/10"
                      : "border-border/60 hover:border-border"
                  }`}
                >
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-xs font-mono text-text-muted">{s.ticker}</span>
                  </div>
                  <div className="text-xs text-text-secondary leading-tight mb-1">{s.sector}</div>
                  <div className={`text-sm font-mono font-semibold ${
                    (s.changePercent ?? 0) >= 0 ? "text-success" : "text-danger"
                  }`}>
                    {s.changePercent !== null
                      ? `${s.changePercent >= 0 ? "+" : ""}${s.changePercent.toFixed(2)}%`
                      : "—"}
                  </div>
                </button>
              ))}
          </div>
        )}
      </Card>

      {/* Period bar charts */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h2 className="text-sm font-semibold text-text-secondary">Sector Returns by Period</h2>
          <div className="flex gap-1">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setActivePeriod(p)}
                className={`px-2.5 py-1 rounded-md text-xs font-mono transition-colors ${
                  activePeriod === p
                    ? "bg-surface-alt text-text-primary"
                    : "text-text-muted hover:text-text-primary"
                }`}
              >
                {PERIOD_LABELS[p]}
              </button>
            ))}
          </div>
        </div>
        {loading ? (
          <div className="animate-pulse bg-surface-alt rounded-lg h-80" />
        ) : (
          <SectorReturnsChart
            data={chartData}
            onSectorClick={(s) => setSelectedSector(s === selectedSector ? null : s)}
          />
        )}
      </Card>

      {/* Fundamentals table */}
      <Card>
        <h2 className="text-sm font-semibold text-text-secondary mb-4">Sector ETF Fundamentals</h2>
        {loading || !fundamentals ? (
          <div className="animate-pulse bg-surface-alt rounded-lg h-48" />
        ) : (
          <SectorFundamentalsTable data={fundamentals} />
        )}
      </Card>

      {/* Rotation clock */}
      <Card>
        <h2 className="text-sm font-semibold text-text-secondary mb-4">Sector Rotation Clock</h2>
        <p className="text-xs text-text-muted mb-4">
          Sam Stovall 4-phase model. Bubbles sized by AUM. Click a dot to explore an industry.
        </p>
        {loading || !rotation ? (
          <div className="animate-pulse bg-surface-alt rounded-lg h-96" />
        ) : (
          <SectorRotationClock
            data={rotation}
            onSectorClick={(s) => setSelectedSector(s === selectedSector ? null : s)}
          />
        )}
      </Card>

      {/* Industry drill-down */}
      {selectedSector && (
        <Card>
          <SectorIndustryDrillDown
            sector={selectedSector}
            data={drillData}
            loading={drillLoading}
          />
        </Card>
      )}
    </main>
  );
}
