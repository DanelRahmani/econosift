"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { RatesData } from "@/lib/types";
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
  AreaChart,
  Area,
  ReferenceLine,
} from "recharts";

function KpiCard({
  label,
  value,
  unit = "%",
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
      {sub && <div className="text-xs text-text-secondary mt-1">{sub}</div>}
    </Card>
  );
}

const GRID = "rgba(255,255,255,0.08)";

export function RatesYields() {
  const [data, setData] = useState<RatesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api
      .macroRates()
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
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
        Rates data unavailable — backend endpoint not yet implemented.
      </div>
    );
  }

  const spread = data.spread_2y10y;
  const spreadColor =
    spread != null && spread < 0 ? "text-danger" : "text-success";

  const tenors = [
    "DGS3MO",
    "DGS2",
    "DGS5",
    "DGS7",
    "DGS10",
    "DGS20",
    "DGS30",
  ];
  const tenorLabels: Record<string, string> = {
    DGS3MO: "3M",
    DGS2: "2Y",
    DGS5: "5Y",
    DGS7: "7Y",
    DGS10: "10Y",
    DGS20: "20Y",
    DGS30: "30Y",
  };
  const curveData = tenors.map((t) => ({
    tenor: tenorLabels[t],
    yield: data.yields[t] ?? null,
  }));

  // Build historical multi-line data aligned by index
  const hist10y = data.history["DGS10"] ?? [];
  const hist2y = data.history["DGS2"] ?? [];
  const hist3m = data.history["DGS3MO"] ?? [];
  const histData = hist10y.map((pt, i) => ({
    date: pt.date.slice(0, 7),
    "10Y": pt.value,
    "2Y": hist2y[i]?.value ?? null,
    "3M": hist3m[i]?.value ?? null,
  }));

  const histBe5 = data.history["T5YIE"] ?? [];
  const histBe10 = data.history["T10YIE"] ?? [];
  const breakevenData = histBe5.map((pt, i) => ({
    date: pt.date.slice(0, 7),
    "5Y BE": pt.value,
    "10Y BE": histBe10[i]?.value ?? null,
  }));

  const histHY = data.history["BAMLH0A0HYM2"] ?? [];
  const histIG = data.history["BAMLC0A0CM"] ?? [];
  const spreadData = histHY.map((pt, i) => ({
    date: pt.date.slice(0, 7),
    "HY OAS": pt.value,
    "IG OAS": histIG[i]?.value ?? null,
  }));

  const taylorImplied = data.taylor_rule?.implied ?? [];
  const taylorActual = data.taylor_rule?.actual ?? [];
  const taylorData = taylorImplied.map((pt, i) => ({
    date: pt.date.slice(0, 7),
    "Taylor Rule": pt.value,
    Actual: taylorActual[i]?.value ?? null,
  }));

  const acmExp = data.acm?.expectations ?? [];
  const acmTP = data.acm?.term_premium ?? [];
  const acmData = acmExp.map((pt, i) => ({
    date: pt.date.slice(0, 7),
    Expectations: pt.value,
    "Term Premium": acmTP[i]?.value ?? null,
  }));

  return (
    <div className="space-y-6">
      {/* KPI Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <KpiCard label="Fed Funds Rate" value={data.yields["FEDFUNDS"] ?? null} />
        <KpiCard label="10Y Treasury" value={data.yields["DGS10"] ?? null} />
        <KpiCard label="2Y Treasury" value={data.yields["DGS2"] ?? null} />
        <KpiCard
          label="2Y/10Y Spread"
          value={spread}
          color={spreadColor}
          sub={data.inverted ? "INVERTED" : undefined}
        />
        <KpiCard
          label="30Y Mortgage"
          value={data.yields["MORTGAGE30US"] ?? null}
        />
      </div>

      {/* Yield Curve Snapshot */}
      <Card className="p-4">
        <h3 className="font-semibold mb-3 flex items-center gap-2">
          US Treasury Yield Curve
          {data.inverted && (
            <span className="text-xs bg-danger/20 text-danger px-2 py-0.5 rounded">
              INVERTED
            </span>
          )}
        </h3>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={curveData}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
            <XAxis dataKey="tenor" tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={(v) => `${v}%`} domain={["auto", "auto"]} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`, "Yield"]} />
            <Line
              type="monotone"
              dataKey="yield"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      {/* Historical Yields */}
      {histData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">Treasury Yields — Historical</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={histData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <Legend />
              <Line type="monotone" dataKey="10Y" stroke="#3b82f6" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="2Y" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="3M" stroke="#10b981" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* TIPS & Breakevens */}
      {breakevenData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">TIPS Breakeven Inflation</h3>
          <div className="flex flex-wrap gap-4 text-sm text-text-secondary mb-3">
            <span>
              5Y Breakeven:{" "}
              <strong className="text-text-primary">
                {data.yields["T5YIE"]?.toFixed(2) ?? "—"}%
              </strong>
            </span>
            <span>
              10Y Breakeven:{" "}
              <strong className="text-text-primary">
                {data.yields["T10YIE"]?.toFixed(2) ?? "—"}%
              </strong>
            </span>
            <span>
              10Y Real Yield:{" "}
              <strong className="text-text-primary">
                {data.yields["DFII10"]?.toFixed(2) ?? "—"}%
              </strong>
            </span>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={breakevenData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <Legend />
              <ReferenceLine
                y={2}
                stroke="rgba(255,255,255,0.3)"
                strokeDasharray="4 4"
                label={{
                  value: "2% target",
                  fill: "rgba(255,255,255,0.4)",
                  fontSize: 11,
                }}
              />
              <Line type="monotone" dataKey="5Y BE" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="10Y BE" stroke="#ef4444" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Credit Spreads */}
      {spreadData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">Credit Spreads (OAS)</h3>
          <div className="flex flex-wrap gap-4 text-sm text-text-secondary mb-3">
            <span>
              HY Spread:{" "}
              <strong className="text-text-primary">
                {data.yields["BAMLH0A0HYM2"]?.toFixed(0) ?? "—"} bps
              </strong>
            </span>
            <span>
              IG Spread:{" "}
              <strong className="text-text-primary">
                {data.yields["BAMLC0A0CM"]?.toFixed(0) ?? "—"} bps
              </strong>
            </span>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={spreadData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="HY OAS" stroke="#ef4444" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="IG OAS" stroke="#3b82f6" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Taylor Rule */}
      {taylorData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">Taylor Rule: Implied vs Actual Fed Funds</h3>
          <p className="text-xs text-text-secondary mb-3">
            r = 0.5 + π + 0.5(π − 2%) + 0.5 × output gap
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={taylorData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <Legend />
              <Line
                type="monotone"
                dataKey="Taylor Rule"
                stroke="#f59e0b"
                dot={false}
                strokeWidth={2}
                strokeDasharray="5 5"
              />
              <Line type="monotone" dataKey="Actual" stroke="#3b82f6" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* ACM Decomposition */}
      {acmData.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-1">ACM 10Y Yield Decomposition</h3>
          <p className="text-xs text-text-secondary mb-3">
            Expectations component vs term premium — Source:{" "}
            {data.acm?.source ?? "FRED"}
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={acmData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v?.toFixed(2)}%`]} />
              <Legend />
              <Area
                type="monotone"
                dataKey="Expectations"
                stackId="1"
                stroke="#3b82f6"
                fill="#3b82f6"
                fillOpacity={0.4}
              />
              <Area
                type="monotone"
                dataKey="Term Premium"
                stackId="1"
                stroke="#f59e0b"
                fill="#f59e0b"
                fillOpacity={0.4}
              />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
}
