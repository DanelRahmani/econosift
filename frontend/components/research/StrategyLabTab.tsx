"use client";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ResponsiveContainer, LineChart, Line, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import { apiQuery } from "@/lib/queries";
import { api } from "@/lib/api";
import type { StrategyParams, StrategyResult, StrategyRunBody, WalkForwardBody } from "@/lib/types";
import { Card, ControlBar, KpiStrip, KpiTile, ToggleChip, chartPalette, chartTooltipStyle } from "@/components/ui";
import { useTheme } from "@/components/ThemeProvider";
import { capPoints } from "@/lib/series";

/**
 * Strategy Lab — Phase 70. Compute tier: 🔴 Run Analysis only, never on mount.
 *
 * A strategy is a .py file with generate_weights(ctx); it runs in a sandboxed
 * subprocess over the point-in-time index universe. Uploading is off unless an
 * admin turns it on, and the page always says what the sandbox does and does not
 * isolate on this install: an upload is code running on this machine.
 */

const pct = (v: number | null | undefined, d = 1) => (v != null ? `${(v * 100).toFixed(d)}%` : "—");
const num = (v: number | null | undefined, d = 2) => (v != null ? v.toFixed(d) : "—");

function parseJson<T>(text: string, what: string): T {
  if (!text.trim()) return {} as T;
  try {
    const v = JSON.parse(text);
    if (v && typeof v === "object" && !Array.isArray(v)) return v as T;
  } catch {
    /* fall through */
  }
  throw new Error(`${what} must be a JSON object, e.g. {"top_n": 50}`);
}

