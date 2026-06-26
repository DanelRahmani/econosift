/**
 * Interpretation guide for financial ratios: what each measures, the
 * favorable / average / caution bands, and the common exceptions where the
 * rule of thumb breaks down (industry, growth stage, accounting quirks).
 *
 * Thresholds are expressed in the *same units the API returns* — margins, ROA,
 * ROE, FCF margin and dividend yield arrive as fractions (0.12 = 12%), so their
 * thresholds are fractional and flagged with `isPct` for display.
 */
export type Tone = "good" | "normal" | "bad";

export interface RatioGuide {
  meaning: string;
  exception?: string;
  /** "high" = higher is better, "low" = lower is better, "band" = a sweet spot. */
  dir: "high" | "low" | "band";
  t1: number;
  t2: number;
  /** Good region for "band" ratios (between t1 and t2). */
  lo?: number;
  hi?: number;
  isPct?: boolean;
  /** Suffix for non-pct ratios (e.g. "×", " days"). */
  suffix?: string;
}

export const RATIO_GUIDE: Record<string, RatioGuide> = {
  // ── Liquidity ──────────────────────────────────────────────────────────
  currentRatio: {
    meaning: "Current assets ÷ current liabilities — can the firm cover its near-term bills?",
    dir: "band", t1: 1, t2: 3, lo: 1.5, hi: 3,
    exception: "Far above 3 can signal idle cash or bloated inventory rather than strength.",
  },
  quickRatio: {
    meaning: "Liquidity excluding inventory — the acid test.",
    dir: "high", t1: 0.7, t2: 1,
    exception: "Retailers run low quick ratios normally because inventory turns fast.",
  },
  cashRatio: {
    meaning: "Cash & equivalents ÷ current liabilities — strictest liquidity measure.",
    dir: "high", t1: 0.2, t2: 0.5,
    exception: "A persistently high cash ratio may mean capital isn't being deployed.",
  },
  operatingCFRatio: {
    meaning: "Operating cash flow ÷ current liabilities — bills covered by real cash.",
    dir: "high", t1: 0.5, t2: 1,
  },

  // ── Leverage ───────────────────────────────────────────────────────────
  debtToEquity: {
    meaning: "Total debt ÷ equity — reliance on borrowed money.",
    dir: "low", t1: 0.5, t2: 1.5,
    exception: "Utilities, banks and capital-intensive firms carry high D/E by nature.",
  },
  debtToAssets: {
    meaning: "Share of assets financed by debt.",
    dir: "low", t1: 0.4, t2: 0.6,
    exception: "Asset-heavy sectors (real estate, telecom) sit higher without distress.",
  },
  interestCoverage: {
    meaning: "EBIT ÷ interest expense — ability to service debt from earnings.",
    dir: "high", t1: 2, t2: 5, suffix: "×",
    exception: "Cyclical firms dip below 2× in troughs yet recover; one year isn't fatal.",
  },
  netDebtEbitda: {
    meaning: "Net debt ÷ EBITDA — years of earnings to repay debt.",
    dir: "low", t1: 2, t2: 4, suffix: "×",
    exception: "Negative when cash exceeds debt (net cash) — that's a strong sign.",
  },

  // ── Efficiency ─────────────────────────────────────────────────────────
  assetTurnover: {
    meaning: "Revenue ÷ assets — sales generated per dollar of assets.",
    dir: "high", t1: 0.5, t2: 1, suffix: "×",
    exception: "Highly industry-specific: retail runs high, utilities/telecom run low.",
  },
  inventoryTurnover: {
    meaning: "How many times inventory is sold and replaced per year.",
    dir: "high", t1: 3, t2: 6, suffix: "×",
    exception: "Luxury and heavy-equipment makers turn inventory slowly by design.",
  },
  receivablesTurnover: {
    meaning: "How quickly the firm collects on credit sales.",
    dir: "high", t1: 4, t2: 8, suffix: "×",
    exception: "Cash businesses show very high turnover; long B2B terms lower it.",
  },
  dso: {
    meaning: "Days sales outstanding — average days to collect payment.",
    dir: "low", t1: 45, t2: 75, suffix: " days",
    exception: "Project/B2B firms with net-60/90 terms run higher without trouble.",
  },

  // ── Profitability (fractions) ──────────────────────────────────────────
  grossMargin: {
    meaning: "Revenue left after the cost of goods sold.",
    dir: "high", t1: 0.2, t2: 0.4, isPct: true,
    exception: "Grocers/distributors operate on thin gross margins by model.",
  },
  operatingMargin: {
    meaning: "Profitability from core operations, before interest & tax.",
    dir: "high", t1: 0.05, t2: 0.15, isPct: true,
  },
  netMargin: {
    meaning: "Bottom-line profit per dollar of revenue.",
    dir: "high", t1: 0.03, t2: 0.1, isPct: true,
    exception: "One-off charges or tax items can distort a single year.",
  },
  ebitdaMargin: {
    meaning: "Cash earnings power before D&A and capital structure.",
    dir: "high", t1: 0.1, t2: 0.2, isPct: true,
  },
  roa: {
    meaning: "Return on assets — profit per dollar of assets.",
    dir: "high", t1: 0.02, t2: 0.05, isPct: true,
  },
  roe: {
    meaning: "Return on equity — profit per dollar of shareholder capital.",
    dir: "high", t1: 0.08, t2: 0.15, isPct: true,
    exception: "High leverage inflates ROE; negative equity makes it meaningless.",
  },
  fcfMargin: {
    meaning: "Free cash flow per dollar of revenue, after capex.",
    dir: "high", t1: 0.03, t2: 0.1, isPct: true,
    exception: "Heavy-investment growth years can show low/negative FCF margin.",
  },

  // ── Valuation multiples (green = cheaper, red = richer) ─────────────────
  peRatio: {
    meaning: "Price ÷ earnings — dollars paid per $1 of profit.",
    dir: "low", t1: 15, t2: 30, suffix: "×",
    exception: "A high P/E can be justified by fast growth; negative P/E = losses.",
  },
  forwardPE: {
    meaning: "P/E on next-year earnings estimates.",
    dir: "low", t1: 15, t2: 30, suffix: "×",
    exception: "Relies on analyst forecasts, which can be optimistic.",
  },
  pbRatio: {
    meaning: "Price ÷ book value — premium over net asset value.",
    dir: "low", t1: 1.5, t2: 4, suffix: "×",
    exception: "Asset-light, high-ROE firms trade at high P/B and deserve to.",
  },
  psRatio: {
    meaning: "Price ÷ sales — useful when earnings are thin or negative.",
    dir: "low", t1: 2, t2: 6, suffix: "×",
    exception: "High-margin software commands higher P/S than low-margin retail.",
  },
  evEbitda: {
    meaning: "Enterprise value ÷ EBITDA — capital-structure-neutral valuation.",
    dir: "low", t1: 10, t2: 16, suffix: "×",
    exception: "Higher growth and higher margins warrant higher multiples.",
  },
  evRevenue: {
    meaning: "Enterprise value ÷ revenue.",
    dir: "low", t1: 3, t2: 8, suffix: "×",
    exception: "Pre-profit, fast-growing firms trade at elevated EV/Revenue.",
  },
  dividendYield: {
    meaning: "Annual dividend ÷ share price.",
    dir: "band", t1: 0.5, t2: 8, lo: 2, hi: 6, isPct: false, suffix: "%",
    exception: "A yield above ~8% often signals the market expects a dividend cut.",
  },
  eps: {
    meaning: "Net income per diluted share.",
    dir: "high", t1: 0, t2: 0.0001,
    exception: "Negative EPS = net loss; share buybacks flatter per-share figures.",
  },
};

