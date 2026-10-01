"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ComposableMap,
  Geographies,
  Geography,
  ZoomableGroup,
} from "react-simple-maps";
import { feature } from "topojson-client";
import type { AtlasCountry } from "@/lib/types";
import { fmtNum } from "@/lib/format";
import { openSourceMenu } from "@/components/provenance/SourceMenu";
import { resolveRefs, type Provenance } from "@/lib/provenance";

interface Props {
  countries: AtlasCountry[];
  year: number;
  unit: string;
  colorFor: (v: number | null | undefined) => string;
  region: string;
  members: Set<string>; // ISO3 set for region filter
  iso3ById: Map<string, string>; // numeric id -> iso3
  prov?: Provenance; // provenance map of the timeline response
  indicatorLabel?: string;
}

// Hardcoded zoom targets per region (center [lng, lat], zoom)
const REGION_VIEW: Record<string, { center: [number, number]; zoom: number }> = {
  World: { center: [0, 20], zoom: 1 },
  G7: { center: [-10, 48], zoom: 2.2 },
  G20: { center: [20, 25], zoom: 1.4 },
  Eurozone: { center: [12, 50], zoom: 3.5 },
  EM: { center: [30, 15], zoom: 1.2 },
};

export function WorldMap({ countries, year, unit, colorFor, region, members, iso3ById, prov, indicatorLabel }: Props) {
  // Use `object` as a safe escape hatch for the parsed topojson/geojson data
  const [geojson, setGeojson] = useState<object | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    name: string;
    value: number | null;
  } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setLoadError(false);
    fetch("/world-110m.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((topo: unknown) => {
        if (cancelled) return;
        // Cast through unknown to satisfy topojson-client's strict type params
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const fc = feature(topo as any, (topo as any).objects.countries);
        setGeojson(fc as object);
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError(true);
          setGeojson(null);
        }
      });
    return () => { cancelled = true; };
  }, []);

  // Build value lookup: iso3 -> value for the current year
  const valueByIso3 = useMemo(() => {
    const m = new Map<string, number | null>();
    for (const c of countries) {
      m.set(c.iso3, c.values[String(year)] ?? null);
    }
    return m;
  }, [countries, year]);

  const view = REGION_VIEW[region] ?? REGION_VIEW.World;

  if (loadError) {
    return (
      <div className="w-full h-[500px] flex items-center justify-center text-text-muted text-sm">
        Failed to load world map data. Please refresh the page.
      </div>
    );
  }

  if (!geojson) {
    return (
      <div className="w-full h-[500px] flex items-center justify-center text-text-muted animate-pulse">
        Loading map...
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative w-full" style={{ height: 500 }}>
      <ComposableMap
        key={region}
        projection="geoMercator"
        projectionConfig={{ scale: 130 }}
        width={800}
        height={500}
        style={{ width: "100%", height: "100%" }}
      >
        <ZoomableGroup center={view.center} zoom={view.zoom} maxZoom={8}>
          <Geographies geography={geojson}>
            {({ geographies }) =>
              geographies.map((geo) => {
                // geo.id is the ISO numeric string from world-110m TopoJSON
                const numericId = String((geo as { id?: unknown }).id ?? "");
                const iso3 = iso3ById.get(numericId);
                const value = iso3 ? (valueByIso3.get(iso3) ?? null) : null;
                const inRegion = region === "World" || (iso3 ? members.has(iso3) : false);
                const fill = inRegion ? colorFor(value) : "#2a2a3a";
                const opacity = inRegion ? 1 : 0.35;
                const countryName = iso3
                  ? (countries.find((c) => c.iso3 === iso3)?.name ?? iso3)
                  : numericId;

                return (
                  <Geography
                    key={geo.rsmKey}
                    geography={geo}
                    fill={fill}
                    fillOpacity={opacity}
                    stroke="#1a1a2a"
                    strokeWidth={0.4}
                    style={{
                      default: { outline: "none" },
                      hover: {
                        outline: "none",
                        fillOpacity: inRegion ? 0.8 : 0.2,
                        cursor: "pointer",
                      },
                      pressed: { outline: "none" },
                    }}
                    onMouseEnter={(e: React.MouseEvent) => {
                      setTooltip({
                        x: e.nativeEvent.offsetX,
                        y: e.nativeEvent.offsetY,
                        name: countryName,
                        value,
                      });
                    }}
                    onMouseMove={(e: React.MouseEvent) => {
                      setTooltip((prev) =>
                        prev
                          ? { ...prev, x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY }
                          : null
                      );
                    }}
                    onMouseLeave={() => setTooltip(null)}
                    onContextMenu={(e: React.MouseEvent) => {
                      if (e.shiftKey) return;
                      // preventDefault also tells the app-wide listener this menu is handled here.
                      e.preventDefault();
                      let refs = resolveRefs(prov, `countries.${iso3 ?? numericId}`);
                      // The timeline lists World Bank and IMF refs; imfYears says which one supplied this year.
                      const imfYears = (countries.find((c) => c.iso3 === iso3) as (AtlasCountry & { imfYears?: number[] }) | undefined)?.imfYears;
                      if (refs.length > 1) {
                        const fromImf = !!imfYears?.includes(year);
                        const pick = refs.filter((r) => (r.provider === "imf") === fromImf);
                        if (pick.length) refs = pick;
                      }
                      openSourceMenu({
                        x: e.clientX,
                        y: e.clientY,
                        refs,
                        prov,
                        ctx: `${countryName} · ${year}${indicatorLabel ? ` · ${indicatorLabel}` : ""}`,
                        value: value !== null ? `${fmtNum(value)} ${unit}` : undefined,
                      });
                    }}
                  />
                );
              })
            }
          </Geographies>
        </ZoomableGroup>
      </ComposableMap>

      {/* Hover tooltip */}
      {tooltip && (
        <div
          className="pointer-events-none absolute z-20 bg-surface border border-border rounded-lg px-3 py-2 text-xs shadow-lg"
          style={{ left: tooltip.x + 12, top: tooltip.y - 8 }}
        >
          <div className="font-semibold text-text-primary">{tooltip.name}</div>
          <div className="text-text-secondary">
            {tooltip.value !== null && tooltip.value !== undefined
              ? `${fmtNum(tooltip.value)} ${unit}`
              : "No data"}
          </div>
        </div>
      )}
    </div>
  );
}
