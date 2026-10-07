"use client";

import { useEffect, useState, useMemo } from "react";
import { LineChart, Line, ResponsiveContainer } from "recharts";
import { api } from "@/lib/api";
import type { FxRatesResponse, FxPair } from "@/lib/types";
import { Card, Skeleton, chartPalette } from "@/components/ui";
import { useTheme } from "@/components/ThemeProvider";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { fmtNum, fmtPct } from "@/lib/format";
import { useRefreshNonce } from "@/lib/refresh";

const BASES = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD"] as const;

// KPI headline pairs to show in the strip (quote currencies to highlight)
const KPI_QUOTES = ["EUR", "GBP", "JPY", "CHF", "CNY"];

function changeColor(v: number | null): string {
  if (v === null) return "text-text-secondary";
  return v >= 0 ? "text-success" : "text-danger";
}

function ChangeCell({ value }: { value: number | null }) {
  return (
    <span className={`font-mono ${changeColor(value)}`}>
      {value === null ? "—" : fmtPct(value)}
    </span>
  );
}

function SparklineCell({ values, positive }: { values: number[]; positive: boolean }) {
  const { theme } = useTheme();
  const pal = chartPalette(theme);
  const color = positive ? "#16a34a" : "#c4394a";

  if (!values || values.length < 2) {
    return <span className="text-text-muted text-xs">—</span>;
  }

  const data = values.map((v, i) => ({ i, v }));

  return (
    <div className="w-[120px] h-[32px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Line
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function KpiTile({ pair }: { pair: FxPair }) {
  const isPositive = pair.change1d !== null && pair.change1d >= 0;
  return (
    <div className="flex flex-col gap-1 px-4 py-3 rounded-lg bg-surface-alt border border-border min-w-[120px]" data-prov={`pairs.${pair.quote}`} data-prov-ctx={pair.pair}>
      <span className="text-xs text-text-muted font-medium">{pair.pair}</span>
      <span className="text-base font-semibold text-text-primary font-mono">
        {pair.rate === null ? "—" : fmtNum(pair.rate, 4)}
      </span>
      <span className={`text-xs font-mono ${changeColor(pair.change1d)}`} data-prov={`pairs.${pair.quote}.change1d`}>
        {pair.change1d === null ? "—" : (isPositive ? "+" : "") + fmtPct(pair.change1d)} 1D
      </span>
    </div>
  );
}

export function FxRatesPanel() {
  const [base, setBase] = useState<string>("USD");
  const [data, setData] = useState<FxRatesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const { theme } = useTheme();
  const scope = useSourceScope(provOf(data));

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(false);
    api
      .fxRates(base)
      .then((d) => {
        if (active) {
          setData(d);
          setLoading(false);
        }
      })
      .catch(() => {
        if (active) {
          setError(true);
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [base, refreshNonce]);

  // Headline KPI pairs: filter to target currencies, skip base==quote
  const kpiPairs = useMemo(() => {
    if (!data) return [];
    return KPI_QUOTES.flatMap((q) => {
      const p = data.pairs.find((pair) => pair.pair === `${base}/${q}` || pair.quote === q);
      if (!p || p.pair === `${base}/${base}`) return [];
      return [p];
    }).slice(0, 6);
  }, [data, base]);

  // All pairs excluding base==quote identity
  const allPairs = useMemo(() => {
    if (!data) return [];
    return data.pairs.filter((p) => {
      const [b, q] = p.pair.split("/");
      return b !== q;
    });
  }, [data]);

  return (
    <Card {...scope}>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div className="flex flex-col gap-0.5">
          <h2 className="text-base font-semibold text-text-primary">FX Rates</h2>
          {data?.asOf && (
            <span className="text-xs text-text-muted">as of {data.asOf}</span>
          )}
        </div>
        <select
          className="input text-sm py-1"
          value={base}
          onChange={(e) => setBase(e.target.value)}
        >
          {BASES.map((b) => (
            <option key={b} value={b} className="bg-surface">
              {b}
            </option>
          ))}
        </select>
      </div>

      {/* Loading state */}
      {loading && !data && <Skeleton className="h-64" />}

      {/* Error / empty state */}
      {!loading && (error || (data && data.pairs.length === 0)) && (
        <p className="text-text-muted text-sm">FX data unavailable.</p>
      )}

      {/* Content */}
      {!loading && data && data.pairs.length > 0 && (
        <>
          {/* KPI Strip */}
          {kpiPairs.length > 0 && (
            <div className="flex flex-wrap gap-3 mb-6">
              {kpiPairs.map((pair) => (
                <KpiTile key={pair.pair} pair={pair} />
              ))}
            </div>
          )}

          {/* Full Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-text-muted text-xs">
                  <th className="text-left pb-2 font-medium">Pair</th>
                  <th className="text-right pb-2 font-medium">Rate</th>
                  <th className="text-right pb-2 font-medium">1D%</th>
                  <th className="text-right pb-2 font-medium">1W%</th>
                  <th className="text-right pb-2 font-medium">1M%</th>
                  <th className="text-right pb-2 font-medium">1Y%</th>
                  <th className="text-right pb-2 font-medium pr-1">30D</th>
                </tr>
              </thead>
              <tbody>
                {allPairs.map((pair) => {
                  const isUp =
                    pair.change1d !== null
                      ? pair.change1d >= 0
                      : pair.sparkline.length >= 2
                      ? pair.sparkline[pair.sparkline.length - 1] >= pair.sparkline[0]
                      : true;
                  return (
                    <tr
                      key={pair.pair}
                      className="border-b border-border/50 hover:bg-surface-alt/60 transition-colors"
                      data-prov={`pairs.${pair.quote}`}
                      data-prov-ctx={pair.pair}
                    >
                      <td className="py-2 text-text-primary font-medium">{pair.pair}</td>
                      <td className="py-2 text-right font-mono text-text-primary">
                        {pair.rate === null ? "—" : fmtNum(pair.rate, 4)}
                      </td>
                      <td className="py-2 text-right" data-prov={`pairs.${pair.quote}.change1d`}>
                        <ChangeCell value={pair.change1d} />
                      </td>
                      <td className="py-2 text-right" data-prov={`pairs.${pair.quote}.change1w`}>
                        <ChangeCell value={pair.change1w} />
                      </td>
                      <td className="py-2 text-right" data-prov={`pairs.${pair.quote}.change1m`}>
                        <ChangeCell value={pair.change1m} />
                      </td>
                      <td className="py-2 text-right" data-prov={`pairs.${pair.quote}.change1y`}>
                        <ChangeCell value={pair.change1y} />
                      </td>
                      <td className="py-2 text-right">
                        <div className="flex justify-end">
                          <SparklineCell values={pair.sparkline} positive={isUp} />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}
