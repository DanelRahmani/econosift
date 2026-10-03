"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useRefreshNonce } from "@/lib/refresh";
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
  const [gdp, setGdp] = useState<number | null>(null);
  const [cpi, setCpi] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [gdpProv, setGdpProv] = useState<Provenance | undefined>(undefined);
  const [cpiProv, setCpiProv] = useState<Provenance | undefined>(undefined);

  const refreshNonce = useRefreshNonce(); // re-fetch on the page's Refresh (P1-20)
  const shownFor = useRef<string | null>(null);
  useEffect(() => {
    // A new country starts blank; a Refresh keeps the current reading on
    // screen until the new one arrives.
    if (shownFor.current !== country) {
      setLoading(true);
      setGdp(null);
      setCpi(null);
      setGdpProv(undefined);
      setCpiProv(undefined);
      shownFor.current = country;
    }
    const year = new Date().getFullYear();
    Promise.all([
      api.macroData(country, "gdp_growth", year - 3, year),
      api.macroData(country, "inflation", year - 3, year),
    ])
      .then(([gdpRes, cpiRes]) => {
        const gdpPts = gdpRes.series.find((s) => s.country === country)?.data ?? [];
        const cpiPts = cpiRes.series.find((s) => s.country === country)?.data ?? [];
        setGdp(gdpPts.length ? gdpPts[gdpPts.length - 1].value : null);
        setCpi(cpiPts.length ? cpiPts[cpiPts.length - 1].value : null);
        setGdpProv(provOf(gdpRes));
        setCpiProv(provOf(cpiRes));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [country, refreshNonce]);

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
