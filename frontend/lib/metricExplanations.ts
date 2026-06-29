// Central dictionary of metric explanations for tooltips + walkthrough content.
// Used by MetricTooltip and WalkthroughBanner components.

export type MetricKey = keyof typeof METRIC_EXPLANATIONS;

export interface MetricEntry {
  short: string;
  long: string;
  wikiSlug?: string;
  color?: "green" | "red" | "neutral";
  warning?: string;
}

export type WalkthroughKey = "dashboard" | "markets" | "portfolio";

export const METRIC_EXPLANATIONS = {
  // ── General / Cross-page ──
  sharpe: {
    short: "Return per unit of risk — higher is better.",
    long: "Sharpe Ratio = (Return − Risk-Free Rate) ÷ Volatility. Above 1 is good, above 2 is excellent, below 0.5 is poor.",
    wikiSlug: "sharpe-ratio",
    color: "green",
  },
  sortino: {
    short: "Like Sharpe but only penalizes downside volatility.",
    long: "Sortino Ratio = (Return − Risk-Free Rate) ÷ Downside Deviation. Ignores upside volatility — better for asymmetric return profiles.",
    wikiSlug: "sortino-ratio",
    color: "green",
  },
  beta: {
    short: "How much a stock moves with the market.",
    long: "Beta = 1 means moves with the market. Beta > 1 amplifies moves, Beta < 1 dampens them. Negative Beta means it moves opposite the market.",
    wikiSlug: "beta",
    color: "neutral",
  },
  volatility: {
    short: "How much the price fluctuates — annualized standard deviation of returns.",
    long: "Annualized Volatility = Daily Std Dev × √252. ~15% is typical for S&P 500; >30% is high risk; <10% is low volatility.",
    wikiSlug: "volatility",
    color: "neutral",
    warning: "High volatility is normal for individual stocks — diversify to reduce it.",
  },
  var95: {
    short: "The worst loss you'd expect 95% of the time.",
    long: "Value at Risk (95%) = the loss threshold exceeded only 5% of days. e.g., VaR 3% means on 95% of days, loss < 3%.",
    wikiSlug: "value-at-risk",
    color: "red",
    warning: "VaR does NOT capture tail risk beyond the threshold. Use CVaR for worst-case scenarios.",
  },
  cvar95: {
    short: "Average loss on the worst 5% of days.",
    long: "Conditional VaR = average loss in the worst 5% tail. More conservative than VaR — captures 'how bad bad gets'.",
    wikiSlug: "conditional-value-at-risk",
    color: "red",
  },
  maxDrawdown: {
    short: "Largest peak-to-trough decline.",
    long: "Max Drawdown = (Trough − Peak) ÷ Peak. A 50% drawdown needs a 100% gain to recover. This is the ultimate test of staying power.",
    wikiSlug: "drawdown",
    color: "red",
    warning: "Drawdowns are unavoidable — focus on recovery time more than depth.",
  },
  annReturn: {
    short: "Compounded yearly return.",
    long: "Annualized Return = (End Value ÷ Start Value)^(1/Years) − 1. Unlike average return, this accounts for compounding.",
    wikiSlug: "compound-annual-growth-rate",
    color: "green",
  },
  totalReturn: {
    short: "Overall percentage gain or loss over the entire period.",
    long: "Total Return = (Current Value − Initial Value) ÷ Initial Value. Includes price changes and dividends. Not annualized.",
    wikiSlug: "total-return",
    color: "green",
  },

  // ── Valuation ──
  trailingPE: {
    short: "Price ÷ last 12 months' earnings.",
    long: "A high P/E may mean the market expects future growth, or it may mean the stock is overvalued. Compare to industry average.",
    wikiSlug: "price-earnings-ratio",
    color: "neutral",
  },
  forwardPE: {
    short: "Price ÷ forecasted next-12-months' earnings.",
    long: "Usually lower than trailing P/E if earnings are expected to grow. Be skeptical — analysts forecasts are often optimistic.",
    wikiSlug: "forward-price-to-earnings",
    color: "neutral",
  },
  dcfTarget: {
    short: "Intrinsic value based on discounted future cash flows.",
    long: "DCF = present value of all projected free cash flows + terminal value, discounted at WACC. If DCF > market price, the stock may be undervalued.",
    wikiSlug: "discounted-cash-flow",
    color: "green",
  },
  dividendYield: {
    short: "Annual dividend ÷ share price.",
    long: "High yield (>4%) may indicate value, or a dividend that might be cut. Low yield may indicate a growth company reinvesting profits.",
    wikiSlug: "dividend-yield",
    color: "neutral",
  },
  fcfYield: {
    short: "Free cash flow per share ÷ share price — like earnings yield but harder to manipulate.",
    long: "FCF Yield > 5% is attractive. Free cash flow is what's left after capital expenditures — real cash available to shareholders.",
    wikiSlug: "free-cash-flow-yield",
    color: "green",
  },
  evToFcf: {
    short: "Enterprise Value ÷ Free Cash Flow — total company value vs cash generation.",
    long: "Lower is better. Accounts for debt unlike P/E. EV/FCF < 15 often considered undervalued.",
    wikiSlug: "enterprise-value-to-free-cash-flow",
    color: "green",
  },
  pegRatio: {
    short: "P/E ÷ earnings growth rate — adjusts valuation for growth.",
    long: "PEG < 1 suggests undervalued relative to growth. PEG > 2 suggests overvalued. Only meaningful for companies with positive earnings.",
    wikiSlug: "peg-ratio",
    color: "green",
  },

  // ── Profitability ──
  roic: {
    short: "Return on Invested Capital — how efficiently a company uses its capital.",
    long: "ROIC = NOPAT ÷ Invested Capital. Above WACC means the company creates value. Below WACC means it destroys value. >15% is excellent.",
    wikiSlug: "return-on-invested-capital",
    color: "green",
  },
  roe: {
    short: "Return on Equity — profit generated from shareholders' money.",
    long: "ROE = Net Income ÷ Shareholder Equity. >15% is strong. Watch out: high debt inflates ROE without improving the business.",
    wikiSlug: "return-on-equity",
    color: "green",
  },
  grossMargin: {
    short: "Revenue minus cost of goods sold, as a percentage.",
    long: "Higher gross margin = more pricing power. Compare within the same industry — tech companies often have 60%+, retailers 20-30%.",
    wikiSlug: "gross-margin",
    color: "green",
  },
  operatingMargin: {
    short: "Operating profit ÷ revenue — profitability before interest and taxes.",
    long: "Shows how efficiently the company runs its core business. Trending upward is a bullish sign. >15% is healthy for most industries.",
    wikiSlug: "operating-margin",
    color: "green",
  },
  netMargin: {
    short: "Bottom-line profit as % of revenue.",
    long: "Net Margin = Net Income ÷ Revenue. Accounts for ALL costs. Low margin + high debt = risky combination.",
    wikiSlug: "net-profit-margin",
    color: "green",
  },

  // ── Leverage & Liquidity ──
  debtToEquity: {
    short: "Total debt ÷ shareholder equity — how leveraged the company is.",
    long: "<0.5 is conservative, >2 is highly leveraged. Banks naturally have higher D/E. Compare to industry peers, not across sectors.",
    wikiSlug: "debt-to-equity-ratio",
    color: "red",
    warning: "High debt magnifies both gains AND losses during downturns.",
  },
  currentRatio: {
    short: "Current assets ÷ current liabilities — short-term financial health.",
    long: ">1.5 is comfortable. <1 means the company may struggle to pay bills. Too high (>3) might mean inefficient use of assets.",
    wikiSlug: "current-ratio",
    color: "green",
  },
  quickRatio: {
    short: "Like Current Ratio but excludes inventory — stricter test.",
    long: "Quick Ratio = (Cash + Receivables) ÷ Current Liabilities. >1 is solid. Inventory can be hard to sell in a crisis.",
    wikiSlug: "quick-ratio",
    color: "green",
  },
  interestCoverage: {
    short: "Operating profit ÷ interest expense — can the company pay its debts?",
    long: ">5 is comfortable. <2 is dangerous — one bad quarter and interest payments could overwhelm profits.",
    wikiSlug: "interest-coverage-ratio",
    color: "green",
  },

  // ── Efficiency ──
  assetTurnover: {
    short: "Revenue ÷ total assets — how efficiently assets generate sales.",
    long: "Higher is better. Retailers often have >2 (high volume), utilities <0.5 (asset-heavy). Compare within industry.",
    wikiSlug: "asset-turnover-ratio",
    color: "neutral",
  },
  inventoryTurnover: {
    short: "How fast the company sells through inventory.",
    long: "High turnover = efficient (or understocked). Low turnover = products sitting on shelves (or overstocked).",
    wikiSlug: "inventory-turnover",
    color: "neutral",
  },

  // ── Technicals ──
  rsi: {
    short: "Relative Strength Index — momentum oscillator (0-100).",
    long: ">70 = overbought (might pull back). <30 = oversold (might bounce). RSI works best in range-bound markets, fails in strong trends.",
    wikiSlug: "relative-strength-index",
    color: "neutral",
    warning: "RSI can stay overbought for weeks in a strong uptrend — don't use it alone.",
  },
  macd: {
    short: "Moving Average Convergence Divergence — trend-following momentum indicator.",
    long: "Bullish: MACD line crosses above signal line. Bearish: crosses below. Divergence (price makes new high but MACD doesn't) signals weakness.",
    wikiSlug: "macd",
    color: "neutral",
  },

  // ── Risk / Advanced ──
  hurst: {
    short: "Hurst exponent — measures trend persistence vs mean reversion.",
    long: ">0.5 = trending (momentum works). <0.5 = mean-reverting (buy dips). =0.5 = random walk (no edge).",
    wikiSlug: "hurst-exponent",
    color: "neutral",
  },
  garch: {
    short: "GARCH(1,1) — statistical model for volatility clustering.",
    long: "GARCH captures the tendency of volatile periods to cluster together. Used to forecast short-term volatility better than simple historical vol.",
    wikiSlug: "garch",
    color: "neutral",
  },
  alpha: {
    short: "Excess return beyond what beta predicts — 'skill' vs the market.",
    long: "Positive alpha means the portfolio beat its benchmark after adjusting for risk (beta). Alpha is the holy grail of active management — hard to sustain.",
    wikiSlug: "alpha",
    color: "green",
  },
  rSquared: {
    short: "How much of the portfolio's movement is explained by the benchmark.",
    long: "R² = 0.9 means 90% of performance comes from market moves, 10% from stock selection. Index funds have R² near 1.0 by design.",
    wikiSlug: "r-squared",
    color: "neutral",
  },
  kellyFraction: {
    short: "Optimal position size based on expected return and volatility.",
    long: "Kelly Criterion = (Expected Return) ÷ Variance. Full Kelly is aggressive — most traders use half-Kelly for safety.",
    wikiSlug: "kelly-criterion",
    color: "neutral",
    warning: "Kelly assumes you know true probabilities — in investing, you don't. Use conservatively.",
  },

  // ── Portfolio ──
  efficientFrontier: {
    short: "The set of portfolios offering the highest return for each level of risk.",
    long: "Any portfolio below the frontier is suboptimal — you could get more return for the same risk, or less risk for the same return.",
    wikiSlug: "efficient-frontier",
    color: "green",
  },
  riskContribution: {
    short: "How much each holding contributes to total portfolio risk.",
    long: "A stock with small weight can dominate risk if it's highly volatile and correlated. Risk parity aims to equalize these contributions.",
    wikiSlug: "risk-contribution",
    color: "neutral",
  },
  correlation: {
    short: "How two assets move together — from -1 (opposite) to +1 (identical).",
    long: "Correlation of 0 = no relationship. Diversification works best with low or negative correlations. Watch out: correlations spike during crises.",
    wikiSlug: "correlation",
    color: "green",
    warning: "In a crisis, all correlations tend toward +1 — diversification can fail when you need it most.",
  },

  // ── Market Breadth ──
  mcclellan: {
    short: "McClellan Oscillator — short-term market breadth momentum.",
    long: "Positive = more stocks advancing. Readings above +100 suggest overbought, below -100 suggest oversold. Works best with the Summation Index.",
    wikiSlug: "mcclellan-oscillator",
    color: "neutral",
  },
  fearGreed: {
    short: "CNN Fear & Greed Index — composite of 7 market sentiment signals.",
    long: "0 = Extreme Fear (contrarian buy signal). 100 = Extreme Greed (contrarian sell signal). Based on momentum, put/call, VIX, junk demand, etc.",
    wikiSlug: "fear-and-greed-index",
    color: "neutral",
    warning: "Markets can stay irrational longer than you can stay solvent. Fear & Greed is a guide, not a timer.",
  },
  advanceDecline: {
    short: "Number of stocks going up vs down in an index.",
    long: "When the market rises but fewer stocks participate (narrow breadth), it's a warning sign. Healthy rallies have broad participation.",
    wikiSlug: "advance-decline-line",
    color: "neutral",
  },

  // ── Options ──
  iv30: {
    short: "Implied Volatility — the market's expectation of future volatility, derived from option prices.",
    long: "Higher IV = more expensive options. IV30 is the 30-day at-the-money implied vol. 'Buy low IV, sell high IV' is the options trader's mantra.",
    wikiSlug: "implied-volatility",
    color: "neutral",
  },
  ivRank: {
    short: "Where current IV stands vs its 1-year range (0-100%).",
    long: "IV Rank 0 = at 1-year low, 100 = at 1-year high. >50 = options are relatively expensive, <25 = relatively cheap.",
    wikiSlug: "implied-volatility-rank",
    color: "neutral",
  },
  maxPain: {
    short: "The strike price where option buyers lose the most — often where the stock gravitates at expiry.",
    long: "Max Pain theory: market makers hedge to push the stock toward the strike where most options expire worthless. Controversial but often accurate.",
    wikiSlug: "max-pain-theory",
    color: "neutral",
  },
  delta: {
    short: "How much the option price changes for a $1 move in the stock.",
    long: "Call delta 0-1, put delta -1-0. At-the-money ≈ 0.5. Delta also approximates the probability of expiring in-the-money.",
    wikiSlug: "delta",
    color: "neutral",
  },
  gamma: {
    short: "How fast delta changes — the 'acceleration' of the option price.",
    long: "High gamma near expiry = wild swings. Long gamma benefits from volatility, short gamma gets crushed by it.",
    wikiSlug: "gamma",
    color: "neutral",
  },
  theta: {
    short: "Time decay — how much value the option loses each day.",
    long: "Theta accelerates near expiry. Option buyers fight theta; option sellers collect it. 'Theta gang' strategies profit from time decay.",
    wikiSlug: "theta",
    color: "red",
  },
  vega: {
    short: "How much the option price changes when IV moves 1%.",
    long: "Long options = long vega (profit from IV increase). Short options = short vega (profit from IV decrease, get hurt by spikes).",
    wikiSlug: "vega",
    color: "neutral",
  },

  // ── Macro ──
  gdpGrowth: {
    short: "Year-over-year GDP growth — the broadest measure of economic health.",
    long: "2-3% is 'normal' for developed economies. Negative = recession. Too high (>6%) may signal overheating and inflation risk.",
    wikiSlug: "gross-domestic-product",
    color: "green",
  },
  cpiInflation: {
    short: "Consumer Price Index — year-over-year change in consumer prices.",
    long: "~2% is targeted by most central banks. >5% is painful. Deflation (<0%) can be worse than inflation — it causes consumers to delay spending.",
    wikiSlug: "consumer-price-index",
    color: "red",
    warning: "Headline CPI includes volatile food & energy. Core CPI excludes them for a smoother trend.",
  },
  unemployment: {
    short: "Percentage of the labor force actively seeking work.",
    long: "~4-5% is 'full employment' in the US. Very low unemployment (<3%) can drive wage inflation. High unemployment (>8%) signals recession.",
    wikiSlug: "unemployment-rate",
    color: "red",
  },
  yieldSpread: {
    short: "10-year minus 2-year Treasury yield — recession predictor.",
    long: "Inverted (negative) = markets expect rate cuts — often precedes recession. Has predicted every US recession since 1950, with few false positives.",
    wikiSlug: "yield-curve",
    color: "red",
    warning: "The inversion itself doesn't cause recession — it signals that the bond market expects one.",
  },
  creditSpread: {
    short: "Corporate bond yield minus Treasury yield — default risk premium.",
    long: "Widening = investors demand more compensation for risk (bearish). Narrowing = risk appetite improving (bullish). Investment grade spreads typically 0.5-2%.",
    wikiSlug: "credit-spread",
    color: "red",
  },
  policyRate: {
    short: "The central bank's main interest rate — sets the floor for all other rates.",
    long: "Rising rates = tightening (slows economy, hurts growth stocks). Falling rates = easing (stimulates economy, helps growth stocks).",
    wikiSlug: "federal-funds-rate",
    color: "neutral",
  },

  // ── Corporate Health ──
  altmanZ: {
    short: "Altman Z-Score — bankruptcy probability within 2 years.",
    long: ">3.0 = Safe zone. 1.8-3.0 = Grey zone (watch carefully). <1.8 = Distress zone (high bankruptcy risk). Based on profitability, leverage, liquidity, and efficiency.",
    wikiSlug: "altman-z-score",
    color: "red",
    warning: "Z-Score was designed for manufacturing firms. Use cautiously for financials and tech companies.",
  },
  piotroski: {
    short: "Piotroski F-Score — 9-point fundamental strength check for value stocks.",
    long: "Scores 0-9 on profitability, leverage, and operating efficiency. 7-9 = strong. 0-3 = weak. Designed to find the best value stocks and avoid value traps.",
    wikiSlug: "piotroski-score",
    color: "green",
  },
  beneish: {
    short: "Beneish M-Score — detects earnings manipulation from financial statements.",
    long: "> -1.78 = likely manipulator. < -1.78 = unlikely manipulator. Uses 8 ratios including receivables growth, margin decline, and asset quality.",
    wikiSlug: "beneish-m-score",
    color: "red",
  },

  // ── FX ──
  fxCarry: {
    short: "Profit from borrowing in low-rate currencies and lending in high-rate ones.",
    long: "Daily carry = (target rate − base rate) ÷ 365. Positive carry pays you to hold the position. Carry trades work until they crash — typically during risk-off events.",
    wikiSlug: "carry-trade",
    color: "green",
    warning: "Carry trades are 'picking up nickels in front of a steamroller' — steady small gains, occasional massive losses.",
  },
} as const;

