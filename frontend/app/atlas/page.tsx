"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Card, Skeleton } from "@/components/ui";
import { WorldMap } from "@/components/atlas/WorldMap";
import { IndicatorSelector } from "@/components/atlas/IndicatorSelector";
import { RegionFilter } from "@/components/atlas/RegionFilter";
import { YearSlider } from "@/components/atlas/YearSlider";
import { ColorLegend } from "@/components/atlas/ColorLegend";
import { AtlasKPIs } from "@/components/atlas/AtlasKPIs";
import { RankingTable } from "@/components/atlas/RankingTable";
import type { AtlasIndicator, AtlasRegion, AtlasTimelineResponse } from "@/lib/types";

const DEFAULT_INDICATOR = "gdp_growth";
const DEFAULT_YEAR = 2024;
const YEAR_MIN = 2000;
const YEAR_MAX = 2024;

export default function AtlasPage() {
  const [indicators, setIndicators] = useState<AtlasIndicator[]>([]);
  const [regions, setRegions] = useState<AtlasRegion[]>([]);
  const [timeline, setTimeline] = useState<AtlasTimelineResponse | null>(null);
  const [loadingMeta, setLoadingMeta] = useState(true);
  const [loadingTimeline, setLoadingTimeline] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [indicator, setIndicator] = useState(DEFAULT_INDICATOR);
  const [year, setYear] = useState(DEFAULT_YEAR);
  const [region, setRegion] = useState("World");
  const [playing, setPlaying] = useState(false);

  // Fetch indicators + regions once on mount
  useEffect(() => {
    let alive = true;
    Promise.all([api.atlasIndicators(), api.atlasRegions()])
      .then(([ind, reg]) => {
        if (!alive) return;
        setIndicators(ind.indicators);
        setRegions(reg.regions);
      })
      .catch(() => alive && setError("Failed to load atlas metadata"))
      .finally(() => alive && setLoadingMeta(false));
    return () => { alive = false; };
  }, []);

  // Fetch timeline whenever indicator changes
  useEffect(() => {
    let alive = true;
    setLoadingTimeline(true);
    setError(null);
    api.atlasTimeline(indicator, YEAR_MIN, YEAR_MAX)
      .then((data) => alive && setTimeline(data))
      .catch(() => alive && setError(`Failed to load data for ${indicator}`))
      .finally(() => alive && setLoadingTimeline(false));
    return () => { alive = false; };
  }, [indicator]);

  // Memoised region -> member ISO3 set
  const members = useMemo<Set<string>>(() => {
    if (region === "World") return new Set();
    const r = regions.find((r) => r.id === region);
    return new Set(r?.members ?? []);
  }, [region, regions]);

  // Build iso3 -> numeric id lookup from timeline countries
  const iso3ById = useMemo<Map<string, string>>(() => {
    const m = new Map<string, string>();
    for (const c of timeline?.countries ?? []) {
      if (c.id) m.set(c.id, c.iso3);
    }
    return m;
  }, [timeline]);

  // Compute min/max for the current year across region
  const { minVal, maxVal } = useMemo(() => {
    if (!timeline) return { minVal: 0, maxVal: 1 };
    const yearStr = String(year);
    const vals: number[] = [];
    for (const c of timeline.countries) {
      const inRegion = region === "World" || members.has(c.iso3);
      const v = c.values[yearStr];
      if (inRegion && v !== null && v !== undefined) vals.push(v);
    }
    if (!vals.length) return { minVal: 0, maxVal: 1 };
    return { minVal: Math.min(...vals), maxVal: Math.max(...vals) };
  }, [timeline, year, region, members]);

  const activeIndicator = indicators.find((i) => i.id === indicator);

  const handleYear = useCallback((v: number) => {
    setYear(v);
  }, []);

  const isLoading = loadingMeta || loadingTimeline;

  return (
    <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-text-primary">Global Macro Atlas</h1>
          <p className="text-sm text-text-secondary mt-1">
            Choropleth world map of macro indicators across 200+ countries, 2000–2024.
          </p>
        </div>
        <RegionFilter regions={regions} active={region} onSelect={setRegion} />
      </div>

      {/* Indicator selector */}
      <Card>
        <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Indicator</h2>
        {loadingMeta ? (
          <div className="flex gap-2 flex-wrap">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-28 rounded-full" />
            ))}
          </div>
        ) : (
          <IndicatorSelector
            indicators={indicators}
            active={indicator}
            onSelect={(id) => { setIndicator(id); setPlaying(false); }}
          />
        )}
      </Card>

      {/* Error banner */}
      {error && (
        <div className="rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      {/* KPI strip */}
      {isLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
      ) : timeline ? (
        <AtlasKPIs
          countries={timeline.countries}
          year={year}
          unit={timeline.unit}
          region={region}
          members={members}
        />
      ) : null}

      {/* Map */}
      <Card className="p-0 overflow-hidden">
        {isLoading || !timeline ? (
          <Skeleton className="h-[500px] rounded-xl" />
        ) : (
          <div className="p-2">
            <WorldMap
              countries={timeline.countries}
              year={year}
              unit={timeline.unit}
              goodDirection={timeline.goodDirection}
              region={region}
              members={members}
              iso3ById={iso3ById}
            />
          </div>
        )}
      </Card>

      {/* Color legend */}
      {timeline && !isLoading && (
        <Card>
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">
            Color Scale — {activeIndicator?.label ?? indicator}
          </h2>
          <ColorLegend
            min={minVal}
            max={maxVal}
            unit={timeline.unit}
            goodDirection={timeline.goodDirection}
          />
        </Card>
      )}

      {/* Year slider */}
      <Card>
        <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Year</h2>
        <YearSlider
          year={year}
          min={YEAR_MIN}
          max={YEAR_MAX}
          playing={playing}
          onYear={handleYear}
          onPlayingChange={setPlaying}
        />
      </Card>

      {/* Ranking table */}
      <Card>
        {isLoading || !timeline ? (
          <Skeleton className="h-64" />
        ) : (
          <RankingTable
            countries={timeline.countries}
            year={year}
            unit={timeline.unit}
            indicatorLabel={activeIndicator?.label ?? indicator}
            region={region}
            members={members}
          />
        )}
      </Card>
    </main>
  );
}
