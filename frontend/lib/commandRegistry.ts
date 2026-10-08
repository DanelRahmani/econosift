/**
 * Static entries for the command palette (P1-18): every page and every deep-linkable sub-tab,
 * plus the fuzzy ranking shared with the live ticker and Wiki results.
 */
import { MACRO_TABS, MARKETS_TABS, PORTFOLIO_TABS, RESEARCH_TABS, YIELD_TABS } from "@/lib/pageTabs";

export type CommandGroup = "Pages" | "Tabs" | "Tickers" | "Wiki";

export interface CommandItem {
  id: string;
  group: CommandGroup;
  label: string;
  /** Secondary text, e.g. the parent page of a tab or a ticker's exchange. */
  hint?: string;
  href: string;
  /** Extra words matched (weakly) by the fuzzy search. */
  keywords?: string;
}

const PAGES: { href: string; label: string; keywords: string }[] = [
  { href: "/dashboard", label: "Dashboard", keywords: "home breadth fear greed movers indices" },
  { href: "/markets", label: "Markets", keywords: "stocks quote chart technicals valuation dcf ratios" },
  { href: "/screener", label: "Screener", keywords: "screen signals filter s&p 500 nasdaq dow" },
  { href: "/portfolio", label: "Portfolio", keywords: "efficient frontier black-litterman monte carlo kelly fama-french scenario lab stress test gfc covid shock" },
  { href: "/research", label: "Research", keywords: "quant risk parity carry momentum backtest" },
  { href: "/macro", label: "Macro", keywords: "economy gdp inflation employment" },
  { href: "/atlas", label: "Atlas", keywords: "map world choropleth countries" },
  { href: "/risk", label: "Risk", keywords: "garch hurst cointegration var volatility" },
  { href: "/options", label: "Options", keywords: "greeks implied volatility iv smile black-scholes" },
  { href: "/calendar", label: "Calendar", keywords: "earnings economic releases dividends ipo central bank meetings" },
  { href: "/yield", label: "Yield", keywords: "treasury curve tips breakeven term premium bonds policy sovereign central banks carry divergence default" },
  { href: "/sovereign", label: "Sovereign Risk", keywords: "ratings default traffic light" },
  { href: "/trade", label: "Trade", keywords: "exports imports balance openness" },
  { href: "/corporate", label: "Corporate Health", keywords: "altman piotroski beneish z-score" },
  { href: "/dividends", label: "Dividends", keywords: "yield aristocrats payout ddm" },
  { href: "/insider", label: "Insider Trading", keywords: "form 4 buy sell cluster" },
  { href: "/mergers", label: "Merger News", keywords: "m&a mergers acquisitions news" },
  { href: "/stability", label: "Stability", keywords: "currency crisis banking early warning npl" },
  { href: "/crossborder", label: "Cross-Border", keywords: "bis banking debt securities" },
  { href: "/country", label: "Countries", keywords: "country profiles factbook" },
  { href: "/wiki", label: "Wiki", keywords: "dictionary glossary terms definitions" },
  { href: "/admin", label: "Admin", keywords: "settings api keys cache theme health" },
];

function tabItems(page: string, path: string, tabs: readonly { value: string; label: string }[]): CommandItem[] {
  return tabs.map((t) => ({
    id: `tab:${path}:${t.value}`,
    group: "Tabs" as const,
    label: t.label,
    hint: page,
    href: `${path}?tab=${encodeURIComponent(t.value)}`,
    keywords: page,
  }));
}

const byLabel = (tabs: readonly string[]) => tabs.map((t) => ({ value: t, label: t }));

export const STATIC_COMMANDS: CommandItem[] = [
  ...PAGES.map((p) => ({ id: `page:${p.href}`, group: "Pages" as const, label: p.label, href: p.href, keywords: p.keywords })),
  ...tabItems("Markets", "/markets", byLabel(MARKETS_TABS)),
  ...tabItems("Macro", "/macro", MACRO_TABS.map((t) => ({ value: t.id, label: t.label }))),
  ...tabItems("Research", "/research", RESEARCH_TABS.map((t) => ({ value: t.key, label: t.label }))),
  ...tabItems("Portfolio", "/portfolio", byLabel(PORTFOLIO_TABS)),
  ...tabItems("Yield", "/yield", byLabel(YIELD_TABS)),
];

/** True when every character of `needle` appears in `hay` in order. */
function isSubsequence(needle: string, hay: string): boolean {
  let i = 0;
  for (const ch of hay) if (ch === needle[i]) i++;
  return i === needle.length;
}

/**
 * Fuzzy score of `query` against an item (0 = no match). Every query word must match the label
 * (word start 3, substring 2, in-order letters 1) or, more weakly, the hint/keywords (1).
 * A label starting with the whole query gets a bonus.
 */
export function scoreCommand(query: string, item: Pick<CommandItem, "label" | "hint" | "keywords">): number {
  const q = query.trim().toLowerCase();
  if (!q) return 1;
  const label = item.label.toLowerCase();
  const extra = `${item.hint ?? ""} ${item.keywords ?? ""}`.toLowerCase();
  let score = 0;
  for (const word of q.split(/\s+/)) {
    const atWordStart = new RegExp(`(^|[^a-z0-9])${word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`).test(label);
    if (atWordStart) score += 3;
    else if (label.includes(word)) score += 2;
    else if (extra.includes(word)) score += 1;
    else if (word.length >= 3 && isSubsequence(word, label)) score += 1;
    else return 0;
  }
  if (label.startsWith(q)) score += 5;
  return score;
}

/** Best matches first; ties keep registry order (pages before tabs). */
export function rankCommands(query: string, items: CommandItem[], limit = 8): CommandItem[] {
  return items
    .map((item, i) => ({ item, i, s: scoreCommand(query, item) }))
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s || a.i - b.i)
    .slice(0, limit)
    .map((x) => x.item);
}
