"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { CreditConditionsData, ConditionSignal } from "@/lib/types";
import { Card, ChartSkeleton, chartPalette } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";
import { legendProv } from "./legendProv";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { useRefreshNonce } from "@/lib/refresh";

function fmt(v: number | null | undefined, decimals = 2, suffix = ""): string {
  return v != null ? `${v.toFixed(decimals)}${suffix}` : "—";
}

function signalColor(signal: ConditionSignal | undefined): string {
  if (signal === "stress") return "text-danger";
  if (signal === "normal") return "text-success";
  return "";
}

function ConditionKpi({
  label,
  value,
  signal,
  sub,
  asOf,
  prov,
}: {
  label: string;
  value: string;
  signal?: ConditionSignal;
  sub: string;
  asOf?: string | null;
  prov?: string;
}) {
  return (
    <Card className="p-4" data-prov={prov} data-prov-ctx={label}>
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${signalColor(signal)}`}>{value}</div>
      <div className="text-xs text-text-secondary mt-0.5">{sub}</div>
      {asOf && <div className="text-[10px] text-text-muted mt-1">as of {asOf}</div>}
    </Card>
  );
}

export function CreditConditions() {
  const [data, setData] = useState<CreditConditionsData | null>(null);
  const [loading, setLoading] = useState(true);
  const scope = useSourceScope(provOf(data));
  const pal = chartPalette("dark");

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    api
      .macroCreditConditions()
      .then(setData)
      .catch(() => setData({ error: "unavailable" }))
      .finally(() => setLoading(false));
  }, [refreshNonce]);

  const kpis = data?.kpis;
  const signals = data?.signals;
  const hist = data?.history;

  // EBP and the GZ credit spread share a monthly grid.
  const ebpChart = useMemo(() => {
    const gz = new Map((hist?.gz_spread ?? []).map((p) => [p.date, p.value]));
    return (hist?.ebp ?? []).map((p) => ({
      date: p.date.slice(0, 7),
      "Excess Bond Premium": p.value,
      "GZ Credit Spread": gz.get(p.date) ?? null,
    }));
  }, [hist]);

  // NFCI vs ANFCI, weekly.
  const nfciChart = useMemo(() => {
    const adj = new Map((hist?.anfci ?? []).map((p) => [p.date, p.value]));
    return (hist?.nfci ?? []).map((p) => ({
      date: p.date.slice(0, 7),
      NFCI: p.value,
      ANFCI: adj.get(p.date) ?? null,
    }));
  }, [hist]);

  const sofrChart = useMemo(
    () => (hist?.sofr_iorb ?? []).map((p) => ({ date: p.date, value: p.value })),
    [hist]
  );

  const sloosChart = useMemo(
    () => (hist?.sloos_ci ?? []).map((p) => ({ date: p.date.slice(0, 7), value: p.value })),
    [hist]
  );

  if (loading) return <ChartSkeleton />;

  if (!data || data.error || !kpis) {
    return (
      <Card className="p-4">
        <h3 className="font-semibold mb-1">Credit &amp; Funding Conditions</h3>
        <p className="text-sm text-text-secondary">
          {data?.error === "FRED API key required"
            ? "A FRED API key is required for these indicators. Add one in Admin → API Keys."
            : "Credit conditions data is currently unavailable — the upstream source did not return data."}
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-6" {...scope}>
      <div>
        <h2 className="font-semibold text-lg">Credit &amp; Funding Conditions</h2>
        <p className="text-xs text-text-secondary mt-1">
          Four indicators with the strongest out-of-sample evidence for predicting real
          activity and returns. Each has a documented causal transmission channel, not
          just a correlation.
        </p>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <ConditionKpi
          label="SOFR − IORB"
          prov="kpis.sofr_iorb"
          value={fmt(kpis.sofr_iorb, 2, " pp")}
          signal={signals?.sofr_iorb}
          sub="Above 0 = repo pricing through the Fed's floor, i.e. reserves scarce"
          asOf={data.asOf?.sofr_iorb}
        />
        <ConditionKpi
          label="SLOOS — C&I standards"
          prov="kpis.sloos_ci"
          value={fmt(kpis.sloos_ci, 1, "%")}
          signal={signals?.sloos_ci}
          sub="Net % of banks tightening. >20% has accompanied contractions"
          asOf={data.asOf?.sloos_ci}
        />
        <ConditionKpi
          label="Excess Bond Premium"
          prov="kpis.ebp"
          value={fmt(kpis.ebp, 2)}
          signal={signals?.ebp}
          sub="Spread beyond default risk. Positive = impaired risk appetite"
          asOf={data.asOf?.ebp}
        />
        <ConditionKpi
          label="ANFCI"
          prov="kpis.anfci"
          value={fmt(kpis.anfci, 2)}
          signal={signals?.anfci}
          sub="Conditions relative to the business cycle. >0 = tighter than warranted"
          asOf={data.asOf?.nfci}
        />
      </div>

      {/* Excess Bond Premium */}
      {ebpChart.length > 0 && (
        <Card className="p-4" data-prov="history.ebp" data-prov-ctx="Excess bond premium & GZ credit spread">
          <h3 className="font-semibold mb-1">Excess Bond Premium &amp; GZ Credit Spread</h3>
          <p className="text-xs text-text-secondary mb-3">
            Gilchrist &amp; Zakrajšek (2012) split corporate spreads into compensation for
            default risk and a residual — the EBP — that tracks intermediary risk-bearing
            capacity. The EBP is the stronger predictor of real activity of the two.
            {kpis.gz_recession_prob != null && (
              <>
                {" "}Their associated recession probability currently reads{" "}
                <span className="font-semibold text-text-primary" data-prov="kpis.gz_recession_prob" data-prov-ctx="GZ implied recession probability">
                  {(kpis.gz_recession_prob * 100).toFixed(1)}%
                </span>.
              </>
            )}
          </p>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={ebpChart}>
              <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => (v != null ? v.toFixed(3) : "—")} />
              <Legend formatter={legendProv({ "Excess Bond Premium": "history.ebp", "GZ Credit Spread": "history.gz_spread" })} />
              <ReferenceLine y={0} stroke={pal.axis} strokeDasharray="4 4" />
              <Line type="monotone" dataKey="Excess Bond Premium" stroke="#ef4444" dot={false} strokeWidth={1.6} />
              <Line type="monotone" dataKey="GZ Credit Spread" stroke="#3b82f6" dot={false} strokeWidth={1.2} />
            </LineChart>
          </ResponsiveContainer>
          <p className="text-[11px] text-text-muted mt-2">
            Source: {data.sources?.ebp}
          </p>
        </Card>
      )}

      {/* SLOOS */}
      {sloosChart.length > 0 && (
        <Card className="p-4" data-prov="history.sloos_ci" data-prov-ctx="SLOOS C&I lending standards">
          <h3 className="font-semibold mb-1">Bank Lending Standards — C&amp;I Loans</h3>
          <p className="text-xs text-text-secondary mb-3">
            Net percentage of senior loan officers reporting tighter standards. Lown &amp;
            Morgan (2006) found this predicts output declines better than the fed funds
            rate itself — banks refusing to lend <em>is</em> the transmission mechanism,
            not a proxy for it. Quarterly, so it moves slowly.
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={sloosChart}>
              <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(1)}%`, "Net tightening"]} />
              <ReferenceLine y={0} stroke={pal.axis} />
              <ReferenceLine y={20} stroke="#ef4444" strokeDasharray="4 4" label={{ value: "contraction zone", fontSize: 10, fill: "#ef4444" }} />
              <Bar dataKey="value" radius={[2, 2, 0, 0]}>
                {sloosChart.map((d, i) => (
                  <Cell key={i} fill={(d.value ?? 0) > 0 ? "#ef4444" : "#10b981"} fillOpacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* SOFR - IORB */}
      {sofrChart.length > 0 && (
        <Card className="p-4" data-prov="history.sofr_iorb" data-prov-ctx="SOFR minus IORB">
          <h3 className="font-semibold mb-1">Reserve Scarcity — SOFR minus IORB</h3>
          <p className="text-xs text-text-secondary mb-3">
            Secured overnight repo against the rate the Fed pays on reserves. A persistently
            positive spread means cash is scarce enough that borrowers will pay above the
            administered floor — the September 2019 repo squeeze showed here first. IOER is
            spliced in before IORB replaced it on 2021-07-29.
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={sofrChart}>
              <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(3)} pp`, "SOFR − IORB"]} />
              <ReferenceLine y={0} stroke={pal.axis} strokeDasharray="4 4" />
              <ReferenceLine y={0.1} stroke="#ef4444" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="value" stroke="#f59e0b" dot={false} strokeWidth={1.4} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* NFCI vs ANFCI */}
      {nfciChart.length > 0 && (
        <Card className="p-4" data-prov="history.nfci" data-prov-ctx="NFCI vs ANFCI">
          <h3 className="font-semibold mb-1">NFCI vs ANFCI</h3>
          <p className="text-xs text-text-secondary mb-3">
            Chicago Fed composite financial conditions, weekly. ANFCI is orthogonalised to
            growth and inflation, so it isolates conditions that are loose or tight{" "}
            <em>relative to</em> where the economy actually is — the more informative of the
            two. Zero = average conditions; positive = tighter.
          </p>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={nfciChart}>
              <CartesianGrid strokeDasharray="3 3" stroke={pal.grid} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => (v != null ? v.toFixed(3) : "—")} />
              <Legend formatter={legendProv({ NFCI: "history.nfci", ANFCI: "history.anfci" })} />
              <ReferenceLine y={0} stroke={pal.axis} strokeDasharray="4 4" />
              <Line type="monotone" dataKey="NFCI" stroke="#3b82f6" dot={false} strokeWidth={1.3} />
              <Line type="monotone" dataKey="ANFCI" stroke="#8b5cf6" dot={false} strokeWidth={1.6} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Extended reference table */}
      <Card className="p-4">
        <h3 className="font-semibold mb-3">Indicator Reference</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-text-secondary border-b border-border">
                <th className="py-2 pr-4 font-medium">Indicator</th>
                <th className="py-2 pr-4 font-medium">Latest</th>
                <th className="py-2 pr-4 font-medium">Frequency</th>
                <th className="py-2 pr-4 font-medium">Evidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              <tr data-prov="kpis.sofr_iorb" data-prov-ctx="SOFR − IORB">
                <td className="py-2 pr-4">SOFR − IORB</td>
                <td className="py-2 pr-4 font-mono">{fmt(kpis.sofr_iorb, 3, " pp")}</td>
                <td className="py-2 pr-4 text-text-secondary">Daily</td>
                <td className="py-2 pr-4 text-text-secondary">Mechanical — repo above the administered floor is definitionally reserve scarcity</td>
              </tr>
              <tr data-prov="kpis.sloos_ci" data-prov-ctx="SLOOS net tightening (C&I)">
                <td className="py-2 pr-4">SLOOS net tightening (C&amp;I)</td>
                <td className="py-2 pr-4 font-mono">{fmt(kpis.sloos_ci, 1, "%")}</td>
                <td className="py-2 pr-4 text-text-secondary">Quarterly</td>
                <td className="py-2 pr-4 text-text-secondary">Lown &amp; Morgan (2006, JMCB); Bassett et al. (2014, JME)</td>
              </tr>
              <tr data-prov="kpis.ebp" data-prov-ctx="Excess bond premium">
                <td className="py-2 pr-4">Excess Bond Premium</td>
                <td className="py-2 pr-4 font-mono">{fmt(kpis.ebp, 3)}</td>
                <td className="py-2 pr-4 text-text-secondary">Monthly</td>
                <td className="py-2 pr-4 text-text-secondary">Gilchrist &amp; Zakrajšek (2012, AER)</td>
              </tr>
              <tr data-prov="kpis.gz_spread" data-prov-ctx="GZ credit spread">
                <td className="py-2 pr-4">GZ credit spread</td>
                <td className="py-2 pr-4 font-mono">{fmt(kpis.gz_spread, 3)}</td>
                <td className="py-2 pr-4 text-text-secondary">Monthly</td>
                <td className="py-2 pr-4 text-text-secondary">Gilchrist &amp; Zakrajšek (2012, AER)</td>
              </tr>
              <tr data-prov="kpis.nfci" data-prov-ctx="NFCI">
                <td className="py-2 pr-4">NFCI</td>
                <td className="py-2 pr-4 font-mono">{fmt(kpis.nfci, 3)}</td>
                <td className="py-2 pr-4 text-text-secondary">Weekly</td>
                <td className="py-2 pr-4 text-text-secondary">Chicago Fed composite of 105 financial indicators</td>
              </tr>
              <tr data-prov="kpis.anfci" data-prov-ctx="ANFCI">
                <td className="py-2 pr-4">ANFCI</td>
                <td className="py-2 pr-4 font-mono">{fmt(kpis.anfci, 3)}</td>
                <td className="py-2 pr-4 text-text-secondary">Weekly</td>
                <td className="py-2 pr-4 text-text-secondary">NFCI orthogonalised to growth and inflation</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-text-muted mt-3">
          Predictive content is not the same as tradeable alpha: these largely proxy for
          risk premia, so they signal loudest when risk is already being repriced.
        </p>
      </Card>
    </div>
  );
}
