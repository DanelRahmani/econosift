const DASH = "—";

export function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return DASH;
  return v.toFixed(digits);
}

export function fmtPct(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return DASH;
  return `${v.toFixed(digits)}%`;
}

// For ratios stored as fractions (e.g. 0.25 -> 25.00%)
export function fmtPctFromFraction(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return DASH;
  return `${(v * 100).toFixed(digits)}%`;
}

export function fmtPrice(v: number | null | undefined, currency = "$"): string {
  if (v === null || v === undefined || Number.isNaN(v)) return DASH;
  return `${currency}${v.toFixed(2)}`;
}

export function fmtLarge(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return DASH;
  const abs = Math.abs(v);
  if (abs >= 1e12) return `${(v / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  return v.toFixed(2);
}

export const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: "$", EUR: "€", GBP: "£", JPY: "¥", CNY: "¥",
  CHF: "Fr", CAD: "C$", AUD: "A$", INR: "₹", KRW: "₩",
};

export function currencySymbol(code: string | undefined): string {
  if (!code) return "$";
  return CURRENCY_SYMBOLS[code] || `${code} `;
}

// Brand-led series palette: crimson first, then complementary hues that read
// well on both the light (#fff) and dark (#0f0608) Axiom backgrounds.
export const CHART_COLORS = [
  "#c4394a", "#0065cb", "#16a34a", "#ca8a04",
  "#0891b2", "#9333ea", "#ea580c", "#db2777",
];