function classifyTone(g: RatioGuide, v: number): Tone {
  switch (g.dir) {
    case "high":
      return v >= g.t2 ? "good" : v >= g.t1 ? "normal" : "bad";
    case "low":
      return v <= g.t1 ? "good" : v <= g.t2 ? "normal" : "bad";
    case "band": {
      const lo = g.lo ?? g.t1;
      const hi = g.hi ?? g.t2;
      if (v >= lo && v <= hi) return "good";
      if (v >= g.t1 && v <= g.t2) return "normal";
      return "bad";
    }
  }
}

export function ratioTone(key: string, v: number | null): Tone | null {
  const g = RATIO_GUIDE[key];
  if (!g || v === null || Number.isNaN(v)) return null;
  return classifyTone(g, v);
}

function fmtThreshold(g: RatioGuide, v: number): string {
  if (g.isPct) return `${(v * 100).toFixed(v * 100 < 1 ? 1 : 0)}%`;
  const n = Number.isInteger(v) ? v.toString() : v.toFixed(1);
  return `${n}${g.suffix ?? ""}`;
}

/** Human-readable Good / Average / Caution bands for the guide panel. */
export function ratioRanges(key: string): { good: string; normal: string; bad: string } | null {
  const g = RATIO_GUIDE[key];
  if (!g) return null;
  const f = (v: number) => fmtThreshold(g, v);
  if (g.dir === "high") return { good: `≥ ${f(g.t2)}`, normal: `${f(g.t1)} – ${f(g.t2)}`, bad: `< ${f(g.t1)}` };
  if (g.dir === "low") return { good: `≤ ${f(g.t1)}`, normal: `${f(g.t1)} – ${f(g.t2)}`, bad: `> ${f(g.t2)}` };
  const lo = g.lo ?? g.t1, hi = g.hi ?? g.t2;
  return { good: `${f(lo)} – ${f(hi)}`, normal: `${f(g.t1)} – ${f(lo)} or ${f(hi)} – ${f(g.t2)}`, bad: `< ${f(g.t1)} or > ${f(g.t2)}` };
}

