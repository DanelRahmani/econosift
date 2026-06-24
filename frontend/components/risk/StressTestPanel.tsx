"use client";

import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import { Card } from "@/components/ui";
import { chartTooltipStyle, chartPalette } from "@/components/ui";
import { fmtPct } from "@/lib/format";
import { api } from "@/lib/api";
import type { StressTestResponse, StressScenarioResult } from "@/lib/types";

interface Props {
  ticker: string;
  theme: "light" | "dark";
}

const SCENARIO_META: Record<string, { emoji: string; period: string; description: string }> = {
  gfc:    { emoji: "🏦", period: "Oct '07 – Mar '09", description: "S&P 500 fell ~57% as credit markets froze" },
  covid:  { emoji: "🦠", period: "Feb '20 – Mar '20", description: "Fastest 30%+ market decline in history (~33 days)" },
  rates:  { emoji: "📈", period: "Jan '22 – Oct '22", description: "Fed's fastest rate-hiking cycle since 1980; S&P –25%" },
  dotcom: { emoji: "💻", period: "Mar '00 – Oct '02", description: "Nasdaq fell ~78% as tech valuations collapsed" },
};

function ScenarioCard({
  scenario, theme,
}: { scenario: StressScenarioResult; theme: "light" | "dark" }) {
  const [expanded, setExpanded] = useState(false);
  const meta = SCENARIO_META[scenario.scenario];
  const tooltip = chartTooltipStyle(theme);
  const palette = chartPalette(theme);

  return (
    <Card className="p-4 space-y-2">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-lg">{meta?.emoji}</span>
            <h4 className="text-sm font-semibold">{scenario.label}</h4>
          </div>
          <p className="text-xs text-text-muted mt-0.5">{meta?.period} · {meta?.description}</p>
        </div>
        <div className="text-right">
          <div className={`text-lg font-bold tabular-nums ${(scenario.totalReturn ?? 0) < 0 ? "text-danger" : "text-success"}`}>
            {scenario.totalReturn !== null ? fmtPct(scenario.totalReturn * 100) : "—"}
          </div>
          <div className="text-xs text-text-muted">Total return</div>
        </div>
      </div>

      {scenario.error ? (
        <div className="text-xs text-warning">{scenario.error}</div>
      ) : (
        <>
          <div className="flex gap-4 text-xs">
            <div>
              <span className="text-text-muted">Max DD: </span>
              <span className={`font-semibold ${(scenario.maxDrawdown ?? 0) < -0.1 ? "text-danger" : ""}`}>
                {scenario.maxDrawdown !== null ? fmtPct(scenario.maxDrawdown * 100) : "—"}
              </span>
            </div>
            <button
              onClick={() => setExpanded((e) => !e)}
              className="text-accent hover:underline ml-auto"
            >
              {expanded ? "Hide chart" : "Show chart"}
            </button>
          </div>

          {expanded && scenario.returnsTimeSeries.length > 0 && (
            <ResponsiveContainer width="100%" height={160}>
              <LineChart
                data={scenario.returnsTimeSeries}
                margin={{ top: 4, right: 8, left: -20, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={palette.grid} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 9, fill: palette.axis }}
                  tickFormatter={(v) => v?.slice(0, 7) ?? ""}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fontSize: 9, fill: palette.axis }}
                  tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                />
                <Tooltip
                  {...tooltip}
                  formatter={(v: number) => [`${(v * 100).toFixed(2)}%`, "Cumulative Return"]}
                />
                <ReferenceLine y={0} stroke={palette.axis} strokeDasharray="4 2" />
                <Line dataKey="value" stroke="#c4394a" dot={false} strokeWidth={1.5} name={scenario.scenario.toUpperCase()} />
                {scenario.benchmark && (
                  <Line
                    data={scenario.benchmark}
                    dataKey="value"
                    stroke="#6b7280"
                    dot={false}
                    strokeWidth={1}
                    strokeDasharray="4 2"
                    name="Benchmark"
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          )}
        </>
      )}
    </Card>
  );
}

export function StressTestPanel({ ticker, theme }: Props) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<StressTestResponse | null>(null);

  async function runStress() {
    setLoading(true);
    try {
      const res = await api.riskStress(ticker);
      setResult(res);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">Historical Stress Testing</h3>
          <span className="px-1.5 py-0.5 rounded text-xs bg-danger/20 text-danger font-medium">
            Run Analysis
          </span>
        </div>
      </div>

      <p className="text-xs text-text-muted">
        Replays {ticker}'s actual historical returns across 4 major market crises. Requires
        sufficient historical data (pre-2001 for dot-com). Returns and drawdowns computed
        from real price sequences.
      </p>

      <div className="p-3 rounded-md bg-warning/10 border border-warning/30 text-xs text-warning">
        Compute-intensive — fetches 10 years of price history and may take 15–30s.
      </div>

      <button
        onClick={runStress}
        disabled={loading}
        className="w-full py-2 rounded-md text-sm font-medium bg-danger/10 text-danger border border-danger/30 hover:bg-danger hover:text-white transition-colors disabled:opacity-50"
      >
        {loading ? "Running stress tests…" : "Run Stress Analysis (4 scenarios)"}
      </button>

      {result && (
        <div className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {result.scenarios.map((s) => (
              <ScenarioCard key={s.scenario} scenario={s} theme={theme} />
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
