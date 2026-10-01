"use client";

import { Card } from "@/components/ui";
import {
  fmtNum,
  fmtPct,
  fmtPctFromFraction,
  fmtPrice,
  fmtLarge,
  currencySymbol,
} from "@/lib/format";
import type { ValuationKpis, WaccInfo, Fundamentals } from "@/lib/types";
import { NaReason } from "@/components/markets/NaReason";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface Props {
  kpis: ValuationKpis;
  wacc: WaccInfo;
  fundamentals: Fundamentals;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const DASH = "—";

function nil(v: number | null | undefined): boolean {
  return v === null || v === undefined || Number.isNaN(v as number);
}

/** Format a decimal percentage field (e.g. 0.005 → "0.50%"). */
function fmtDecPct(v: number | null | undefined, digits = 2): string {
  if (nil(v)) return DASH;
  return fmtPct((v as number) * 100, digits);
}

/** Format a WACC-style decimal field already in fraction form. */
function fmtWacc(v: number | null | undefined): string {
  return fmtDecPct(v, 2);
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** A single KPI tile in the top strip. */
function KpiTile({ label, value, prov, hint }: { label: string; value: string; prov?: string; hint?: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-lg bg-surface-alt px-3 py-2.5 min-w-[6rem]" data-prov={prov} data-prov-ctx={label} title={hint}>
      <span className="text-xs text-text-muted truncate">{label}</span>
      <span className="font-mono text-xs lg:text-sm text-text-primary truncate" title={value}>{value}</span>
    </div>
  );
}

/** A two-column label/value row used inside extended tables. */
function Row({ label, value, valueClass, prov, naReason }: { label: string; value: string; valueClass?: string; prov?: string; naReason?: string }) {
  return (
    <>
      <dt className="text-text-secondary text-sm" data-prov={prov} data-prov-ctx={label}>{label}</dt>
      <dd className={`text-right font-mono text-sm ${valueClass ?? ""}`} data-prov={prov} data-prov-ctx={label}>
        {naReason ? <NaReason reason={naReason} /> : value}
      </dd>
    </>
  );
}

/**
 * Piotroski bands. The classic cut-offs are for the 9-point score: >= 7 strong,
 * 4-6 neutral, < 4 weak. When fewer tests are computable (e.g. 7 for banks) the cut-offs
 * are scaled by the same fractions of maxScore: strong >= ceil(7/9 x max), weak < ceil(4/9 x max).
 */
function piotroskiBands(maxScore: number): { strongMin: number; weakBelow: number } {
  return {
    strongMin: Math.ceil((7 * maxScore) / 9 - 1e-9),
    weakBelow: Math.ceil((4 * maxScore) / 9 - 1e-9),
  };
}

/** Piotroski score badge with traffic-light color, bands scaled to maxScore. */
function PiotroskiBadge({ score, maxScore }: { score: number | null; maxScore: number | null }) {
  if (nil(score) || nil(maxScore)) {
    return <span className="px-2 py-0.5 rounded-md text-xs font-semibold bg-surface-alt text-text-secondary">{DASH}</span>;
  }
  const s = score as number;
  const { strongMin, weakBelow } = piotroskiBands(maxScore as number);
  const cls =
    s >= strongMin ? "bg-success/20 text-success" :
    s >= weakBelow ? "bg-warning/20 text-warning" :
    "bg-danger/20 text-danger";
  return (
    <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${cls}`}>
      {s} / {maxScore}
    </span>
  );
}

/**
 * Beneish M-Score badge. Red if mScore > -1.78 (possible manipulation), green only for a
 * real score below it. A missing score (with its backend note) is a neutral n/a, never green.
 */
function BeneishBadge({ mScore, note }: { mScore: number | null; note?: string }) {
  if (nil(mScore)) {
    return <NaReason reason={note} className="px-2 py-0.5 rounded-md text-xs font-semibold bg-surface-alt" />;
  }
  const manipulated = (mScore as number) > -1.78;
  const cls = manipulated ? "bg-danger/20 text-danger" : "bg-success/20 text-success";
  return (
    <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${cls}`}>
      {`${(mScore as number).toFixed(2)}${manipulated ? " ⚠ Possible manip." : " ✓ Low risk"}`}
    </span>
  );
}

/**
 * Ohlson O-Score badge showing probability of default. Colour bands: < 5 % green (low),
 * 5-50 % neutral (no verdict: Ohlson probabilities are not calibrated for modern large caps,
 * so a mid value is not "good" and not an alarm), > 50 % red (the classic O-score cut-off).
 */
function OhlsonBadge({ oScore, probDefault }: { oScore: number | null; probDefault: number | null }) {
  if (nil(oScore) && nil(probDefault)) {
    return <span className="px-2 py-0.5 rounded-md text-xs font-semibold bg-surface-alt text-text-secondary">{DASH}</span>;
  }
  const prob = nil(probDefault) ? null : (probDefault as number) * 100;
  const cls =
    prob === null ? "bg-surface-alt text-text-secondary" :
    prob > 50 ? "bg-danger/20 text-danger" :
    prob < 5 ? "bg-success/20 text-success" :
    "bg-surface-alt text-text-secondary";
  const scoreStr = nil(oScore) ? "" : `O=${(oScore as number).toFixed(2)} · `;
  const probStr = prob !== null ? `P(default)=${prob.toFixed(1)}%` : "";
  return (
    <span
      className={`px-2 py-0.5 rounded-md text-xs font-semibold ${cls}`}
      title="Ohlson probabilities are uncalibrated for modern large caps; read as a relative distress rank, not a literal default probability."
    >
      {scoreStr}{probStr || DASH}
    </span>
  );
}

/** Legend line under the Piotroski label, with bands scaled to the score's maximum. */
function piotroskiLegend(maxScore: number | null): string {
  if (nil(maxScore)) return "≥7 Strong · 4–6 Neutral · <4 Weak (of 9)";
  const { strongMin, weakBelow } = piotroskiBands(maxScore as number);
  return `≥${strongMin} Strong · ${weakBelow}–${strongMin - 1} Neutral · <${weakBelow} Weak (of ${maxScore})`;
}

/** Short float color: >20% red, 10-20% orange, else default. */
function shortFloatClass(v: number | null): string {
  if (nil(v)) return "";
  const pct = (v as number) * 100;
  if (pct > 20) return "text-danger";
  if (pct > 10) return "text-warning";
  return "";
}

// ---------------------------------------------------------------------------
// DuPont rows helper
// ---------------------------------------------------------------------------

/**
 * Render labeled values for a DuPont factor object.
 * Keys we surface: netMargin, assetTurnover, equityMultiplier for 3-factor;
 * plus taxBurden, interestBurden, operatingMargin for 5-factor.
 */
const DUPONT_3_LABELS: Record<string, string> = {
  netMargin: "Net Margin",
  assetTurnover: "Asset Turnover",
  equityMultiplier: "Equity Multiplier",
  roe: "ROE",
};

const DUPONT_5_LABELS: Record<string, string> = {
  taxBurden: "Tax Burden",
  interestBurden: "Interest Burden",
  operatingMargin: "EBIT Margin",
  assetTurnover: "Asset Turnover",
  equityMultiplier: "Equity Multiplier",
  roe: "ROE",
};

function formatDupontValue(key: string, v: number | null): string {
  if (nil(v)) return DASH;
  const n = v as number;
  // Margin / burden / multiplier fields — detect by key suffix
  if (key.toLowerCase().includes("margin") || key.toLowerCase().includes("burden")) {
    return fmtPct(n * 100);
  }
  if (key === "roe") return fmtPct(n * 100);
  // Turnover and multiplier — plain ratio
  return fmtNum(n, 2) + "×";
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ValuationKpiPanel({ kpis, wacc, fundamentals }: Props) {
  const sym = currencySymbol(kpis.currency);

  // ── Null KPIs the backend explained (e.g. ADR with no FX rate) ────────────
  const naReasonOf = (key: string, v: number | null | undefined): string | undefined =>
    nil(v) ? kpis.unavailable?.[key] : undefined;
  const unavailableNotes = (
    [
      ["EV / FCF", "evToFcf", kpis.evToFcf],
      ["FCF Yield", "fcfYield", kpis.fcfYield],
      ["Book Value / Sh.", "bookValue", kpis.bookValue],
    ] as [string, string, number | null][]
  ).flatMap(([label, key, v]) => {
    const r = naReasonOf(key, v);
    return r ? [[label, r] as [string, string]] : [];
  });

  // ── 52-week range string ──────────────────────────────────────────────────
  const rangeStr =
    nil(kpis.fiftyTwoWeekLow) && nil(kpis.fiftyTwoWeekHigh)
      ? DASH
      : `${nil(kpis.fiftyTwoWeekLow) ? DASH : fmtPrice(kpis.fiftyTwoWeekLow, sym)} – ${nil(kpis.fiftyTwoWeekHigh) ? DASH : fmtPrice(kpis.fiftyTwoWeekHigh, sym)}`;

  // ── KPI strip tiles ───────────────────────────────────────────────────────
  const kpiTiles: { label: string; value: string; prov: string; hint?: string }[] = [
    { label: "Price", value: fmtPrice(kpis.price, sym), prov: "kpis.price" },
    { label: "Market Cap", value: nil(kpis.marketCap) ? DASH : `${sym}${fmtLarge(kpis.marketCap)}`, prov: "kpis.marketCap" },
    { label: "P/E (TTM)", value: fmtNum(kpis.trailingPE), prov: "kpis.trailingPE" },
    { label: "Forward P/E", value: fmtNum(kpis.forwardPE), prov: "kpis.forwardPE" },
    { label: "EPS (TTM)", value: nil(kpis.trailingEps) ? DASH : `${sym}${fmtNum(kpis.trailingEps)}`, prov: "kpis.trailingEps" },
    { label: "Fwd EPS", value: nil(kpis.forwardEps) ? DASH : `${sym}${fmtNum(kpis.forwardEps)}`, prov: "kpis.forwardEps" },
    { label: "Div. Yield", value: nil(kpis.dividendYield) ? DASH : fmtPct(kpis.dividendYield), prov: "kpis.dividendYield" },
    { label: "52W Range", value: rangeStr, prov: "kpis.fiftyTwoWeekLow" },
    { label: "Beta (5y mo.)", value: fmtNum(kpis.beta), prov: "kpis.beta", hint: "Yahoo beta: 5 years of monthly returns vs the S&P 500. The Ratios tab and Overview use the selected period of daily returns vs the ticker's local index." },
  ];

  // ── Short float color ─────────────────────────────────────────────────────
  const sfClass = shortFloatClass(kpis.shortPercentOfFloat);

  // ── ROIC ─────────────────────────────────────────────────────────────────
  const roicVal = fundamentals.roic?.roic ?? null;

  // ── CCC ──────────────────────────────────────────────────────────────────
  const ccc = fundamentals.cashConversionCycle?.ccc ?? null;

  // ── Piotroski criteria count ──────────────────────────────────────────────
  const piotroski = fundamentals.piotroski;
  const beneish = fundamentals.beneish;
  const ohlson = fundamentals.ohlson;

  // ── DuPont ───────────────────────────────────────────────────────────────
  const dupont = fundamentals.dupont;

  return (
    <div className="space-y-4">

      {/* ── KPI Strip ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
        {kpiTiles.map((t) => (
          <KpiTile key={t.label} label={t.label} value={t.value} prov={t.prov} hint={t.hint} />
        ))}
      </div>

      {/* ── Sector / Industry ─────────────────────────────────────────────── */}
      {(kpis.sector || kpis.industry) && (
        <div className="flex flex-wrap gap-2 text-xs text-text-secondary">
          {kpis.sector && (
            <span className="px-2 py-0.5 rounded bg-surface-alt" data-prov="kpis.sector">{kpis.sector}</span>
          )}
          {kpis.industry && (
            <span className="px-2 py-0.5 rounded bg-surface-alt" data-prov="kpis.industry">{kpis.industry}</span>
          )}
        </div>
      )}

      {/* ── Extended Fundamentals ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Left column: Valuation/Quality + WACC */}
        <div className="space-y-4">

          {/* Valuation / Quality */}
          <Card>
            <h3 className="text-sm font-semibold text-text-secondary mb-3 uppercase tracking-wide">
              Valuation &amp; Quality
            </h3>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5">
              <Row label="EV / FCF" value={fmtNum(kpis.evToFcf)} prov="kpis.evToFcf" naReason={naReasonOf("evToFcf", kpis.evToFcf)} />
              <Row label="FCF Yield" value={fmtDecPct(kpis.fcfYield)} prov="kpis.fcfYield" naReason={naReasonOf("fcfYield", kpis.fcfYield)} />
              <Row
                label="Short Float %"
                value={nil(kpis.shortPercentOfFloat) ? DASH : fmtDecPct(kpis.shortPercentOfFloat)}
                valueClass={sfClass}
                prov="kpis.shortPercentOfFloat"
              />
              <Row label="Short Ratio" value={fmtNum(kpis.shortRatio)} prov="kpis.shortRatio" />
              <Row
                label="ROIC"
                value={nil(roicVal) ? DASH : fmtPctFromFraction(roicVal)}
                prov="fundamentals.roic.roic"
              />
              <Row label="Book Value / Sh." value={nil(kpis.bookValue) ? DASH : `${sym}${fmtNum(kpis.bookValue)}`} prov="kpis.bookValue" naReason={naReasonOf("bookValue", kpis.bookValue)} />
              <Row
                label="CAPM Required Ret."
                value={fmtDecPct(wacc.costOfEquity)}
                prov="valuation.wacc.costOfEquity"
              />
              <Row
                label="Cash Conv. Cycle"
                value={nil(ccc) ? DASH : `${fmtNum(ccc, 1)} days`}
                prov="fundamentals.cashConversionCycle.ccc"
              />
              <Row
                label="Avg. Volume"
                value={nil(kpis.averageVolume) ? DASH : fmtLarge(kpis.averageVolume)}
                prov="kpis.averageVolume"
              />
            </dl>
            {unavailableNotes.length > 0 && (
              <ul className="mt-3 space-y-0.5 text-xs text-text-muted" data-prov="kpis.unavailable">
                {unavailableNotes.map(([label, reason]) => (
                  <li key={label}>{label}: n/a — {reason}</li>
                ))}
              </ul>
            )}
            <p className="mt-3 text-xs text-text-muted">
              Short data: US-listed only.
            </p>
          </Card>

          {/* WACC Breakdown */}
          <Card>
            <h3 className="text-sm font-semibold text-text-secondary mb-3 uppercase tracking-wide">
              WACC Breakdown
            </h3>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5">
              <Row label="WACC" value={fmtWacc(wacc.wacc)} prov="valuation.wacc.wacc" />
              <Row label="Cost of Equity" value={fmtWacc(wacc.costOfEquity)} prov="valuation.wacc.costOfEquity" />
              <Row label="Cost of Debt" value={fmtWacc(wacc.costOfDebt)} prov="valuation.wacc.costOfDebt" />
              <Row label="Tax Rate" value={fmtWacc(wacc.taxRate)} prov="valuation.wacc.taxRate" />
              <Row label="ERP" value={fmtWacc(wacc.erp)} prov="valuation.wacc.erp" />
              <Row label="Risk-Free" value={fmtWacc(wacc.riskFree)} prov="valuation.wacc.riskFree" />
              <Row label="Beta (2y daily, local index)" value={fmtNum(wacc.beta)} prov="valuation.wacc.beta" />
              <Row
                label="Wt. Equity"
                value={nil(wacc.weightEquity) ? DASH : fmtPct((wacc.weightEquity as number) * 100)}
                prov="valuation.wacc.weightEquity"
              />
              <Row
                label="Wt. Debt"
                value={nil(wacc.weightDebt) ? DASH : fmtPct((wacc.weightDebt as number) * 100)}
                prov="valuation.wacc.weightDebt"
              />
              <Row
                label="Country"
                value={wacc.country || DASH}
                prov="valuation.wacc.country"
              />
            </dl>
          </Card>
        </div>

        {/* Right column: DuPont + Scores */}
        <div className="space-y-4">

          {/* DuPont */}
          <Card>
            <h3 className="text-sm font-semibold text-text-secondary mb-3 uppercase tracking-wide">
              DuPont Decomposition
            </h3>
            {dupont ? (
              <div className="space-y-4">
                {/* 3-Factor */}
                <div>
                  <p className="text-xs font-medium text-text-secondary mb-2">
                    3-Factor (Net Margin × Asset Turnover × Equity Multiplier = ROE)
                  </p>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                    {Object.entries(dupont.threeFactor)
                      .filter(([k]) => k in DUPONT_3_LABELS)
                      .map(([k, v]) => (
                        <Row
                          key={k}
                          label={DUPONT_3_LABELS[k] ?? k}
                          value={formatDupontValue(k, v)}
                          prov={`fundamentals.dupont.threeFactor.${k}`}
                        />
                      ))}
                  </dl>
                  {/* Horizontal waterfall strip */}
                  <DupontWaterfall factors={dupont.threeFactor} labels={DUPONT_3_LABELS} />
                </div>

                <div className="border-t border-border" />

                {/* 5-Factor */}
                <div>
                  <p className="text-xs font-medium text-text-secondary mb-2">
                    5-Factor
                  </p>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                    {Object.entries(dupont.fiveFactor)
                      .filter(([k]) => k in DUPONT_5_LABELS)
                      .map(([k, v]) => (
                        <Row
                          key={k}
                          label={DUPONT_5_LABELS[k] ?? k}
                          value={formatDupontValue(k, v)}
                          prov={`fundamentals.dupont.fiveFactor.${k}`}
                        />
                      ))}
                  </dl>
                </div>
              </div>
            ) : (
              <p className="text-sm text-text-muted">{DASH}</p>
            )}
          </Card>

          {/* Quality Scores */}
          <Card>
            <h3 className="text-sm font-semibold text-text-secondary mb-3 uppercase tracking-wide">
              Quality &amp; Distress Scores
            </h3>
            <div className="space-y-3">

              {/* Piotroski */}
              <div className="flex items-start justify-between gap-2" data-prov="fundamentals.piotroski">
                <div className="min-w-0">
                  <p className="text-sm text-text-secondary">Piotroski F-Score</p>
                  <p className="text-xs text-text-muted mt-0.5">
                    {piotroskiLegend(piotroski?.maxScore ?? null)}
                  </p>
                </div>
                <PiotroskiBadge
                  score={piotroski?.score ?? null}
                  maxScore={piotroski?.maxScore ?? null}
                />
              </div>

              {/* Piotroski criteria detail */}
              {piotroski?.criteria && Object.keys(piotroski.criteria).length > 0 && (
                <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 pl-1">
                  {Object.entries(piotroski.criteria).map(([k, v]) => (
                    <div key={k} className="flex items-center gap-1.5 text-xs" data-prov={`fundamentals.piotroski.criteria.${k}`}>
                      <span
                        className={
                          v === true ? "text-success" :
                          v === false ? "text-danger" :
                          "text-text-muted"
                        }
                      >
                        {v === true ? "✓" : v === false ? "✗" : "—"}
                      </span>
                      <span className="text-text-secondary truncate capitalize">
                        {k.replace(/([A-Z])/g, " $1").trim()}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              <div className="border-t border-border" />

              {/* Beneish */}
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm text-text-secondary">Beneish M-Score</p>
                  <p className="text-xs text-text-muted mt-0.5">
                    &gt;−1.78 = possible earnings manipulation
                  </p>
                </div>
                <BeneishBadge
                  mScore={beneish?.mScore ?? null}
                  note={beneish?.note}
                />
              </div>
              {nil(beneish?.mScore) && beneish?.note && (
                <p className="text-xs text-text-muted" data-prov="fundamentals.beneish">n/a — {beneish.note}</p>
              )}

              <div className="border-t border-border" />

              {/* Ohlson */}
              <div className="flex items-start justify-between gap-2" data-prov="fundamentals.ohlson.oScore">
                <div className="min-w-0">
                  <p className="text-sm text-text-secondary">Ohlson O-Score</p>
                  <p className="text-xs text-text-muted mt-0.5">
                    Probability of bankruptcy within 2 years
                  </p>
                </div>
                <OhlsonBadge
                  oScore={ohlson?.oScore ?? null}
                  probDefault={ohlson?.probDefault ?? null}
                />
              </div>

            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DuPont waterfall strip (bonus visual)
// ---------------------------------------------------------------------------

/**
 * A compact horizontal bar "waterfall" showing the relative magnitude of each
 * factor. We normalise all absolute values to [0, 1] and render coloured
 * segments with a label below.
 */
function DupontWaterfall({
  factors,
  labels,
}: {
  factors: Record<string, number | null>;
  labels: Record<string, string>;
}) {
  const entries = Object.entries(factors).filter(
    ([k, v]) => k in labels && !nil(v) && k !== "roe",
  ) as [string, number][];

  if (!entries.length) return null;

  const absVals = entries.map(([, v]) => Math.abs(v));
  const maxAbs = Math.max(...absVals, 1e-9);

  return (
    <div className="mt-2">
      <div className="flex h-2 rounded overflow-hidden gap-px">
        {entries.map(([k, v], i) => {
          const width = (Math.abs(v) / maxAbs) * 100;
          // Alternate hue palette — accent for positive, muted for multiplier
          const colors = [
            "bg-accent/70",
            "bg-success/60",
            "bg-warning/60",
            "bg-text-secondary/40",
          ];
          return (
            <div
              key={k}
              title={`${labels[k] ?? k}: ${formatDupontValue(k, v)}`}
              className={`h-full ${colors[i % colors.length]} transition-all`}
              style={{ width: `${width}%` }}
            />
          );
        })}
      </div>
      <div className="flex gap-px mt-1">
        {entries.map(([k, v], i) => {
          const width = (Math.abs(v as number) / maxAbs) * 100;
          return (
            <div
              key={k}
              className="overflow-hidden"
              style={{ width: `${width}%` }}
            >
              <span className="text-[9px] text-text-muted truncate block leading-tight">
                {labels[k] ?? k}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
