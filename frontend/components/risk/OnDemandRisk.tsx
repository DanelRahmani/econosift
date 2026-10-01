"use client";

import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { Card } from "@/components/ui";
import { chartTooltipStyle, chartPalette } from "@/components/ui";
import { fmtNum, fmtPct } from "@/lib/format";
import { api } from "@/lib/api";
import type { GarchResult, HurstResult, OUResponse, CointegrationResult } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

interface Props {
  ticker: string;
  tickers: string;
  theme: "light" | "dark";
}

function PanelShell({
  title, badge, children, onCalculate, loading, scope, tier = "yellow",
}: {
  title: string;
  badge?: string;
  children: React.ReactNode;
  onCalculate: () => void;
  loading: boolean;
  scope?: Record<string, string>;
  tier?: "yellow";
}) {
  return (
    <Card className="p-4 space-y-3" {...scope}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">{title}</h3>
          {badge && (
            <span className="px-1.5 py-0.5 rounded text-xs bg-warning/20 text-warning font-medium">
              {badge}
            </span>
          )}
        </div>
        <button
          onClick={onCalculate}
          disabled={loading}
          className="px-3 py-1.5 rounded-md text-xs font-medium bg-accent/10 text-accent border border-accent/30 hover:bg-accent hover:text-white transition-colors disabled:opacity-50"
        >
          {loading ? "Calculating…" : "Calculate"}
        </button>
      </div>
      {children}
    </Card>
  );
}

