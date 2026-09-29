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

/**
 * Flexible percentage formatter — callers specify whether the value is
 * already a percentage ("direct", e.g. 0.39 → "0.39%") or a fraction
 * ("fraction", e.g. 0.0039 → "0.39%").
 */
export function fmtPctFlex(
  v: number | null | undefined,
  fmt: "direct" | "fraction",
  digits = 2,
): string {
  if (fmt === "direct") return fmtPct(v, digits);
  return fmtPctFromFraction(v, digits);
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

/** Abbreviate long country names for bar chart Y-axis labels.
 *  Maps full names to common short forms (max ~10 chars). */
const COUNTRY_ABBREV: Record<string, string> = {
  "United States": "US",
  "United Kingdom": "UK",
  "South Korea": "S. Korea",
  "Netherlands": "Netherlands",
  "Switzerland": "Switzerland",
  "Norway": "Norway",
  "Sweden": "Sweden",
  "Germany": "Germany",
  "France": "France",
  "Italy": "Italy",
  "Spain": "Spain",
  "Canada": "Canada",
  "Australia": "Australia",
  "Japan": "Japan",
  "China": "China",
  "India": "India",
  "Brazil": "Brazil",
  "Mexico": "Mexico",
};
export function shortCountryName(name: string): string {
  return COUNTRY_ABBREV[name] ?? name;
}

export const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: "$", EUR: "€", GBP: "£", JPY: "¥", CNY: "¥",
  CHF: "Fr", CAD: "C$", AUD: "A$", INR: "₹", KRW: "₩",
};

export function currencySymbol(code: string | undefined): string {
  if (!code) return "$";
  return CURRENCY_SYMBOLS[code] || `${code} `;
}

// Brand-led series palette: navy, teal, and amber first, followed by
// complementary hues that read well on both light and dark EconoSift surfaces.
export const CHART_COLORS = [
  "#142A43", "#2F8F83", "#D99A36", "#3b82f6",
  "#0891b2", "#9333ea", "#ea580c", "#db2777",
];

/** Format an ISO timestamp to a readable date-time string. */
export function formatAsOf(iso: string | null | undefined): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", {
      month: "short", day: "numeric", year: "numeric",
      hour: "numeric", minute: "2-digit", timeZoneName: "short",
    });
  } catch {
    return iso.slice(0, 10);
  }
}

export function exportToCsv(filename: string, rows: Record<string, unknown>[]) {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const escape = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return s.includes(",") || s.includes('"') || s.includes("\n")
      ? `"${s.replace(/"/g, '""')}"`
      : s;
  };
  const csv = [headers.join(","), ...rows.map((r) => headers.map((h) => escape(r[h])).join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
