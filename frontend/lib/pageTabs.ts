/**
 * Sub-tabs that pages expose as `?tab=…` deep links. Each page renders its tab bar from
 * these lists, and the command palette (P1-18) builds its "Page › Tab" entries from the
 * same lists, so a renamed or added tab cannot drift out of the palette.
 */

/** Markets: the `tab` param is the label itself. */
export const MARKETS_TABS = ["Overview", "Technicals", "Valuation", "Ratios", "News & Events", "Sectors", "Treemap", "Short Interest"] as const;

/** Portfolio: the `tab` param is the label itself. */
export const PORTFOLIO_TABS = ["Overview", "Risk", "Attribution", "Optimize", "Scenario", "Transactions"] as const;

/** Yield: the `tab` param is the label itself. */
export const YIELD_TABS = ["US Curve", "Foreign Spreads", "Global Yields", "Real & Breakeven", "Curve Noise", "US Rates Detail", "Policy Tracker", "Sovereign Risk", "Central Banks", "Default Risk"] as const;

export const RESEARCH_TABS = [
  { key: "riskparity", label: "Risk Parity" },
  { key: "carry", label: "FX Carry" },
  { key: "momentum", label: "Momentum" },
  { key: "moments", label: "Realized Moments" },
  { key: "crossasset", label: "Cross-Asset" },
  { key: "fxmacro", label: "FX-Macro Link" },
  { key: "multicountry", label: "Multi-Country" },
  { key: "dupont", label: "Sector DuPont" },
  { key: "econlab", label: "Econometric Lab" },
  { key: "eventstudy", label: "Event Study" },
  { key: "factorregime", label: "Factor Regime" },
  { key: "backtest", label: "Backtester" },
] as const;

export const MACRO_TABS = [
  { id: "overview", label: "Overview" },
  { id: "inflation", label: "Inflation" },
  { id: "employment", label: "Growth & Employment" },
  { id: "housing", label: "Housing" },
  { id: "fiscal", label: "Fiscal" },
  { id: "labor", label: "Labor" },
  { id: "energy", label: "Energy & Climate" },
  { id: "inequality", label: "Inequality" },
  { id: "business", label: "Business Dynamism" },
  { id: "commodities", label: "Commodities" },
  { id: "fx", label: "FX" },
  { id: "leading", label: "Leading Indicators" },
  { id: "financial", label: "Financial & Funding Conditions" },
  { id: "sentiment", label: "Sentiment & Positioning" },
] as const;

