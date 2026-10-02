"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from "recharts";
import type { AnalystData } from "@/lib/types";
import { fmtNum, fmtPct, fmtPctFromFraction, fmtPrice, fmtLarge, currencySymbol } from "@/lib/format";
import { Card, chartPalette, chartTooltipStyle } from "@/components/ui";
import { useTheme } from "@/components/ThemeProvider";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function NoData({ label = "No analyst data" }: { label?: string }) {
  return <p className="text-sm text-text-muted py-2">{label}</p>;
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">
      {children}
    </h3>
  );
}

// Map 1-5 recommendation scale to label
function recLabel(mean: number | null): string {
  if (mean === null) return "—";
  if (mean <= 1.5) return "Strong Buy";
  if (mean <= 2.5) return "Buy";
  if (mean <= 3.5) return "Hold";
  if (mean <= 4.5) return "Sell";
  return "Strong Sell";
}

function recColor(mean: number | null): string {
  if (mean === null) return "text-text-muted";
  if (mean <= 1.5) return "text-green-500";
  if (mean <= 2.5) return "text-emerald-400";
  if (mean <= 3.5) return "text-yellow-400";
  if (mean <= 4.5) return "text-orange-400";
  return "text-red-500";
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. Price Target Band
// ─────────────────────────────────────────────────────────────────────────────

function PriceTargetSection({
  priceTarget,
  price,
  sym,
}: {
  priceTarget: AnalystData["priceTarget"];
  price: number | null;
  sym: string;
}) {
  const { lowPrice, meanPrice, highPrice, medianPrice, numberOfAnalysts, upsidePct } = priceTarget;

  const hasData =
    lowPrice !== null || meanPrice !== null || highPrice !== null;

  if (!hasData) {
    return (
      <div>
        <SectionTitle>Price Target</SectionTitle>
        <NoData />
      </div>
    );
  }

  // Build a normalised 0-100 band for the inline bar
  const lo = lowPrice ?? 0;
  const hi = highPrice ?? 0;
  const span = hi - lo;

  function pct(v: number | null): number {
    if (v === null || span === 0) return 50;
    return Math.max(0, Math.min(100, ((v - lo) / span) * 100));
  }

  const meanPct = pct(meanPrice);
  const currentPct = pct(price);
  const medianPct = pct(medianPrice);

  const upsidePositive = (upsidePct ?? 0) >= 0;

  return (
    <div>
      <SectionTitle>Price Target ({numberOfAnalysts ?? "?"} Analysts)</SectionTitle>
      {/* KPI row */}
      <div className="flex flex-wrap gap-4 mb-4">
        <div className="text-center">
          <p className="text-xs text-text-muted">Low</p>
          <p className="text-sm font-semibold">{fmtPrice(lowPrice, sym)}</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-text-muted">Median</p>
          <p className="text-sm font-semibold">{fmtPrice(medianPrice, sym)}</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-text-muted">Mean</p>
          <p className="text-sm font-semibold">{fmtPrice(meanPrice, sym)}</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-text-muted">High</p>
          <p className="text-sm font-semibold">{fmtPrice(highPrice, sym)}</p>
        </div>
        <div className="text-center" data-prov="analyst.priceTarget.upsidePct">
          <p className="text-xs text-text-muted">Upside</p>
          <p
            className={`text-sm font-bold ${
              upsidePositive ? "text-green-500" : "text-red-500"
            }`}
          >
            {/* upsidePct is a fraction (0.12 = +12%) */}
            {upsidePct !== null ? `${upsidePct >= 0 ? "+" : ""}${fmtNum(upsidePct * 100)}%` : "—"}
          </p>
        </div>
        {price !== null && (
          <div className="text-center" data-prov="analyst.price">
            <p className="text-xs text-text-muted">Current</p>
            <p className="text-sm font-semibold">{fmtPrice(price, sym)}</p>
          </div>
        )}
      </div>

      {/* Inline band */}
      {span > 0 && (
        <div className="relative h-6 mt-2">
          {/* Track */}
          <div className="absolute top-2 left-0 right-0 h-2 rounded-full bg-surface-2" />
          {/* Mean marker */}
          <div
            className="absolute top-0.5 w-0.5 h-5 bg-blue-400 rounded"
            style={{ left: `${meanPct}%` }}
            title={`Mean: ${fmtPrice(meanPrice, sym)}`}
          />
          {/* Median marker */}
          <div
            className="absolute top-0.5 w-0.5 h-5 bg-purple-400 rounded opacity-70"
            style={{ left: `${medianPct}%` }}
            title={`Median: ${fmtPrice(medianPrice, sym)}`}
          />
          {/* Current price marker */}
          {price !== null && (
            <div
              className="absolute -top-0.5 w-2 h-7 bg-yellow-400 rounded"
              style={{ left: `${currentPct}%`, transform: "translateX(-50%)" }}
              title={`Current: ${fmtPrice(price, sym)}`}
            />
          )}
          {/* Labels */}
          <div className="absolute -bottom-5 left-0 text-xs text-text-muted">
            {fmtPrice(lowPrice, sym)}
          </div>
          <div className="absolute -bottom-5 right-0 text-xs text-text-muted">
            {fmtPrice(highPrice, sym)}
          </div>
        </div>
      )}
      <div className="mt-8 flex gap-4 text-xs text-text-muted">
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 bg-blue-400 rounded" /> Mean
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 bg-purple-400 rounded opacity-70" /> Median
        </span>
        {price !== null && (
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 bg-yellow-400 rounded" /> Current
          </span>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. Consensus Rating
// ─────────────────────────────────────────────────────────────────────────────

const CONSENSUS_COLORS: Record<string, string> = {
  strongBuy: "#16a34a",
  buy: "#4ade80",
  hold: "#ca8a04",
  sell: "#f97316",
  strongSell: "#dc2626",
};

const CONSENSUS_LABELS: Record<string, string> = {
  strongBuy: "Strong Buy",
  buy: "Buy",
  hold: "Hold",
  sell: "Sell",
  strongSell: "Strong Sell",
};

function ConsensusSection({ consensus }: { consensus: AnalystData["consensus"] }) {
  const { recommendationMean, recommendationKey, history } = consensus;
  const { theme } = useTheme();
  const pal = chartPalette(theme);

  const hasMean = recommendationMean !== null;
  const hasHistory = Array.isArray(history) && history.length > 0;

  if (!hasMean && !hasHistory) {
    return (
      <div>
        <SectionTitle>Analyst Consensus</SectionTitle>
        <NoData />
      </div>
    );
  }

  // Most-recent-first for display; take up to 8 periods
  const sortedHistory = hasHistory
    ? [...history].reverse().slice(0, 8)
    : [];

  const barData = sortedHistory.map((h) => ({
    period: h.period,
    "Strong Buy": h.strongBuy,
    Buy: h.buy,
    Hold: h.hold,
    Sell: h.sell,
    "Strong Sell": h.strongSell,
  }));

  return (
    <div>
      <SectionTitle>Analyst Consensus</SectionTitle>
      {/* Current rating KPI */}
      {hasMean && (
        <div className="flex items-baseline gap-3 mb-4">
          <span className={`text-2xl font-bold ${recColor(recommendationMean)}`}>
            {recLabel(recommendationMean)}
          </span>
          {recommendationKey && (
            <span className="text-sm text-text-muted capitalize">
              ({recommendationKey.replace(/_/g, " ")})
            </span>
          )}
          <span className="ml-auto text-sm text-text-muted">
            Mean: {fmtNum(recommendationMean)} / 5
          </span>
        </div>
      )}

      {/* Stacked bar history */}
      {hasHistory ? (
        <div className="h-52" data-prov="analyst.consensus.history">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData} layout="vertical" margin={{ left: 8, right: 8 }}>
              <CartesianGrid stroke={pal.grid} strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fill: pal.axis, fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="period"
                tick={{ fill: pal.axis, fontSize: 11 }}
                width={68}
              />
              <Tooltip {...chartTooltipStyle(theme)} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {(["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"] as const).map((key) => (
                <Bar
                  key={key}
                  dataKey={key}
                  stackId="consensus"
                  fill={
                    key === "Strong Buy"
                      ? CONSENSUS_COLORS.strongBuy
                      : key === "Buy"
                      ? CONSENSUS_COLORS.buy
                      : key === "Hold"
                      ? CONSENSUS_COLORS.hold
                      : key === "Sell"
                      ? CONSENSUS_COLORS.sell
                      : CONSENSUS_COLORS.strongSell
                  }
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        !hasMean && <NoData label="No consensus history" />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. Earnings Surprise History
// ─────────────────────────────────────────────────────────────────────────────

function EarningsSurprisesSection({
  surprises,
  sym,
}: {
  surprises: AnalystData["earningsSurprises"];
  sym: string;
}) {
  const { theme } = useTheme();
  const pal = chartPalette(theme);

  if (!Array.isArray(surprises) || surprises.length === 0) {
    return (
      <div>
        <SectionTitle>Earnings Surprises</SectionTitle>
        <NoData />
      </div>
    );
  }

  const recent = [...surprises].slice(-8).reverse();

  // Quarters without a reported surprise are left out rather than drawn as 0%.
  const barData = recent.flatMap((s) =>
    s.surprisePct == null ? [] : [{ date: s.date, surprise: s.surprisePct }],
  );

  return (
    <div>
      <SectionTitle>Earnings Surprises (last {recent.length} quarters)</SectionTitle>
      <div className="h-40 mb-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={barData} margin={{ left: 0, right: 0 }}>
            <CartesianGrid stroke={pal.grid} strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fill: pal.axis, fontSize: 10 }} />
            <YAxis
              tick={{ fill: pal.axis, fontSize: 10 }}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip
              {...chartTooltipStyle(theme)}
              formatter={(v: number) => [`${fmtNum(v)}%`, "Surprise"]}
            />
            <ReferenceLine y={0} stroke={pal.axis} />
            <Bar dataKey="surprise" name="Surprise %">
              {barData.map((entry, i) => (
                <Cell
                  key={i}
                  fill={entry.surprise >= 0 ? "#16a34a" : "#dc2626"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Compact table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-text-muted border-b border-border">
              <th className="text-left py-1 pr-3">Date</th>
              <th className="text-right py-1 pr-3">Estimate</th>
              <th className="text-right py-1 pr-3">Actual</th>
              <th className="text-right py-1">Surprise</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((s, i) => {
              const pos = (s.surprisePct ?? 0) >= 0;
              return (
                <tr key={i} className="border-b border-border/40 hover:bg-surface-1/50" data-prov-ctx={s.date}>
                  <td className="py-1 pr-3 text-text-secondary">{s.date}</td>
                  <td className="text-right py-1 pr-3">{fmtPrice(s.epsEstimate, sym)}</td>
                  <td className="text-right py-1 pr-3">{fmtPrice(s.epsActual, sym)}</td>
                  <td className={`text-right py-1 font-medium ${pos ? "text-green-500" : "text-red-500"}`}>
                    {s.surprisePct !== null
                      ? `${pos ? "+" : ""}${fmtNum(s.surprisePct)}%`
                      : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. Forward Estimates Table
// ─────────────────────────────────────────────────────────────────────────────

/** Yahoo estimate period codes -> readable labels. */
const ESTIMATE_PERIODS: Record<string, string> = {
  "0q": "Current quarter",
  "+1q": "Next quarter",
  "0y": "Current year",
  "+1y": "Next year",
};

/** Compact currency, e.g. 113624521680 -> "$113.6B". */
function fmtMoneyCompact(v: number, sym: string): string {
  return `${v < 0 ? "-" : ""}${sym}${fmtLarge(Math.abs(v))}`;
}

/**
 * Format one estimate leaf by what it is, not by how it arrived: analyst counts are
 * integers, growth is a fraction shown as %, revenue is compact currency, EPS is
 * currency with 2 decimals. `path` is the key path, e.g. ["revenueEstimate","0y","avg"].
 */
function fmtEstimateNumber(val: number, path: string[], sym: string): string {
  const leaf = path[path.length - 1] ?? "";
  const section = (path[0] ?? "").toLowerCase();
  if (leaf === "numberOfAnalysts") return String(Math.round(val));
  // "growth" inside an estimate period, and top-level revenueGrowth / earningsGrowth / ... are fractions.
  if (leaf === "growth" || /Growth$/.test(leaf)) return fmtPctFromFraction(val, 1);
  if (leaf === "forwardEps") return fmtPrice(val, sym);
  if (path.length > 1 && section.includes("revenue")) return fmtMoneyCompact(val, sym);
  if (path.length > 1 && (section.includes("earnings") || section.includes("eps"))) return fmtPrice(val, sym);
  return fmtNum(val);
}

function renderEstimateValue(val: unknown, sym: string, path: string[] = [], depth = 0): React.ReactNode {
  if (val === null || val === undefined) return <span className="text-text-muted">—</span>;

  if (typeof val === "number") {
    return <span>{fmtEstimateNumber(val, path, sym)}</span>;
  }

  if (typeof val === "string" || typeof val === "boolean") {
    return <span>{String(val)}</span>;
  }

  if (typeof val === "object" && !Array.isArray(val) && depth < 2) {
    const entries = Object.entries(val as Record<string, unknown>).filter(
      ([, v]) => v !== null && v !== undefined
    );
    if (entries.length === 0) return <span className="text-text-muted">—</span>;
    return (
      <table className="text-xs w-full">
        <tbody>
          {entries.map(([k, v]) => (
            <tr key={k} className="border-b border-border/30">
              <td className="py-0.5 pr-3 text-text-muted capitalize">
                {ESTIMATE_PERIODS[k] ?? k.replace(/([A-Z])/g, " $1").trim()}
              </td>
              <td className="py-0.5 text-right">{renderEstimateValue(v, sym, [...path, k], depth + 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  if (Array.isArray(val)) {
    return <span className="text-text-muted text-xs">[array]</span>;
  }

  return <span>{String(val)}</span>;
}

function EstimatesSection({ estimates, sym }: { estimates: AnalystData["estimates"]; sym: string }) {
  if (
    !estimates ||
    typeof estimates !== "object" ||
    Object.keys(estimates).length === 0
  ) {
    return (
      <div>
        <SectionTitle>Forward Estimates</SectionTitle>
        <NoData />
      </div>
    );
  }

  const entries = Object.entries(estimates);

  // Separate scalar fields from period-nested dicts
  const scalars = entries.filter(([, v]) => typeof v !== "object" || v === null);
  const nested = entries.filter(([, v]) => v !== null && typeof v === "object" && !Array.isArray(v));

  return (
    <div>
      <SectionTitle>Forward Estimates</SectionTitle>
      {scalars.length > 0 && (
        <div className="overflow-x-auto mb-4">
          <table className="w-full text-xs">
            <tbody>
              {scalars.map(([k, v]) => (
                <tr key={k} className="border-b border-border/40">
                  <td className="py-1 pr-3 text-text-muted capitalize">
                    {k.replace(/([A-Z])/g, " $1").trim()}
                  </td>
                  <td className="text-right py-1">{renderEstimateValue(v, sym, [k])}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {nested.map(([k, v]) => (
        <div key={k} className="mb-3">
          <p className="text-xs font-semibold text-text-secondary capitalize mb-1">
            {k.replace(/([A-Z])/g, " $1").trim()}
          </p>
          {renderEstimateValue(v, sym, [k])}
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. Growth Estimates
// ─────────────────────────────────────────────────────────────────────────────

function GrowthEstimatesSection({
  growthEstimates,
}: {
  growthEstimates: AnalystData["growthEstimates"];
}) {
  if (
    !growthEstimates ||
    typeof growthEstimates !== "object" ||
    Object.keys(growthEstimates).length === 0
  ) {
    return (
      <div>
        <SectionTitle>Growth Estimates</SectionTitle>
        <NoData />
      </div>
    );
  }

  const periods = Object.keys(growthEstimates);
  // Collect all column keys across all periods
  const colSet = new Set<string>();
  periods.forEach((p) => {
    const row = growthEstimates[p];
    if (row && typeof row === "object") {
      Object.keys(row).forEach((k) => colSet.add(k));
    }
  });
  const cols = Array.from(colSet);

  if (periods.length === 0 || cols.length === 0) {
    return (
      <div>
        <SectionTitle>Growth Estimates</SectionTitle>
        <NoData />
      </div>
    );
  }

  return (
    <div>
      <SectionTitle>Growth Estimates</SectionTitle>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-text-muted border-b border-border">
              <th className="text-left py-1 pr-3">Period</th>
              {cols.map((c) => (
                <th key={c} className="text-right py-1 pr-3 capitalize">
                  {c.replace(/([A-Z])/g, " $1").trim()}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {periods.map((p) => {
              const row = growthEstimates[p] ?? {};
              return (
                <tr key={p} className="border-b border-border/40 hover:bg-surface-1/50">
                  <td className="py-1 pr-3 text-text-secondary font-medium">{p}</td>
                  {cols.map((c) => {
                    const val = row[c];
                    const isNum = typeof val === "number";
                    const pos = isNum && val >= 0;
                    return (
                      <td
                        key={c}
                        className={`text-right py-1 pr-3 ${
                          isNum
                            ? pos
                              ? "text-green-500"
                              : "text-red-500"
                            : "text-text-muted"
                        }`}
                      >
                        {isNum ? fmtPct(val * 100) : "—"}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main export
// ─────────────────────────────────────────────────────────────────────────────

export function AnalystPanel({ analyst }: { analyst: AnalystData }) {
  const sym = currencySymbol(analyst.currency);

  return (
    <div className="space-y-6">
      {/* Top KPI: price target band */}
      <Card className="p-4" data-prov="analyst.priceTarget">
        <PriceTargetSection
          priceTarget={analyst.priceTarget}
          price={analyst.price}
          sym={sym}
        />
      </Card>

      {/* Consensus rating */}
      <Card className="p-4" data-prov="analyst.consensus">
        <ConsensusSection consensus={analyst.consensus} />
      </Card>

      {/* Earnings surprises */}
      <Card className="p-4" data-prov="analyst.earningsSurprises">
        <EarningsSurprisesSection surprises={analyst.earningsSurprises} sym={sym} />
      </Card>

      {/* Forward estimates */}
      <Card className="p-4" data-prov="analyst.estimates">
        <EstimatesSection estimates={analyst.estimates} sym={sym} />
      </Card>

      {/* Growth estimates */}
      <Card className="p-4" data-prov="analyst.growthEstimates">
        <GrowthEstimatesSection growthEstimates={analyst.growthEstimates} />
      </Card>

      {/* Footer */}
      <p className="text-xs text-text-muted text-right">
        Analyst data as of {analyst.asOf}
      </p>
    </div>
  );
}
