"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiQuery } from "@/lib/queries";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf, resolveRefs, type Provenance, type SourceRef } from "@/lib/provenance";

interface RegimeInfo {
  label: string;
  classes: string;
  description: string;
}

function classify(gdp: number | null, cpi: number | null): RegimeInfo {
  if (gdp === null || cpi === null) {
    return {
      label: "No Data",
      classes: "bg-text-muted/20 text-text-muted",
      description: "Insufficient data to classify regime.",
    };
  }
  if (gdp > 2 && cpi < 4) return {
    label: "Expansion",
    classes: "bg-success/20 text-success",
    description: `GDP ${gdp.toFixed(1)}% · CPI ${cpi.toFixed(1)}%`,
  };
  if (gdp > 2 && cpi >= 4) return {
    label: "Overheating",
    classes: "bg-warning/20 text-warning",
    description: `GDP ${gdp.toFixed(1)}% · CPI ${cpi.toFixed(1)}%`,
  };
  if (gdp >= 0) return {
    label: "Slowdown",
    classes: "bg-yellow-500/20 text-yellow-400",
    description: `GDP ${gdp.toFixed(1)}% · CPI ${cpi.toFixed(1)}%`,
  };
  if (cpi >= 4) return {
    label: "Stagflation",
    classes: "bg-danger/30 text-danger",
    description: `GDP ${gdp.toFixed(1)}% · CPI ${cpi.toFixed(1)}%`,
  };
  return {
    label: "Recession",
    classes: "bg-danger/20 text-danger",
    description: `GDP ${gdp.toFixed(1)}% · CPI ${cpi.toFixed(1)}%`,
  };
}

interface Props {
  country: string;
  countryName: string;
}

export function RegimeDetector({ country, countryName }: Props) {
  // A new country starts blank; a Refresh keeps the current reading on screen until the new one arrives.
  const year = new Date().getFullYear();
  const gdpQ = useQuery(apiQuery("macroData", country, "gdp_growth", year - 3, year));
  const cpiQ = useQuery(apiQuery("macroData", country, "inflation", year - 3, year));
  const loading = gdpQ.isLoading || cpiQ.isLoading;
  const lastOf = (res: typeof gdpQ.data) => {
    const pts = res?.series.find((s) => s.country === country)?.data ?? [];
    return pts.length ? pts[pts.length - 1].value : null;
  };
  const gdp = lastOf(gdpQ.data);
  const cpi = lastOf(cpiQ.data);
  const gdpProv = gdpQ.data ? provOf(gdpQ.data) : undefined;
  const cpiProv = cpiQ.data ? provOf(cpiQ.data) : undefined;

  const regime = classify(gdp, cpi);

  // The regime label is derived from both series, so its source is both refs.
  const prov = useMemo<Provenance | undefined>(() => {
    const label = (prefix: string) => (r: SourceRef) => ({
      ...r, title: `${prefix}: ${r.title ?? r.providerName ?? r.provider}`,
    });
    const refs = [
      ...resolveRefs(gdpProv, `series.${country}`).map(label("GDP growth")),
      ...resolveRefs(cpiProv, `series.${country}`).map(label("CPI inflation")),
    ];
    return refs.length ? { "*": refs } : undefined;
  }, [gdpProv, cpiProv, country]);
  const scope = useSourceScope(prov);

  return (
    <div className="flex items-center gap-2 flex-wrap" data-prov-ctx={`${countryName} regime`} {...scope}>
      <span className="text-xs text-text-muted">{countryName}:</span>
      {loading ? (
        <span className="text-xs px-2 py-0.5 rounded-md bg-surface-alt text-text-muted animate-pulse">
          Detecting…
        </span>
      ) : (
        <span
          className={`text-xs px-2.5 py-0.5 rounded-md font-semibold ${regime.classes}`}
          title={regime.description}
        >
          {regime.label}
        </span>
      )}
      {!loading && gdp !== null && cpi !== null && (
        <span className="text-xs text-text-muted">{regime.description}</span>
      )}
    </div>
  );
}
