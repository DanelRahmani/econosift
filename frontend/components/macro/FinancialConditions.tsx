"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { asOf } from "@/lib/series";
import type { FinancialConditionsData, CreditGapsData } from "@/lib/types";
import { Card } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { legendProv } from "./legendProv";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  AreaChart,
  Area,
  BarChart,
  Bar,
  Cell,
} from "recharts";

const GRID = "rgba(255,255,255,0.08)";

function KpiCard({
  label,
  value,
  unit = "",
  color,
  sub,
  prov,
}: {
  label: string;
  value: number | null;
  unit?: string;
  color?: string;
  sub?: string;
  prov?: string;
}) {
  return (
    <Card className="p-4" data-prov={prov} data-prov-ctx={label}>
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${color ?? ""}`}>
        {value != null ? `${value.toFixed(2)}${unit}` : "—"}
      </div>
      {sub && <div className="text-xs text-text-secondary mt-0.5">{sub}</div>}
    </Card>
  );
}

function nfciColor(v: number | null): string {
  if (v == null) return "";
  if (v > 0.5) return "text-danger";
  if (v > 0) return "text-warning";
  return "text-success";
}

export function FinancialConditions() {
  const [data, setData] = useState<FinancialConditionsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [epuLogScale, setEpuLogScale] = useState(false);
  const [fundingData, setFundingData] = useState<any>(null);
  const [creditGaps, setCreditGaps] = useState<CreditGapsData | null>(null);
  const scope = useSourceScope(provOf(data));
  const fundingScope = useSourceScope(provOf(fundingData));
  const gapsScope = useSourceScope(provOf(creditGaps));

  useEffect(() => {
    api
      .macroFinancialConditions()
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
    api.macroFunding().then(setFundingData).catch(() => {});
    api.macroCreditGaps().then(setCreditGaps).catch(() => {});
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-40 animate-pulse bg-surface-alt rounded" />
        ))}
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-text-secondary text-sm py-8 text-center">
        Financial conditions data unavailable — backend endpoint not yet
        implemented.
      </div>
    );
  }

  const { kpis, history } = data;

  const stlfsiAt = asOf(history.stlfsi);
  const stressData = (history.nfci ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    NFCI: pt.value,
    STLFSI: stlfsiAt(pt.date),
  }));

  // Backend now returns $T for Fed BS
  const balanceSheetData = (history.fedBalanceSheet ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    "US Fed Balance Sheet ($T)": pt.value,
  }));

  const delinquencyData = (history.creditCardDelinquency ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    "Credit Card Delinquency %": pt.value,
  }));

  // Backend returns $T for C&I loans
  const loansData = (history.ciLoans ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    "C&I Loans ($T)": pt.value,
  }));

  const epuData = (history.economicPolicyUncertainty ?? []).map((pt) => ({
    date: pt.date.slice(0, 7),
    "Economic Policy Uncertainty": pt.value,
  }));

  return (
    <div className="space-y-6" {...scope}>
      {/* KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <KpiCard
          label="NFCI"
          prov="kpis.nfci"
          value={kpis.nfci}
          sub="Negative = loose, Positive = tight"
          color={nfciColor(kpis.nfci)}
        />
        <KpiCard
          label="STLFSI4"
          prov="kpis.stlfsi"
          value={kpis.stlfsi}
          sub="St. Louis Fed Financial Stress Index"
          color={
            kpis.stlfsi != null && kpis.stlfsi > 0 ? "text-danger" : "text-success"
          }
        />
        <KpiCard
          label="US Fed Balance Sheet"
          prov="kpis.fedBalanceSheet"
          value={kpis.fedBalanceSheet}
          unit="$T"
          sub="Total assets"
        />
        <KpiCard
          label="C&I Loans"
          prov="kpis.ciLoans"
          value={kpis.ciLoans}
          unit="$T"
          sub="Commercial & Industrial"
        />
      </div>

      {/* NFCI + STLFSI */}
      {stressData.length > 0 && (
        <Card className="p-4" data-prov="history.nfci" data-prov-ctx="Financial stress indexes (NFCI, STLFSI4)">
          <h3 className="font-semibold mb-1">Financial Stress Indexes</h3>
          <p className="text-xs text-text-secondary mb-3">
            NFCI (Chicago Fed): 0 = average. Positive = tighter than average.
            STLFSI4 (St. Louis Fed): similar interpretation.
          </p>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={stressData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend formatter={legendProv({ NFCI: "history.nfci", STLFSI: "history.stlfsi" })} />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.3)" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="NFCI" stroke="#3b82f6" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="STLFSI" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* US Federal Reserve Balance Sheet */}
      {balanceSheetData.length > 0 && (
        <Card className="p-4" data-prov="history.fedBalanceSheet" data-prov-ctx="US Federal Reserve balance sheet">
          <h3 className="font-semibold mb-1">US Federal Reserve Balance Sheet</h3>
          <p className="text-xs text-text-secondary mb-3">
            Total assets (USD trillions). QE = expansion; QT = contraction.
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={balanceSheetData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `$${v}T`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`$${v?.toFixed(2)}T`]} />
              <Area
                type="monotone"
                dataKey="US Fed Balance Sheet ($T)"
                stroke="#3b82f6"
                fill="#3b82f6"
                fillOpacity={0.2}
                strokeWidth={2}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Credit Card Delinquency */}
      {delinquencyData.length > 0 && (
        <Card className="p-4" data-prov="history.creditCardDelinquency" data-prov-ctx="Credit card delinquency rate">
          <h3 className="font-semibold mb-1">Credit Card Delinquency Rate (%)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Share of credit card balances 90+ days overdue — signals consumer stress.
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={delinquencyData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <Line
                type="monotone"
                dataKey="Credit Card Delinquency %"
                stroke="#ef4444"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* C&I Loans */}
      {loansData.length > 0 && (
        <Card className="p-4" data-prov="history.ciLoans" data-prov-ctx="Commercial & industrial loans">
          <h3 className="font-semibold mb-1">Commercial & Industrial Loans ($T)</h3>
          <p className="text-xs text-text-secondary mb-3">
            Bank lending to businesses — slowdown signals tighter credit.
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={loansData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `$${v}T`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`$${v?.toFixed(3)}T`]} />
              <Line
                type="monotone"
                dataKey="C&I Loans ($T)"
                stroke="#10b981"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Economic Policy Uncertainty */}
      {epuData.length > 0 && (
        <Card className="p-4" data-prov="history.economicPolicyUncertainty" data-prov-ctx="Economic policy uncertainty index">
          <div className="flex items-center justify-between mb-1">
            <h3 className="font-semibold">Economic Policy Uncertainty Index</h3>
            <button
              onClick={() => setEpuLogScale(!epuLogScale)}
              className={`px-2 py-1 text-xs rounded border transition-colors ${
                epuLogScale ? "border-accent bg-accent/10 text-accent" : "border-border text-text-muted hover:text-text-primary"
              }`}
            >
              {epuLogScale ? "Log Scale" : "Linear Scale"}
            </button>
          </div>
          <p className="text-xs text-text-secondary mb-3">
            Baker, Bloom & Davis index. Higher = more uncertainty. {epuLogScale ? "Log scale reduces outlier skew." : ""}
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={epuData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} scale={epuLogScale ? "log" : "linear"} domain={["auto", "auto"]} />
              <Tooltip formatter={(v: number) => [v?.toFixed(0), "EPU Index"]} />
              <Line
                type="monotone"
                dataKey="Economic Policy Uncertainty"
                stroke="#8b5cf6"
                dot={false}
                strokeWidth={1.5}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* ── Funding & Liquidity ── */}
      {fundingData && !fundingData.error && (
        <>
          <h2 className="font-semibold text-lg border-t border-border pt-6 mt-2">Funding &amp; Liquidity</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4" {...fundingScope}>
            {fundingData.m2?.length > 0 && (
              <Card className="p-4" data-prov="m2" data-prov-ctx="M2 money supply">
                <h3 className="font-semibold text-sm mb-2">M2 Money Supply</h3>
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={fundingData.m2}>
                    <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                    <XAxis dataKey="date" hide /><YAxis domain={['auto','auto']} width={40} fontSize={10} /><Tooltip />
                    <Line type="monotone" dataKey="value" stroke="#3b82f6" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Card>
            )}
            {fundingData.sofr?.length > 0 && (
              <Card className="p-4" data-prov="sofr" data-prov-ctx="SOFR">
                <h3 className="font-semibold text-sm mb-2">SOFR</h3>
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={fundingData.sofr}>
                    <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                    <XAxis dataKey="date" hide /><YAxis domain={['auto','auto']} width={40} fontSize={10} /><Tooltip />
                    <Line type="monotone" dataKey="value" stroke="#f59e0b" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Card>
            )}
            {fundingData.cp_spread?.length > 0 && (
              <Card className="p-4" data-prov="cp_spread" data-prov-ctx="3M CP spread vs fed funds">
                <h3 className="font-semibold text-sm mb-2">3M CP Spread vs Fed Funds</h3>
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={fundingData.cp_spread}>
                    <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                    <XAxis dataKey="date" hide /><YAxis domain={['auto','auto']} width={40} fontSize={10} /><Tooltip />
                    <Line type="monotone" dataKey="value" stroke="#ef4444" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Card>
            )}
          </div>
        </>
      )}

      {/* ── BIS Credit-to-GDP Gaps ── */}
      {creditGaps && creditGaps.countries.length > 0 && (
        <Card className="p-4" data-prov-ctx="Global credit-to-GDP gaps" {...gapsScope}>
          <h3 className="font-semibold mb-1">
            🌍 Global Credit-to-GDP Gaps
          </h3>
          <p className="text-xs text-text-secondary mb-3">
            {creditGaps.note}. Green &lt;2pp · Yellow 2–10pp · Red &gt;10pp.
          </p>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart
              data={creditGaps.countries.filter((c) => c.latestGap != null).map((c) => ({
                name: c.name,
                gap: c.latestGap,
                signal: c.signal,
              }))}
              layout="vertical"
              margin={{ left: 80, right: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tickFormatter={(v) => `${v}pp`} tick={{ fontSize: 11 }} />
              <YAxis type="category" interval={0} dataKey="name" tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)} pp`, "Credit-to-GDP Gap"]} />
              <ReferenceLine x={10} stroke="#ef4444" strokeDasharray="4 4" label="BIS threshold" />
              <ReferenceLine x={2} stroke="#f59e0b" strokeDasharray="4 4" />
              <Bar dataKey="gap" radius={[0, 4, 4, 0]}>
                {(creditGaps.countries.filter((c) => c.latestGap != null).map((c) => {
                  const color = c.signal === "red" ? "#ef4444" : c.signal === "yellow" ? "#f59e0b" : "#10b981";
                  return <Cell key={c.iso2} fill={color} fillOpacity={0.8} />;
                }) as any)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs text-text-secondary mt-2">
            Source: {creditGaps.source}. Gaps measure deviation from long-term credit/GDP trend.
          </p>
        </Card>
      )}
    </div>
  );
}