export const TONE_TEXT: Record<Tone, string> = {
  good: "text-success",
  normal: "text-warning",
  bad: "text-danger",
};
export const TONE_DOT: Record<Tone, string> = {
  good: "bg-success",
  normal: "bg-warning",
  bad: "bg-danger",
};

// ──────────────────────────────────────────────────────────────────────────
// Risk / Performance metric guides (Beta, Sharpe, Sortino, Altman Z)
// ──────────────────────────────────────────────────────────────────────────

export interface RiskMetricGuide {
  label: string;
  meaning: string;
  blurb: string;
  format: "num" | "pct";
  /** "high" = higher better, "low" = lower better, "band" = sweet spot. */
  dir: "high" | "low" | "band";
  good: string;
  normal: string;
  bad: string;
  exception?: string;
}

export const RISK_METRIC_GUIDES: Record<string, RiskMetricGuide> = {
  beta: {
    label: "Beta",
    blurb: "Sensitivity to the S&P 500 — 1.0 = moves with market, < 1 = defensive, > 1 = aggressive",
    meaning:
      "Measures a stock's sensitivity to the benchmark (S&P 500). Computed from 2 years of daily log returns. A beta of 1 means the stock moves with the market; below 1 is defensive, above 1 is aggressive.",
    format: "num",
    dir: "band",
    good: "0.7 – 1.3 (market-like)",
    normal: "0.4 – 0.7 or 1.3 – 2.0",
    bad: "< 0.4 (uncorrelated) or > 2.0 (very volatile)",
    exception:
      "Low-beta utilities and high-beta tech/biotech are normal for their sectors. A negative beta (rare) means the stock tends to move opposite the market.",
  },
  sharpe: {
    label: "Sharpe Ratio",
    blurb: "Return per unit of risk — > 1.0 is good, higher means better risk-adjusted performance",
    meaning:
      "Risk-adjusted return — excess return per unit of total volatility. (Return − RiskFree) ÷ StdDev. Annualised from daily log returns. Higher is better; > 1.0 is considered good.",
    format: "num",
    dir: "high",
    good: "≥ 1.0 (strong risk-adjusted return)",
    normal: "0.5 – 1.0 (adequate)",
    bad: "< 0.5 (poor compensation for risk)",
    exception:
      "Sharpe penalises upside volatility as much as downside. Use Sortino for a downside-only view. Short lookback periods can give misleadingly high/low values.",
  },
  sortino: {
    label: "Sortino Ratio",
    blurb: "Like Sharpe but only penalises downside — higher means better downside-adjusted return",
    meaning:
      "Like Sharpe but only penalises downside deviation (returns below zero). Better for assessing strategies where upside volatility is welcome. Annualised from daily log returns.",
    format: "num",
    dir: "high",
    good: "≥ 1.0 (strong downside-adjusted return)",
    normal: "0.5 – 1.0 (adequate)",
    bad: "< 0.5 (poor downside compensation)",
    exception:
      "A very high Sortino with a low Sharpe suggests the stock had large upside swings — not necessarily sustainable.",
  },
  altmanZ: {
    label: "Altman Z-Score",
    blurb: "Bankruptcy risk model — > 2.99 is safe, < 1.81 signals distress risk",
    meaning:
      "Bankruptcy-prediction model combining five financial ratios: working capital, retained earnings, EBIT, market cap, and sales — all scaled to total assets. Originally calibrated for public manufacturers.",
    format: "num",
    dir: "high",
    good: "> 2.99 (Safe Zone — low bankruptcy risk)",
    normal: "1.81 – 2.99 (Grey Zone — warrants monitoring)",
    bad: "< 1.81 (Distress Zone — elevated bankruptcy risk)",
    exception:
      "Best suited for manufacturing firms. Tech, financial, and service companies may score deceptively low due to asset-light balance sheets. Use as one signal among many.",
  },
};