export function StrategyLabTab() {
  const qc = useQueryClient();
  const { theme } = useTheme();
  const pal = chartPalette(theme);
  const tooltipStyle = chartTooltipStyle(theme);

  const listQ = useQuery(apiQuery("strategies"));
  const list = listQ.data;
  const [selected, setSelected] = useState("example:example_momentum");
  const [showSource, setShowSource] = useState(false);
  const sourceQ = useQuery({ ...apiQuery("strategySource", selected), enabled: showSource });

  const [index, setIndex] = useState<StrategyRunBody["index"]>("sp500");
  const [years, setYears] = useState(10);
  const [rebalance, setRebalance] = useState<StrategyRunBody["rebalance"]>("M");
  const [costBps, setCostBps] = useState(10);
  const [paramsText, setParamsText] = useState("");
  const [mode, setMode] = useState<"backtest" | "walkforward">("backtest");
  const [trainYears, setTrainYears] = useState(3);
  const [testYears, setTestYears] = useState(1);
  const [gridText, setGridText] = useState('{"top_n": [25, 50, 100]}');

  const upload = useMutation({
    mutationFn: async (file: File) => {
      if (list && file.size > list.limits.maxBytes) throw new Error(`the file is over ${list.limits.maxBytes / 1000} kB`);
      return api.uploadStrategy(file.name, await file.text());
    },
    onSuccess: (s) => {
      setSelected(s.id);
      qc.invalidateQueries({ queryKey: ["strategies"] });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteStrategy(id),
    onSuccess: () => {
      setSelected("example:example_momentum");
      qc.invalidateQueries({ queryKey: ["strategies"] });
    },
  });
  const run = useMutation({
    mutationFn: (): Promise<StrategyResult> => {
      const base: StrategyRunBody = {
        strategyId: selected, index, years, rebalance, costBps,
        params: parseJson<StrategyParams>(paramsText, "Parameters"),
      };
      if (mode === "backtest") return api.runStrategy(base);
      const body: WalkForwardBody = {
        ...base, trainYears, testYears, metric: "sharpe",
        grid: parseJson<WalkForwardBody["grid"]>(gridText, "The grid"),
      };
      return api.walkForward(body);
    },
  });

  const res = run.data;
  const curve = useMemo(() => {
    if (!res) return [];
    const dd = new Map(res.drawdown.map((p) => [p.date, p.value]));
    return capPoints(res.equityCurve.map((p) => ({ date: p.date, equity: p.value, drawdown: dd.get(p.date) ?? null })));
  }, [res]);

  const current = list?.strategies.find((s) => s.id === selected);
  const sandbox = list?.sandbox;

  return (
    <div className="space-y-5">
      <Card className="p-4 border-danger/60" role="alert">
        <div className="text-sm font-semibold text-danger">Uploading a strategy runs its Python code on this machine.</div>
        <p className="text-xs text-text-secondary mt-1">
          Only upload files you wrote or have read. Each run starts a short-lived process with no API keys, a{" "}
          {list?.limits.timeoutSeconds ?? 300} s time limit and a {list?.limits.memoryMB ?? 1536} MB memory limit.
          {" "}Uploads are {list?.uploadsEnabled ? <b>on</b> : <b>off</b>} (Admin → Strategy uploads).
        </p>
        {sandbox && (
          <ul className="text-xs text-text-secondary mt-2 space-y-0.5">
            {sandbox.supported ? (
              <>
                <li>Network: {sandbox.network}</li>
                <li>Files: {sandbox.filesystem}</li>
                <li>Memory: {sandbox.memory}</li>
              </>
            ) : (
              <li>Not available here: {sandbox.note}</li>
            )}
          </ul>
        )}
      </Card>

      <Card className="p-4 space-y-3">
        <ControlBar className="mb-0">
          <label className="text-xs text-text-secondary">Strategy</label>
          <select
            aria-label="Strategy"
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="bg-surface border border-border rounded px-2 py-1 text-sm"
          >
            {(list?.strategies ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}{s.builtIn ? " (example)" : ""}
              </option>
            ))}
          </select>
          <ToggleChip active={showSource} onClick={() => setShowSource((v) => !v)}>View code</ToggleChip>
          <label
            className={`text-xs px-3 py-1 rounded border border-border ${list?.uploadsEnabled
              ? "cursor-pointer hover:border-accent" : "opacity-50 cursor-not-allowed"}`}
            title={list?.uploadsEnabled ? "Upload a .py strategy" : "Uploads are off; an admin can turn them on"}
          >
            Upload .py
            <input
              type="file"
              accept=".py,text/x-python"
              className="hidden"
              disabled={!list?.uploadsEnabled || upload.isPending}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) upload.mutate(f);
                e.target.value = "";
              }}
            />
          </label>
          {current && !current.builtIn && (
            <button className="text-xs text-danger hover:underline" onClick={() => remove.mutate(current.id)}>
              Delete
            </button>
          )}
        </ControlBar>
        {upload.error && <div className="text-xs text-danger">Upload refused: {upload.error.message}</div>}
        {current && (
          <div className="text-xs text-text-muted font-mono break-all">sha256 {current.sha256}</div>
        )}
        {showSource && (
          <pre className="text-xs bg-background border border-border rounded p-3 overflow-auto max-h-80">
            {sourceQ.data?.source ?? "Loading…"}
          </pre>
        )}
      </Card>

      <Card className="p-4 space-y-3">
        <ControlBar className="mb-0">
          <ToggleChip active={mode === "backtest"} onClick={() => setMode("backtest")}>Backtest</ToggleChip>
          <ToggleChip active={mode === "walkforward"} onClick={() => setMode("walkforward")}>Walk-forward</ToggleChip>
          <select aria-label="Index" value={index} onChange={(e) => setIndex(e.target.value as StrategyRunBody["index"])}
                  className="bg-surface border border-border rounded px-2 py-1 text-sm">
            <option value="sp500">S&amp;P 500</option>
            <option value="ndx">Nasdaq 100</option>
            <option value="dow">Dow 30</option>
          </select>
          <select aria-label="Rebalance" value={rebalance}
                  onChange={(e) => setRebalance(e.target.value as StrategyRunBody["rebalance"])}
                  className="bg-surface border border-border rounded px-2 py-1 text-sm">
            <option value="W">Weekly</option>
            <option value="M">Monthly</option>
            <option value="Q">Quarterly</option>
          </select>
          <label className="text-xs text-text-secondary">Years
            <input type="number" min={1} max={25} value={years} onChange={(e) => setYears(Number(e.target.value))}
                   className="ml-1 w-14 bg-surface border border-border rounded px-1 py-0.5 text-sm" />
          </label>
          <label className="text-xs text-text-secondary">Cost (bps)
            <input type="number" min={0} max={500} value={costBps} onChange={(e) => setCostBps(Number(e.target.value))}
                   className="ml-1 w-16 bg-surface border border-border rounded px-1 py-0.5 text-sm" />
          </label>
          {mode === "walkforward" && (
            <>
              <label className="text-xs text-text-secondary">Train (y)
                <input type="number" min={1} max={10} value={trainYears} onChange={(e) => setTrainYears(Number(e.target.value))}
                       className="ml-1 w-12 bg-surface border border-border rounded px-1 py-0.5 text-sm" />
              </label>
              <label className="text-xs text-text-secondary">Test (y)
                <input type="number" min={1} max={5} value={testYears} onChange={(e) => setTestYears(Number(e.target.value))}
                       className="ml-1 w-12 bg-surface border border-border rounded px-1 py-0.5 text-sm" />
              </label>
            </>
          )}
        </ControlBar>
        <div className="grid sm:grid-cols-2 gap-3">
          <label className="text-xs text-text-secondary">Parameters (JSON, read as ctx.params)
            <input value={paramsText} onChange={(e) => setParamsText(e.target.value)} placeholder='{"top_n": 50}'
                   className="mt-1 w-full bg-surface border border-border rounded px-2 py-1 text-sm font-mono" />
          </label>
          {mode === "walkforward" && (
            <label className="text-xs text-text-secondary">Grid (JSON, each key a list of values)
              <input value={gridText} onChange={(e) => setGridText(e.target.value)}
                     className="mt-1 w-full bg-surface border border-border rounded px-2 py-1 text-sm font-mono" />
            </label>
          )}
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => run.mutate()}
            disabled={run.isPending || !list || !list.sandbox.supported}
            className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
              run.isPending
                ? "border-border bg-surface-alt text-text-muted cursor-wait"
                : "border-accent/40 bg-accent text-white hover:bg-accent-light disabled:opacity-50"
            }`}
          >
            {run.isPending ? "Running…" : "🔴 Run Analysis"}
          </button>
          <span className="text-xs text-text-muted">
            {mode === "walkforward"
              ? "Picks the grid point with the best in-sample Sharpe per fold; only test windows are shown."
              : "Point-in-time members on each rebalance date; reads stored data only."}
          </span>
        </div>
        {run.error && <pre className="text-xs text-danger whitespace-pre-wrap">{run.error.message}</pre>}
      </Card>

      {res && (
        <>
          <KpiStrip cols={6}>
            <KpiTile label="CAGR" value={pct(res.metrics.cagr)} tone={(res.metrics.cagr ?? 0) >= 0 ? "up" : "down"} />
            <KpiTile label="Sharpe (rf 0)" value={num(res.metrics.sharpe)} />
            <KpiTile label="Max drawdown" value={pct(res.metrics.maxDrawdown)} tone="down" />
            <KpiTile label="Volatility" value={pct(res.metrics.vol)} />
            <KpiTile label="Turnover / year" value={pct(res.metrics.annualTurnover, 0)} sub="one-way" />
            <KpiTile label="Costs" value={pct(res.metrics.totalCost, 2)} sub={`${res.metrics.rebalances} rebalances`} />
          </KpiStrip>

          <Card className="p-4">
            <h3 className="text-sm font-semibold mb-2">
              {res.outOfSampleOnly ? "Out-of-sample equity (test windows only)" : "Equity"}
            </h3>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={curve}>
                <CartesianGrid stroke={pal.grid} strokeDasharray="3 3" />
                <XAxis dataKey="date" stroke={pal.axis} tick={{ fontSize: 11 }} minTickGap={40} />
                <YAxis stroke={pal.axis} tick={{ fontSize: 11 }} domain={["auto", "auto"]} />
                <Tooltip {...tooltipStyle} />
                <Line type="monotone" dataKey="equity" stroke="rgb(var(--primary))" dot={false} />
              </LineChart>
            </ResponsiveContainer>
            <h3 className="text-sm font-semibold mt-4 mb-2">Drawdown</h3>
            <ResponsiveContainer width="100%" height={140}>
              <AreaChart data={curve}>
                <CartesianGrid stroke={pal.grid} strokeDasharray="3 3" />
                <XAxis dataKey="date" stroke={pal.axis} tick={{ fontSize: 11 }} minTickGap={40} />
                <YAxis stroke={pal.axis} tick={{ fontSize: 11 }} tickFormatter={(v) => pct(v, 0)} />
                <Tooltip {...tooltipStyle} formatter={(v) => pct(Number(v))} />
                <Area type="monotone" dataKey="drawdown" stroke="rgb(var(--danger))" fill="rgb(var(--danger))"
                      fillOpacity={0.2} />
              </AreaChart>
            </ResponsiveContainer>
          </Card>

          {res.folds && (
            <Card className="p-4 overflow-x-auto">
              <h3 className="text-sm font-semibold mb-2">Folds</h3>
              <table className="w-full text-xs">
                <thead className="text-text-secondary text-left">
                  <tr><th>Train</th><th>Test</th><th>Chosen parameters</th><th>Test CAGR</th><th>Test Sharpe</th><th>Test max DD</th></tr>
                </thead>
                <tbody className="font-mono">
                  {res.folds.map((f) => (
                    <tr key={f.testStart} className="border-t border-border">
                      <td>{f.trainStart} → {f.trainEnd}</td>
                      <td>{f.testStart} → {f.testEnd}</td>
                      <td>{JSON.stringify(f.params)}</td>
                      <td>{pct(f.testMetrics.cagr)}</td>
                      <td>{num(f.testMetrics.sharpe)}</td>
                      <td>{pct(f.testMetrics.maxDrawdown)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}

          <Card className="p-4 text-xs text-text-secondary space-y-1">
            <h3 className="text-sm font-semibold text-text-primary mb-1">Reproduce this run</h3>
            <div className="font-mono break-all">{res.strategy.name} · sha256 {res.strategy.sha256}</div>
            <div>
              Data: prices to {String(res.snapshot.priceMaxDate)}, {Number(res.snapshot.priceRows).toLocaleString()} bars
              of {String(res.snapshot.symbolsWithPrices)}/{String(res.snapshot.symbols)} members,{" "}
              {String(res.snapshot.membershipRows)} membership rows, filings to {String(res.snapshot.fundamentalMaxFiled)}.
            </div>
            <div>
              Ran in {res.seconds} s
              {res.sandbox.peakMemoryMB != null && <>, sandbox peak {String(res.sandbox.peakMemoryMB)} MB</>}
              {res.externalRequestsDuringRun != null && <>, {res.externalRequestsDuringRun} external requests by the backend</>}.
            </div>
            {res.positionsWithoutExitPrice > 0 && (
              <div>
                {res.positionsWithoutExitPrice} held position(s) had no stored price at the next rebalance and were
                carried at their last price.
              </div>
            )}
            {res.excluded.length > 0 && (
              <details>
                <summary className="cursor-pointer">
                  {res.excluded.length} member(s) excluded: no stored prices (not filled)
                </summary>
                <ul className="mt-1 columns-2 sm:columns-3 font-mono">
                  {res.excluded.map((e) => (
                    <li key={e.symbol} title={e.reason}>{e.symbol} · from {e.firstDate}</li>
                  ))}
                </ul>
              </details>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