// ── Walkthroughs ──
export const WALKTHROUGHS: Record<WalkthroughKey, string[]> = {
  dashboard: [
    "Welcome to the Dashboard! This is your daily market pulse — a high-level snapshot of what's happening across financial markets right now.",
    "Market Breadth shows whether most stocks are going up (healthy) or only a few are carrying the market (unhealthy). The McClellan Oscillator helps spot momentum shifts.",
    "The Fear & Greed Index combines 7 signals into one number: 0 = extreme fear (often a buying opportunity), 100 = extreme greed (often a warning sign).",
    "Top Movers highlights the biggest gainers, losers, and unusual volume stocks. Unusual volume can signal something important happening in a stock.",
  ],
  markets: [
    "The Markets page is your deep-dive into individual stocks. Enter a ticker (like AAPL or TSLA) in the search bar to get started.",
    "The Overview tab shows key stats at a glance: price, PE ratio, market cap, and dividend yield. Green metrics are good, red ones warrant attention.",
    "Switch to the Technicals tab to see charts with indicators like RSI and MACD. RSI >70 means 'overbought', <30 means 'oversold'. MACD shows trend direction.",
    "The Valuation tab estimates what a stock is really worth using 8 different models. The Snowflake Score combines them into one composite rating.",
  ],
  portfolio: [
    "The Portfolio page lets you track your holdings and see how they perform together. Add tickers and weights, then click 'Analyze Portfolio'.",
    "The KPIs at the top show your portfolio's health: total return, annualized return, volatility, Sharpe ratio, and maximum drawdown.",
    "The Risk tab shows correlations between your holdings — diversification works best with assets that don't move together.",
    "The Optimize tab uses math to find the best mix: the Efficient Frontier shows ideal portfolios, and Monte Carlo simulates thousands of random allocations.",
  ],
};
