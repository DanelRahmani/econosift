"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FinancialConditionsData } from "@/lib/types";
import { Card } from "@/components/ui";
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
} from "recharts";

const GRID = "rgba(255,255,255,0.08)";

function KpiCard({
  label,
  value,
  unit = "",
  color,
  sub,
}: {
  label: string;
  value: number | null;
  unit?: string;
  color?: string;
  sub?: string;
}) {
  return (
    <Card className="p-4">
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

  useEffect(() => {
    api
      .macroFinancialConditions()
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
    api.macroFunding().then(setFundingData).catch(() => {});
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

  const stressData = (history.nfci ?? []).map((pt, i) => ({
    date: pt.date.slice(0, 7),
    NFCI: pt.value,
    STLFSI: history.stlfsi?.[i]?.value ?? null,
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
    <div className="space-y-6">
      {/* KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <KpiCard
          label="NFCI"
          value={kpis.nfci}
          sub="Negative = loose, Positive = tight"
          color={nfciColor(kpis.nfci)}
        />
        <KpiCard
          label="STLFSI4"
          value={kpis.stlfsi}
          sub="St. Louis Fed Financial Stress Index"
          color={
            kpis.stlfsi != null && kpis.stlfsi > 0 ? "text-danger" : "text-success"
          }
        />
        <KpiCard
          label="US Fed Balance Sheet"
          value={kpis.fedBalanceSheet}
          unit="$T"
          sub="Total assets"
        />
        <KpiCard
          label="C&I Loans"
          value={kpis.ciLoans}
          unit="$T"
          sub="Commercial & Industrial"
        />
      </div>

      {/* NFCI + STLFSI */}
      {stressData.length > 0 && (
        <Card className="p-4">
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
              <Legend />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.3)" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="NFCI" stroke="#3b82f6" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="STLFSI" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* US Federal Reserve Balance Sheet */}
      {balanceSheetData.length > 0 && (
        <Card className="p-4">
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
        <Card className="p-4">
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
        <Card className="p-4">
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
        <Card className="p-4">
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
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {fundingData.m2?.length > 0 && (
              <Card className="p-4">
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
              <Card className="p-4">
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
              <Card className="p-4">
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
    </div>
  );
}