export function OnDemandRisk({ ticker, tickers, theme }: Props) {
  const palette = chartPalette(theme);
  const tooltip = chartTooltipStyle(theme);

  // GARCH
  const [garchLoading, setGarchLoading] = useState(false);
  const [garch, setGarch] = useState<GarchResult | null>(null);

  // Hurst
  const [hurstLoading, setHurstLoading] = useState(false);
  const [hurst, setHurst] = useState<HurstResult | null>(null);

  // OU
  const [ouLoading, setOuLoading] = useState(false);
  const [ou, setOU] = useState<OUResponse | null>(null);

  // Cointegration
  const [cointLoading, setCointLoading] = useState(false);
  const [coint, setCoint] = useState<CointegrationResult | null>(null);

  const garchScope = useSourceScope(provOf(garch));
  const hurstScope = useSourceScope(provOf(hurst));
  const ouScope = useSourceScope(provOf(ou));
  const cointScope = useSourceScope(provOf(coint));

  async function calcGarch() {
    setGarchLoading(true);
    try {
      const res = await api.riskGarch(ticker);
      setGarch(res);
    } finally {
      setGarchLoading(false);
    }
  }

  async function calcHurst() {
    setHurstLoading(true);
    try {
      const res = await api.riskHurst(ticker);
      setHurst(res);
    } finally {
      setHurstLoading(false);
    }
  }

  async function calcOU() {
    setOuLoading(true);
    try {
      const res = await api.riskOU(tickers);
      setOU(res);
    } finally {
      setOuLoading(false);
    }
  }

  async function calcCoint() {
    setCointLoading(true);
    try {
      const res = await api.riskCointegration(tickers);
      setCoint(res);
    } finally {
      setCointLoading(false);
    }
  }

  const tickerList = tickers.split(",").map((t) => t.trim()).filter(Boolean);
  const hasPair = tickerList.length >= 2;

  return (
    <div className="space-y-4">
      {/* GARCH */}
      <PanelShell
        title="GARCH(1,1) Volatility Model"
        badge="~3s"
        onCalculate={calcGarch}
        loading={garchLoading}
        scope={garchScope}
      >
        <p className="text-xs text-text-muted">
          Fits a GARCH(1,1) model to {ticker}&apos;s return history. Returns conditional variance
          parameters and a 1-day-ahead volatility forecast.
        </p>
        {garch && !garch.error && (
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 pt-1">
            {[
              { label: "ω (omega)", value: fmtNum(garch.omega, 6), prov: "omega" },
              { label: "α (alpha)", value: fmtNum(garch.alpha) },
              { label: "β (beta)", value: fmtNum(garch.beta) },
              { label: "Persistence α+β", value: fmtNum((garch.alpha ?? 0) + (garch.beta ?? 0)) },
              { label: "1D Forecast Vol", value: garch.annForecastVol !== null ? fmtPct(garch.annForecastVol * 100) : "—", prov: "annForecastVol" },
            ].map(({ label, value, prov }) => (
              <div key={label} data-prov={prov}>
                <div className="text-xs text-text-muted">{label}</div>
                <div className="text-sm font-semibold tabular-nums">{value}</div>
              </div>
            ))}
          </div>
        )}
        {garch?.error && <div className="text-xs text-danger">{garch.error}</div>}
      </PanelShell>

      {/* Hurst */}
      <PanelShell
        title="Hurst Exponent"
        badge="~2s"
        onCalculate={calcHurst}
        loading={hurstLoading}
        scope={hurstScope}
      >
        <p className="text-xs text-text-muted">
          R/S analysis on {ticker}&apos;s price series. H &lt; 0.5 = mean-reverting, H ≈ 0.5 = random walk,
          H &gt; 0.5 = trending.
        </p>
        {hurst && (
          <div className="flex items-center gap-4 pt-1">
            <div data-prov="*">
              <div className="text-xs text-text-muted">Hurst Exponent</div>
              <div className="text-2xl font-bold tabular-nums">{fmtNum(hurst.hurst)}</div>
            </div>
            <div data-prov="interpretation" className="text-sm text-text-secondary">{hurst.interpretation}</div>
          </div>
        )}
      </PanelShell>

      {/* OU Fit */}
      <PanelShell
        title="Ornstein-Uhlenbeck Fit"
        badge="~2s"
        onCalculate={calcOU}
        loading={ouLoading}
        scope={ouScope}
      >
        <p className="text-xs text-text-muted">
          OLS-based OU process fit. Useful for mean-reversion strategy parameters.
          Applied to each of: {tickers}.
        </p>
        {ou && (
          <div className="space-y-3 pt-1">
            {ou.results.map((r) => (
              <div key={r.ticker} data-prov-ctx={r.ticker} className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="col-span-full text-xs font-mono font-semibold text-accent">{r.ticker}</div>
                {[
                  { label: "θ (mean reversion speed)", value: fmtNum(r.theta), prov: "theta" },
                  { label: "μ (long-run mean)", value: fmtNum(r.mu, 4), prov: "mu" },
                  { label: "σ (vol)", value: fmtNum(r.sigma), prov: "sigma" },
                  { label: "Half-life (days)", value: fmtNum(r.halfLifeDays, 1), prov: "halfLifeDays" },
                ].map(({ label, value, prov }) => (
                  <div key={label} data-prov={`results.${r.ticker}.${prov}`}>
                    <div className="text-xs text-text-muted">{label}</div>
                    <div className="text-sm font-semibold tabular-nums">{value}</div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </PanelShell>

      {/* Cointegration */}
      <PanelShell
        title="Pairs Cointegration Test"
        badge="~3s"
        onCalculate={calcCoint}
        loading={cointLoading}
        scope={cointScope}
      >
        {!hasPair ? (
          <p className="text-xs text-warning">Add a second ticker to run cointegration analysis.</p>
        ) : (
          <p className="text-xs text-text-muted">
            Engle-Granger cointegration test on {tickerList[0]} vs {tickerList[1]}.
            A p-value &lt; 0.05 suggests a stationary spread (pairs trading signal).
          </p>
        )}
        {coint && !coint.error && (
          <div className="space-y-3 pt-1">
            <div className="flex flex-wrap gap-6">
              {[
                { label: "P-value", value: fmtNum(coint.pValue, 4), prov: "pValue" },
                { label: "Cointegrated?", value: coint.isCointegrated ? "Yes" : "No", prov: "isCointegrated" },
                { label: "Hedge Ratio", value: fmtNum(coint.hedgeRatio), prov: "hedgeRatio" },
              ].map(({ label, value, prov }) => (
                <div key={label} data-prov={prov}>
                  <div className="text-xs text-text-muted">{label}</div>
                  <div className={`text-sm font-semibold ${label === "Cointegrated?" && coint.isCointegrated ? "text-success" : ""}`}>
                    {value}
                  </div>
                </div>
              ))}
            </div>
            {coint.spread.length > 0 && (
              <div data-prov="spread">
                <p className="text-xs text-text-muted mb-1">Spread (pair)</p>
                <ResponsiveContainer width="100%" height={120}>
                  <LineChart data={coint.spread} margin={{ top: 2, right: 8, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={palette.grid} />
                    <XAxis dataKey="date" tick={false} />
                    <YAxis tick={{ fontSize: 9, fill: palette.axis }} />
                    <Tooltip {...tooltip} formatter={(v: number) => [v?.toFixed(2), "Spread"]} />
                    <ReferenceLine y={0} stroke={palette.axis} strokeDasharray="4 2" />
                    <Line dataKey="value" stroke="#c4394a" dot={false} strokeWidth={1.5} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}
        {coint?.error && <div className="text-xs text-danger">{coint.error}</div>}
      </PanelShell>
    </div>
  );
}
