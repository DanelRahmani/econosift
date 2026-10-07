// ── EconoSift Wiki — Financial Terms Dictionary ──
// Static data: ~300 terms across 26 categories, each with a 3-5 sentence
// detailed explanation.  No API required — all search/filter is client-side.

// ── Types ──

export interface WikiTerm {
  /** URL-safe unique identifier (e.g. "moving-average-convergence-divergence") */
  slug: string;
  /** Display name (e.g. "MACD (Moving Average Convergence Divergence)") */
  term: string;
  /** Category key matching WikiCategory.key */
  category: string;
  /** 3-5 sentence detailed explanation */
  definition: string;
  /** Slugs of related terms for cross-linking */
  related: string[];
}

export interface WikiCategory {
  key: string;
  label: string;
  /** Single-char emoji or short descriptor for the category icon */
  icon: string;
}

// ── Categories (26) ──

export const CATEGORIES: WikiCategory[] = [
  { key: "indices",      label: "Market Indices & Benchmarks",   icon: "📊" },
  { key: "technicals",   label: "Technical Indicators",           icon: "📈" },
  { key: "valuation",    label: "Valuation Models",               icon: "💰" },
  { key: "ratios",       label: "Fundamental Financial Ratios",   icon: "📋" },
  { key: "risk",         label: "Risk Metrics",                   icon: "⚠️" },
  { key: "options",      label: "Options & Implied Volatility",   icon: "🔮" },
  { key: "macro",        label: "Macroeconomic Indicators",       icon: "🌍" },
  { key: "yieldcurve",   label: "Yield Curve & Fixed Income",     icon: "📉" },
  { key: "centralbanks", label: "Central Banks & Monetary Policy",icon: "🏦" },
  { key: "fx",           label: "Foreign Exchange (FX)",          icon: "💱" },
  { key: "portfolio",    label: "Portfolio Theory & Analytics",   icon: "🎯" },
  { key: "research",     label: "Research Strategies",            icon: "🔬" },
  { key: "sectors",      label: "Sector & Industry Analysis",     icon: "🏭" },
  { key: "screening",    label: "Screening & Signals",            icon: "🔍" },
  { key: "esg",          label: "ESG & Fraud Detection",          icon: "🛡️" },
  { key: "snowflake",    label: "Snowflake Composite Score",      icon: "❄️" },
  { key: "dashboard",    label: "Dashboard & Market Breadth",     icon: "🖥️" },
  { key: "regime",       label: "Macro Regime Classification",    icon: "🔄" },
  { key: "credit",       label: "Financial Conditions & Credit",  icon: "💳" },
  { key: "sovereign",    label: "Sovereign & Country Risk",       icon: "🏛️" },
  { key: "econlab",      label: "Econometric Lab",                icon: "🧪" },
  { key: "atlas",        label: "Atlas (Global Macro Map)",       icon: "🗺️" },
  { key: "calendar",     label: "Economic Calendar",              icon: "📅" },
  { key: "treemap",      label: "Treemap Visualization",          icon: "🗂️" },
  { key: "stress",       label: "Risk Stress Testing & Monte Carlo", icon: "💥" },
  { key: "misc",         label: "Misc / Infrastructure",          icon: "⚙️" },
];

// ── All Wiki Terms (~300) ──

export const TERMS: WikiTerm[] = [
  // ════════════════════════════════════════════════════════════════
  // 1. Market Indices & Benchmarks
  // ════════════════════════════════════════════════════════════════
  {
    slug: "sp-500",
    term: "S&P 500",
    category: "indices",
    definition:
      "The S&P 500 is a market-capitalisation-weighted index of roughly 500 large US publicly traded companies, maintained by S&P Dow Jones Indices. It is widely regarded as the single best gauge of US large-cap equities and serves as the benchmark against which most fund managers are measured. The index covers about 80% of the US equity market by market cap, spanning all 11 GICS sectors. Its composition is rules-based: a stock must have a market cap of at least $14.6 billion, positive earnings over the most recent four quarters, and adequate liquidity.",
    related: ["dow-30", "nasdaq-100", "spy", "market-cap"],
  },
  {
    slug: "nasdaq-100",
    term: "Nasdaq-100",
    category: "indices",
    definition:
      "The Nasdaq-100 is a market-cap-weighted index of the 100 largest non-financial companies listed on the Nasdaq stock exchange. It is heavily tilted toward technology, with Apple, Microsoft, Amazon, Nvidia, and Alphabet typically dominating the top positions. Financial companies are explicitly excluded, which makes the index less diversified across sectors than the S&P 500. The Nasdaq-100 is often used as a proxy for growth and tech-sector performance and is tracked by the popular Invesco QQQ ETF.",
    related: ["sp-500", "qqq", "nasdaq-composite"],
  },
  {
    slug: "dow-30",
    term: "Dow 30 (DJIA)",
    category: "indices",
    definition:
      "The Dow Jones Industrial Average (DJIA) is a price-weighted index of 30 major US blue-chip companies selected by the editors of The Wall Street Journal. Unlike the S&P 500, the Dow weights stocks by their absolute share price rather than market capitalisation, which means higher-priced stocks have disproportionate influence — a $300 stock moves the index 3× more than a $100 stock, regardless of company size. Created in 1896 by Charles Dow, it is the oldest continuing US market index. The Dow is less representative of the broad market than the S&P 500 but remains culturally iconic.",
    related: ["sp-500", "dia", "price-weighted"],
  },
  {
    slug: "spy",
    term: "SPY (SPDR S&P 500 ETF)",
    category: "indices",
    definition:
      "SPY is the oldest and most liquid US-listed ETF, launched in 1993 by State Street Global Advisors. It tracks the S&P 500 index with extremely tight tracking error and has an expense ratio of approximately 0.09%. With typical daily trading volumes exceeding $30 billion, SPY is the primary vehicle for institutional hedging, liquidity management, and benchmark exposure. It is distinct from other S&P 500 ETFs (like VOO or IVV) due to its massive options market — SPY options are among the most heavily traded in the world.",
    related: ["sp-500", "etf", "options-chain"],
  },
  {
    slug: "agg",
    term: "AGG (iShares Core US Aggregate Bond ETF)",
    category: "indices",
    definition:
      "AGG tracks the Bloomberg US Aggregate Bond Index, which covers the broad US investment-grade bond market including Treasuries, corporate bonds, mortgage-backed securities, and agency debt. With over $100 billion in AUM, it is the benchmark ETF for US fixed-income exposure. The effective duration typically hovers around 6 years, making it moderately sensitive to interest-rate changes. AGG is commonly used as the bond leg in classic 60/40 portfolios and as a risk-free benchmark alternative in fixed-income analysis.",
    related: ["spy", "60-40-benchmark", "duration", "yield-curve"],
  },
  {
    slug: "qqq",
    term: "QQQ (Invesco QQQ Trust)",
    category: "indices",
    definition:
      "QQQ tracks the Nasdaq-100 index, providing concentrated exposure to large-cap technology and growth companies. It is the fifth-most-traded ETF in the US by volume and is highly liquid. QQQ's sector composition is dominated by Information Technology (~50%) and Communication Services (~17%), with negligible exposure to Financials and Energy. Its high growth tilt means it typically outperforms the S&P 500 in bull markets and underperforms during risk-off rotations.",
    related: ["nasdaq-100", "spy", "sector-rotation"],
  },
  {
    slug: "dia",
    term: "DIA (SPDR Dow Jones Industrial Average ETF)",
    category: "indices",
    definition:
      "DIA is the ETF that tracks the Dow Jones Industrial Average, holding the same 30 stocks in the same price-weighted proportions. Launched in 1998, it is smaller and less liquid than SPY or QQQ but still widely referenced. Due to the Dow's price-weighting methodology, DIA's top holdings can shift significantly when a high-priced stock's price changes, even if its market cap hasn't changed meaningfully. This quirk makes DIA behave differently from cap-weighted index ETFs.",
    related: ["dow-30", "spy", "price-weighted"],
  },
  {
    slug: "dxy",
    term: "DXY (US Dollar Index)",
    category: "indices",
    definition:
      "The US Dollar Index (DXY) measures the value of the USD against a basket of six major currencies: EUR (57.6%), JPY (13.6%), GBP (11.9%), CAD (9.1%), SEK (4.2%), and CHF (3.6%). It is a geometrically weighted index, meaning changes are multiplicative rather than additive. The DXY rises when the dollar strengthens relative to the basket. It has been the benchmark USD gauge since 1973, though its heavy euro weighting means it is sometimes overly sensitive to EUR/USD moves.",
    related: ["eur-usd", "fx-carry", "g10-currencies", "central-bank"],
  },
  {
    slug: "irx",
    term: "^IRX (13-Week Treasury Bill)",
    category: "indices",
    definition:
      "^IRX is the CBOE index tracking the yield on the 13-week (3-month) US Treasury bill, annualised on a bond-equivalent basis. It is commonly used as a proxy for the risk-free rate in CAPM calculations, Sharpe ratio denominators, and DCF discount rate estimation. Because the 3-month T-bill is considered virtually free of default risk and has minimal duration, financial models treat it as the closest real-world approximation to the theoretical risk-free asset. The index moves closely with the Fed Funds rate.",
    related: ["capm", "sharpe-ratio", "risk-free-rate", "fed-funds-rate"],
  },
  {
    slug: "tnx",
    term: "^TNX (10-Year Treasury Yield Index)",
    category: "indices",
    definition:
      "^TNX is the CBOE index that reflects the yield on the most recently auctioned 10-year US Treasury note multiplied by 10 (so a 4.25% yield displays as 42.50). The 10-year yield is the most important reference rate in global finance — it anchors mortgage rates, corporate bond yields, and equity valuation discount rates. Movements in the 10-year are driven by growth expectations, inflation expectations, and Fed policy anticipations. It is also the key input for the 'risk-free rate' in most DCF and CAPM implementations.",
    related: ["yield-curve", "capm", "dcf", "breakeven-inflation", "tips"],
  },
  {
    slug: "nasdaq-composite",
    term: "Nasdaq Composite (^IXIC)",
    category: "indices",
    definition:
      "The Nasdaq Composite includes virtually every stock listed on the Nasdaq exchange — over 3,000 companies, including many small-cap and speculative names. Unlike the Nasdaq-100, it includes financial companies and is much broader. It is heavily technology-weighted (over 50%) and is often quoted alongside the S&P 500 and Dow as one of the 'big three' US indices. Due to its inclusion of smaller, younger companies, it tends to be more volatile than the S&P 500.",
    related: ["nasdaq-100", "sp-500", "dow-30"],
  },
  {
    slug: "benchmark",
    term: "Benchmark",
    category: "indices",
    definition:
      "A benchmark is a standard reference index against which the performance of an investment, strategy, or fund is measured. In US equities, the S&P 500 is the most common benchmark; for bonds, it is the Bloomberg US Aggregate (AGG); for global equities, the MSCI World or FTSE All-World. Benchmarks serve two purposes: they provide a passive alternative that any active strategy must beat to justify its fees, and they are used in risk models to calculate metrics like beta, alpha, and tracking error. Choosing the wrong benchmark can make a strategy appear better or worse than it truly is.",
    related: ["sp-500", "beta", "alpha", "tracking-error"],
  },
  {
    slug: "etf",
    term: "ETF (Exchange-Traded Fund)",
    category: "indices",
    definition:
      "An ETF is a pooled investment vehicle that trades on an exchange like a stock, but holds a basket of assets like a mutual fund. ETFs can track indices (passive) or be actively managed. They offer intraday liquidity, transparency of holdings, and generally lower expense ratios than mutual funds. The creation/redemption mechanism involving authorised participants keeps ETF prices close to their net asset value (NAV). Examples at EconoSift include SPY, QQQ, AGG, DIA, and the sector SPDR suite (XLK, XLF, etc.).",
    related: ["spy", "qqq", "agg", "spdr-sector-etfs"],
  },

  // ════════════════════════════════════════════════════════════════
  // 2. Technical Indicators
  // ════════════════════════════════════════════════════════════════
  {
    slug: "macd",
    term: "MACD (Moving Average Convergence Divergence)",
    category: "technicals",
    definition:
      "MACD is a trend-following momentum indicator that reveals the relationship between two exponential moving averages (EMAs) of price — typically the 12-period and 26-period EMAs. The MACD line is the difference between these two EMAs; a 9-period EMA of the MACD line (the signal line) is plotted alongside to generate crossover signals. When the MACD line crosses above the signal line, it is a bullish signal; a cross below is bearish. Divergences between the MACD line and price — where price makes a new high but MACD does not — can warn of an impending trend reversal.",
    related: ["macd-signal-line", "macd-histogram", "rsi", "bollinger-bands", "sma"],
  },
  {
    slug: "macd-signal-line",
    term: "MACD Signal Line",
    category: "technicals",
    definition:
      "The MACD signal line is a 9-period exponential moving average of the MACD line itself. It serves as the trigger for buy and sell signals in the MACD system: when the faster MACD line crosses above the signal line, it generates a bullish crossover; when it crosses below, a bearish crossover. The signal line smooths the MACD line's fluctuations, reducing the number of false signals at the cost of a slight lag. Traders often combine MACD crossovers with other confirmation tools such as trend-line breaks, volume analysis, or RSI to filter out whipsaws in choppy markets.",
    related: ["macd", "macd-histogram", "ema"],
  },
  {
    slug: "macd-histogram",
    term: "MACD Histogram",
    category: "technicals",
    definition:
      "The MACD histogram is the graphical difference between the MACD line and its signal line, plotted as vertical bars above and below a zero line. It provides an early visual warning of momentum shifts — when bars shrink in height regardless of their sign, momentum is decelerating even before a crossover occurs. A rising histogram (bars becoming less negative or more positive) indicates accelerating bullish momentum; a falling histogram signals weakening bullish or building bearish momentum. Gerald Appel, who created MACD, considered the histogram the most useful component of the indicator for anticipating changes in trend direction.",
    related: ["macd", "macd-signal-line", "momentum"],
  },
  {
    slug: "rsi",
    term: "RSI (Relative Strength Index)",
    category: "technicals",
    definition:
      "RSI is a momentum oscillator developed by J. Welles Wilder that measures the speed and magnitude of directional price movements on a 0–100 scale. It is calculated as 100 − (100 / (1 + RS)), where RS is the average gain over the lookback period divided by the average loss. The standard lookback is 14 periods; readings above 70 are traditionally considered overbought and below 30 oversold. However, in strong trending markets RSI can remain overbought or oversold for extended periods, so many traders adjust thresholds to 80/20 or use RSI divergences — where price and RSI move opposite directions — as more reliable signals.",
    related: ["stochastic-rsi", "williams-r", "macd", "bollinger-bands"],
  },
  {
    slug: "bollinger-bands",
    term: "Bollinger Bands",
    category: "technicals",
    definition:
      "Bollinger Bands are a volatility-based envelope plotted at two standard deviations above and below a simple moving average — typically the 20-period SMA. The bands expand during high-volatility periods and contract during low-volatility periods, giving a visual read on market conditions. A 'Bollinger Squeeze' — when the bands narrow significantly — often precedes a sharp breakout, though the direction is not predicted. Price touching or piercing the outer bands does not necessarily signal a reversal; it can indicate a strong trend, and traders often wait for confirmation such as a candle reversal pattern before acting.",
    related: ["bollinger-b", "bollinger-squeeze", "sma", "atr", "keltner-channels"],
  },
  {
    slug: "bollinger-b",
    term: "Bollinger %B",
    category: "technicals",
    definition:
      "%B quantifies where the current price sits within the Bollinger Bands on a 0–1 scale: %B = (Price − Lower Band) / (Upper Band − Lower Band). A value of 0 means price is at the lower band, 1 means it's at the upper band, and 0.5 is the middle band (the SMA). Values above 1 indicate price has broken above the upper band, and below 0 indicate a break below the lower band. %B is useful for screening — for example, scanning for stocks with %B < 0.1 identifies names near the bottom of their volatility envelope.",
    related: ["bollinger-bands", "bollinger-squeeze", "sma"],
  },
  {
    slug: "bollinger-squeeze",
    term: "Bollinger Squeeze",
    category: "technicals",
    definition:
      "A Bollinger Squeeze occurs when the Bollinger Band width narrows to one of its lowest levels over a recent lookback period — typically below the 20th percentile of the prior 125 days. It signals a period of extremely low volatility and is interpreted as the 'calm before the storm,' since low-volatility regimes tend to be followed by high-volatility expansions. The squeeze itself does not predict the direction of the breakout, so traders often combine it with a directional filter such as ADX or wait for a close outside the bands on expanding volume. John Bollinger, the indicator's creator, describes the squeeze as a condition where 'the market is coiling.'",
    related: ["bollinger-bands", "bollinger-b", "atr", "keltner-channels"],
  },
  {
    slug: "ichimoku-cloud",
    term: "Ichimoku Cloud (Ichimoku Kinko Hyo)",
    category: "technicals",
    definition:
      "The Ichimoku Kinko Hyo — Japanese for 'one-glance equilibrium chart' — is a comprehensive technical indicator that plots five lines to show support, resistance, trend direction, and momentum simultaneously. The 'cloud' (kumo) is the shaded area between Senkou Span A and Senkou Span B, projected 26 periods into the future; price above the cloud is bullish, below is bearish, and inside is neutral/choppy. Ichimoku is unusual among indicators in that it directly forecasts future support/resistance zones via the cloud, rather than only analysing past data. It was developed by Japanese journalist Goichi Hosoda in the 1930s and remains widely used in Japan and increasingly globally.",
    related: ["tenkan-sen", "kijun-sen", "senkou-span-a", "senkou-span-b", "chikou-span"],
  },
  {
    slug: "tenkan-sen",
    term: "Tenkan-sen (Conversion Line)",
    category: "technicals",
    definition:
      "The Tenkan-sen is the faster-moving line in the Ichimoku system, calculated as the midpoint of the highest high and lowest low over the past 9 periods: (9-period high + 9-period low) / 2. It represents short-term trend and momentum. When the Tenkan-sen crosses above the Kijun-sen, it generates a bullish signal analogous to a fast MA crossing above a slow MA. The slope of the Tenkan-sen also indicates short-term trend strength — a flat Tenkan-sen suggests consolidation.",
    related: ["kijun-sen", "ichimoku-cloud", "senkou-span-a"],
  },
  {
    slug: "kijun-sen",
    term: "Kijun-sen (Base Line)",
    category: "technicals",
    definition:
      "The Kijun-sen is the slower, medium-term line in Ichimoku, calculated as (26-period high + 26-period low) / 2. It acts as a gauge of medium-term equilibrium and often serves as a trailing stop level in Ichimoku-based trading systems. Price above the Kijun-sen is considered bullish; below is bearish. The Kijun-sen's slope reflects the medium-term trend, and its flatness can indicate a ranging market. A Kijun-sen cross with price is a significant signal in Ichimoku analysis.",
    related: ["tenkan-sen", "ichimoku-cloud", "senkou-span-b"],
  },
  {
    slug: "senkou-span-a",
    term: "Senkou Span A (Leading Span A)",
    category: "technicals",
    definition:
      "Senkou Span A is one of the two lines that form the Ichimoku cloud (kumo), calculated as (Tenkan-sen + Kijun-sen) / 2 and plotted 26 periods ahead of the current bar. Together with Senkou Span B, it defines the cloud's leading edge. When Senkou Span A is above Senkou Span B, the cloud is typically coloured green (bullish); when below, red (bearish). The thickness of the cloud — the gap between the two spans — reflects the volatility of the equilibrium between short- and medium-term trends.",
    related: ["senkou-span-b", "tenkan-sen", "kijun-sen", "ichimoku-cloud"],
  },
  {
    slug: "senkou-span-b",
    term: "Senkou Span B (Leading Span B)",
    category: "technicals",
    definition:
      "Senkou Span B is the slower of the two cloud-forming lines in Ichimoku, calculated as (52-period high + 52-period low) / 2 and plotted 26 periods into the future. Because it uses a longer lookback, Senkou Span B moves more slowly than Senkou Span A, and the resulting cloud represents the zone between short/mid-term equilibrium (Span A) and long-term equilibrium (Span B). A thick cloud ahead of price suggests strong future support or resistance, while a thin cloud may be easily broken.",
    related: ["senkou-span-a", "ichimoku-cloud", "kijun-sen"],
  },
  {
    slug: "chikou-span",
    term: "Chikou Span (Lagging Span)",
    category: "technicals",
    definition:
      "The Chikou Span is the current closing price plotted 26 periods behind the current bar. Visually, it is a lagging confirmation line: if the Chikou Span is above the price of 26 periods ago, the trend is considered bullish; if below, bearish. Because it is plotted in the past, it acts as a 'rear-view mirror' that confirms whether prior price action was strong enough to sustain the current trend. Chikou Span breaking above or below historical price can provide early warning of trend change.",
    related: ["ichimoku-cloud", "tenkan-sen", "kijun-sen"],
  },
  {
    slug: "fibonacci-retracement",
    term: "Fibonacci Retracement Levels",
    category: "technicals",
    definition:
      "Fibonacci retracement levels are horizontal lines drawn on a price chart at key Fibonacci ratios — 23.6%, 38.2%, 50%, 61.8%, and 78.6% — between a significant swing high and swing low. The 61.8% level (the 'golden ratio') is considered the most important; price often finds support or resistance near these levels during pullbacks in a trend. These levels are not derived from any causal financial theory but are widely followed by traders, which can make them self-fulfilling. They are most effective when they coincide with other technical signals such as moving averages, prior support/resistance, or trend-line touches.",
    related: ["fibonacci-extension", "pivot-points", "support-resistance"],
  },
  {
    slug: "fibonacci-extension",
    term: "Fibonacci Extension Levels",
    category: "technicals",
    definition:
      "Fibonacci extensions project price targets beyond 100% of a prior swing — common levels include 127.2%, 138.2%, 161.8%, and 261.8%. They are used to estimate where price may go after breaking through a retracement level, particularly in Elliott Wave and harmonic pattern trading. Unlike retracements, which look backward, extensions aim to forecast forward price objectives. The 161.8% extension is the most popular target for trend-following traders.",
    related: ["fibonacci-retracement", "pivot-points"],
  },
  {
    slug: "pivot-points",
    term: "Pivot Points (Classic)",
    category: "technicals",
    definition:
      "Pivot points are intraday support and resistance levels calculated from the previous period's high, low, and close. The central pivot (PP) = (H + L + C) / 3; support levels S1, S2, S3 and resistance levels R1, R2, R3 are derived from PP and the prior range. Floor traders have used pivot points for decades to identify potential turning points and set stop-loss orders. They are most effective on shorter timeframes (5-min to 1-hour charts) and when multiple timeframes align at the same level.",
    related: ["fibonacci-retracement", "support-resistance", "sma"],
  },
  {
    slug: "stochastic-rsi",
    term: "Stochastic RSI (StochRSI)",
    category: "technicals",
    definition:
      "Stochastic RSI applies the stochastic oscillator formula to RSI values rather than price, creating an indicator of RSI's position within its own range. It oscillates between 0 and 1 (or 0–100), with readings above 0.8 considered overbought and below 0.2 oversold. Because it is a derivative of a derivative, StochRSI is extremely sensitive and generates more signals than RSI alone — making it useful for short-term timing but prone to false signals in choppy markets. It was developed by Tushar Chande and Stanley Kroll.",
    related: ["rsi", "williams-r", "stochastic-oscillator"],
  },
  {
    slug: "williams-r",
    term: "Williams %R",
    category: "technicals",
    definition:
      "Williams %R is a momentum oscillator developed by Larry Williams that measures the closing price relative to the high-low range over a lookback period (typically 14). It ranges from 0 to −100; readings above −20 are considered overbought and below −80 oversold. Unlike RSI, which uses average gains/losses, Williams %R is a simple normalisation of price within its recent range, making it more responsive but also more prone to false signals. It is often used in combination with RSI or MACD for confirmation.",
    related: ["rsi", "stochastic-rsi", "macd"],
  },
  {
    slug: "obv",
    term: "OBV (On-Balance Volume)",
    category: "technicals",
    definition:
      "On-Balance Volume is a cumulative momentum indicator that adds the day's volume to a running total when price closes higher and subtracts it when price closes lower. Developed by Joseph Granville, OBV is based on the premise that volume precedes price: rising OBV confirms an uptrend, while falling OBV confirms a downtrend. An OBV divergence — where price makes a new high but OBV does not — warns that buying pressure is weakening and a trend reversal may be near. OBV works best on liquid stocks where volume data is reliable.",
    related: ["obv-divergence", "cmf", "accumulation-distribution"],
  },
  {
    slug: "obv-divergence",
    term: "OBV Divergence",
    category: "technicals",
    definition:
      "OBV divergence occurs when On-Balance Volume moves in the opposite direction of price. A bearish divergence — price makes a higher high but OBV makes a lower high — suggests that the uptrend lacks volume confirmation and may reverse. A bullish divergence — price makes a lower low but OBV makes a higher low — indicates accumulation during weakness and potential trend reversal upward. Divergences are most meaningful when they persist over multiple weeks, not just a few days.",
    related: ["obv", "cmf", "rsi-divergence"],
  },
  {
    slug: "cmf",
    term: "CMF (Chaikin Money Flow)",
    category: "technicals",
    definition:
      "Chaikin Money Flow is a volume-weighted oscillator created by Marc Chaikin that measures accumulation (buying pressure) versus distribution (selling pressure) over a specified period, typically 20 or 21 days. It uses the close location value — where price closes within its daily high-low range — multiplied by volume, then sums and divides by total volume. CMF oscillates above and below zero; positive values indicate accumulation and negative values indicate distribution. Unlike OBV, CMF accounts for where price closes within the day's range, not just the direction of the close.",
    related: ["obv", "accumulation-distribution", "money-flow-index"],
  },
  {
    slug: "atr",
    term: "ATR (Average True Range)",
    category: "technicals",
    definition:
      "Average True Range is a volatility indicator developed by J. Welles Wilder that measures the average of the true range over a specified period (typically 14). The true range for a given period is the greatest of: (high − low), |high − previous close|, or |low − previous close|. ATR does not indicate price direction — only the degree of price movement. Traders use ATR to set stop-loss distances (e.g., 2× ATR below entry) and position-size based on volatility. Higher ATR values indicate increased volatility and wider stops are warranted.",
    related: ["bollinger-bands", "keltner-channels", "volatility"],
  },
  {
    slug: "sma",
    term: "SMA (Simple Moving Average)",
    category: "technicals",
    definition:
      "A Simple Moving Average is the arithmetic mean of price over a specified number of periods, with each data point weighted equally. The SMA-50 and SMA-200 are the most widely watched moving averages in US equity markets. SMAs lag price because they assign equal weight to all data points in the window; this lag increases with the lookback period. Despite their simplicity, SMAs remain foundational — they form the basis for Bollinger Bands, serve as dynamic support/resistance levels, and are used in crossover strategies like the Golden Cross and Death Cross.",
    related: ["sma-50", "sma-200", "golden-cross", "death-cross", "ema", "bollinger-bands"],
  },
  {
    slug: "sma-50",
    term: "SMA-50 (50-Day Simple Moving Average)",
    category: "technicals",
    definition:
      "The 50-day SMA is a medium-term moving average that smooths out roughly 10 weeks of trading data. It is widely watched by institutional traders as a proxy for the intermediate trend. When price is above the 50-day, the intermediate trend is considered bullish; below, bearish. The 50-day often acts as dynamic support in uptrends — pullbacks to the 50-day that hold are common entry points for trend-following strategies. The percentage of S&P 500 stocks above their 50-day is a key market breadth indicator.",
    related: ["sma", "sma-200", "golden-cross", "death-cross", "market-breadth"],
  },
  {
    slug: "sma-200",
    term: "SMA-200 (200-Day Simple Moving Average)",
    category: "technicals",
    definition:
      "The 200-day SMA is the most important long-term moving average, representing roughly 10 months of trading. It is the definitive line separating bull markets (price above) from bear markets (price below) in the eyes of many institutional investors. The 200-day is often a major support or resistance level — breaking above it after a prolonged period below is considered a significant bullish signal. Many systematic trend-following strategies use the 200-day as a binary risk-on/risk-off switch.",
    related: ["sma", "sma-50", "golden-cross", "death-cross"],
  },
  {
    slug: "golden-cross",
    term: "Golden Cross",
    category: "technicals",
    definition:
      "A Golden Cross is a bullish technical pattern that occurs when the 50-day SMA crosses above the 200-day SMA. It signals that short-term momentum is accelerating relative to the long-term trend, and it is one of the most widely followed bullish signals in technical analysis. The signal is most reliable when it occurs after a prolonged downtrend and is accompanied by rising volume. However, because moving averages are lagging indicators, the Golden Cross often confirms a rally that is already well underway rather than providing an early entry.",
    related: ["death-cross", "sma-50", "sma-200", "sma"],
  },
  {
    slug: "death-cross",
    term: "Death Cross",
    category: "technicals",
    definition:
      "A Death Cross occurs when the 50-day SMA crosses below the 200-day SMA — the bearish counterpart to the Golden Cross. It is interpreted as a signal that short-term momentum has deteriorated enough to drag the intermediate trend below the long-term trend. While historically associated with major bear markets, Death Crosses also generate false signals during whipsawing, range-bound markets. Many analysts treat the Death Cross as a lagging confirmation — most of the damage has often already occurred by the time the crossover triggers.",
    related: ["golden-cross", "sma-50", "sma-200", "sma"],
  },
  {
    slug: "52-week-high-low",
    term: "52-Week High/Low",
    category: "technicals",
    definition:
      "The 52-week high and low are the highest and lowest prices at which a stock has traded over the preceding 52 weeks (roughly one calendar year). These levels are psychologically significant — breaking above the 52-week high is considered bullish and often attracts momentum traders, while breaking below the 52-week low is bearish and can trigger stop-loss cascades. The percentage distance from the 52-week high is a common screening criterion: stocks near their highs are strong, while those far below may indicate persistent weakness or potential value opportunities.",
    related: ["near-52-week-high", "near-52-week-low", "week-52-position", "support-resistance"],
  },
  {
    slug: "week-52-position",
    term: "Week-52 Position",
    category: "technicals",
    definition:
      "The 52-week position expresses where current price sits as a percentage between the 52-week low (0%) and 52-week high (100%). A reading of 80% means the stock is closer to its high than its low, suggesting strength. This metric normalises price across stocks of different absolute values, making it useful for cross-sectional comparison and screening. It is calculated as: (Price − 52-Week Low) / (52-Week High − 52-Week Low) × 100.",
    related: ["52-week-high-low", "near-52-week-high", "near-52-week-low"],
  },
  {
    slug: "normalised-price",
    term: "Normalised Price (Base 100)",
    category: "technicals",
    definition:
      "Normalised price rebases a price series so that the starting value equals 100, with all subsequent values expressed relative to that starting point. For example, a price of 110 would be 10% above the base. This allows direct visual comparison of performance across assets with vastly different absolute prices — comparing a $20 stock to a $500 stock on the same chart. It is particularly useful for multi-asset price charts and relative strength analysis across an index universe.",
    related: ["relative-strength", "sparkline", "price-chart"],
  },

  // ════════════════════════════════════════════════════════════════
  // 3. Valuation Models
  // ════════════════════════════════════════════════════════════════
  {
    slug: "dcf",
    term: "DCF (Discounted Cash Flow)",
    category: "valuation",
    definition:
      "Discounted Cash Flow is an intrinsic valuation method that estimates the value of an investment based on its expected future cash flows, discounted back to present value using a required rate of return. The core principle is that a dollar tomorrow is worth less than a dollar today due to the time value of money and risk. In a two-stage DCF — the most common variant used on EconoSift — cash flows are projected explicitly for a high-growth period (Stage 1, typically 5 years) and then a terminal value captures all cash flows beyond that using a perpetual growth assumption. DCF is considered the most theoretically sound valuation approach, but its output is highly sensitive to assumptions about growth rates and discount rates.",
    related: ["two-stage-dcf", "wacc", "terminal-growth-rate", "intrinsic-value", "fcf"],
  },
  {
    slug: "two-stage-dcf",
    term: "Two-Stage DCF",
    category: "valuation",
    definition:
      "A two-stage DCF models a company's cash flows in two phases: a high-growth explicit forecast period (Stage 1, typically 5 years) followed by a stable terminal growth phase (Stage 2) where the company grows at a perpetual, sustainable rate. The terminal value — often calculated using the Gordon Growth Model — typically represents 60–80% of the total valuation, making the terminal growth rate and WACC assumptions critically important. This structure is preferred for companies expected to grow above the economy's long-run rate in the near term before maturing.",
    related: ["dcf", "terminal-growth-rate", "gordon-growth-model", "wacc"],
  },
  {
    slug: "wacc",
    term: "WACC (Weighted Average Cost of Capital)",
    category: "valuation",
    definition:
      "WACC is the blended cost of a company's capital — both debt and equity — weighted by their respective proportions in the capital structure. It serves as the discount rate in DCF valuation, representing the minimum return a company must earn to satisfy all its capital providers. WACC = (E/V × Cost of Equity) + (D/V × Cost of Debt × (1 − Tax Rate)), where E is equity market value, D is debt market value, and V = E + D. A higher WACC reduces DCF value (more risk → higher discount → lower present value); a lower WACC increases it.",
    related: ["dcf", "cost-of-equity", "cost-of-debt", "capm"],
  },
  {
    slug: "cost-of-equity",
    term: "Cost of Equity",
    category: "valuation",
    definition:
      "Cost of Equity is the expected return that equity investors demand as compensation for bearing the risk of owning a company's shares. It is typically estimated using the Capital Asset Pricing Model (CAPM): Cost of Equity = Risk-Free Rate + Beta × Equity Risk Premium. It is always higher than the cost of debt because equity holders are last in line in bankruptcy. For high-beta, volatile companies, the cost of equity can be substantial, directly reducing DCF valuations.",
    related: ["capm", "cost-of-debt", "wacc", "beta", "equity-risk-premium"],
  },
  {
    slug: "cost-of-debt",
    term: "Cost of Debt",
    category: "valuation",
    definition:
      "Cost of Debt is the effective after-tax interest rate a company pays on its total debt obligations. The tax adjustment — multiplying the pre-tax cost by (1 − tax rate) — reflects the fact that interest expense is tax-deductible, creating a debt tax shield. Companies with high credit ratings enjoy lower costs of debt, while distressed or highly levered firms face significantly higher borrowing costs. In WACC, the after-tax cost of debt is weighted by the proportion of debt in the capital structure.",
    related: ["wacc", "cost-of-equity", "debt-to-equity", "interest-coverage"],
  },
  {
    slug: "capm",
    term: "CAPM (Capital Asset Pricing Model)",
    category: "valuation",
    definition:
      "CAPM is the foundational model of modern finance that describes the relationship between systematic risk and expected return for an individual asset. The formula: Expected Return = Risk-Free Rate + β × (Market Return − Risk-Free Rate). The model assumes that only non-diversifiable (systematic) risk is priced — idiosyncratic risk can be diversified away. Developed independently by Sharpe, Lintner, and Mossin in the 1960s, CAPM remains the most widely used tool for estimating cost of equity despite empirical challenges, including the observation that low-beta stocks have historically outperformed the model's predictions.",
    related: ["cost-of-equity", "beta", "risk-free-rate", "equity-risk-premium", "alpha"],
  },
  {
    slug: "capm-implied-return",
    term: "CAPM Implied Return",
    category: "valuation",
    definition:
      "The CAPM implied return is the expected annual return for a stock derived from the CAPM formula, given its beta, the current risk-free rate, and the equity risk premium. It represents what the market 'should' demand to hold the stock, not what it will actually deliver. At EconoSift, this is displayed as one of the valuation models in the 8-model engine and compared against the stock's current valuation to gauge whether expected returns justify the price.",
    related: ["capm", "cost-of-equity", "expected-return", "axiom-fair-value"],
  },
  {
    slug: "gordon-growth-model",
    term: "Gordon Growth Model (GGM)",
    category: "valuation",
    definition:
      "The Gordon Growth Model values a stock as the present value of an infinite stream of dividends growing at a constant rate: P = D₁ / (r − g), where D₁ is next year's dividend, r is the required return, and g is the perpetual growth rate. It is the simplest dividend discount model and is most appropriate for mature, stable companies with predictable dividend policies. GGM is also used to calculate the terminal value in DCF models (Terminal Value = FCFₙ₊₁ / (WACC − g)). The model is extremely sensitive to the spread (r − g); small changes in this spread produce large changes in value.",
    related: ["ddm", "dcf", "terminal-growth-rate", "dividend-yield"],
  },
  {
    slug: "ddm",
    term: "DDM (Dividend Discount Model)",
    category: "valuation",
    definition:
      "The Dividend Discount Model values a stock as the sum of all expected future dividends, discounted back to present value at the required rate of return. The simplest form is the Gordon Growth Model (constant growth), but multi-stage DDMs allow for varying growth phases. DDM is theoretically elegant — a stock's value is ultimately the present value of the cash it returns to shareholders — but it is impractical for companies that do not pay dividends or have unpredictable dividend policies. At EconoSift, DDM is one of the 8 valuation models in the composite valuation engine.",
    related: ["gordon-growth-model", "dcf", "dividend-yield", "axiom-fair-value"],
  },
  {
    slug: "fcf",
    term: "FCF (Free Cash Flow)",
    category: "valuation",
    definition:
      "Free Cash Flow is the cash a company generates from operations after accounting for capital expenditures needed to maintain or expand its asset base: FCF = Operating Cash Flow − Capex. It represents the cash available to be returned to shareholders (via dividends or buybacks) or to pay down debt. FCF is often preferred over earnings for valuation because it is harder to manipulate through accounting choices. The FCF yield (FCF / Market Cap) is a key valuation ratio — a high FCF yield suggests the company is generating substantial cash relative to its price.",
    related: ["dcf", "fcf-yield", "ev-to-fcf", "nopat"],
  },
  {
    slug: "terminal-growth-rate",
    term: "Terminal Growth Rate",
    category: "valuation",
    definition:
      "The terminal growth rate is the perpetual annual growth rate assumed for cash flows beyond the explicit forecast period in a DCF model. It is typically set at or slightly below the long-run nominal GDP growth rate of the economy (~2–3% for developed markets). This assumption is critical because terminal value often constitutes 60–80% of total DCF value. An overly optimistic terminal growth rate can dramatically inflate the valuation, while an overly conservative one can make almost any company look overvalued.",
    related: ["dcf", "two-stage-dcf", "gordon-growth-model", "wacc"],
  },
  {
    slug: "enterprise-value",
    term: "Enterprise Value (EV)",
    category: "valuation",
    definition:
      "Enterprise Value represents the total theoretical takeover price of a company: EV = Market Cap + Total Debt + Preferred Stock + Minority Interest − Cash and Equivalents. It captures the value of the entire business attributable to all capital providers (debt and equity holders), making it the numerator in EV-based valuation multiples like EV/EBITDA and EV/FCF. EV is preferred over market cap for valuation comparisons because it neutralises differences in capital structure — two identical businesses financed differently will have different market caps but similar EVs.",
    related: ["equity-value", "ev-to-ebitda", "ev-to-fcf", "market-cap"],
  },
  {
    slug: "equity-value",
    term: "Equity Value",
    category: "valuation",
    definition:
      "Equity Value — also called market capitalisation — is the value attributable to common shareholders: Enterprise Value minus net debt (total debt minus cash). In DCF analysis, the discounted cash flows produce enterprise value, from which net debt is subtracted to arrive at equity value, which is then divided by shares outstanding to get the intrinsic value per share. Equity value is what shareholders actually own; enterprise value is what the whole business is worth.",
    related: ["enterprise-value", "intrinsic-value", "market-cap", "dcf"],
  },
  {
    slug: "intrinsic-value",
    term: "Intrinsic Value",
    category: "valuation",
    definition:
      "Intrinsic value is the estimated true per-share worth of a stock based on fundamental analysis — what a rational investor 'should' pay, independent of the current market price. Different models produce different intrinsic value estimates, which is why EconoSift aggregates 8 models into a composite fair value estimate. The gap between intrinsic value and market price is the upside/downside percentage. Warren Buffett popularised the concept, defining intrinsic value as 'the discounted value of the cash that can be taken out of a business during its remaining life.'",
    related: ["axiom-fair-value", "dcf", "upside-downside", "fair-value"],
  },
  {
    slug: "upside-downside",
    term: "Upside / Downside %",
    category: "valuation",
    definition:
      "Upside (or downside) is the percentage difference between a stock's estimated intrinsic value and its current market price: (Intrinsic Value − Price) / Price × 100. A positive number indicates the stock appears undervalued (upside potential); a negative number indicates it appears overvalued (downside risk). This single number is the most intuitive output of any valuation model — it answers 'by how much is this stock mispriced?' However, because intrinsic value estimates are uncertain, the upside/downside should always be considered alongside the model's sensitivity and the spread of estimates across different valuation approaches.",
    related: ["intrinsic-value", "axiom-fair-value", "dcf", "sensitivity-grid"],
  },
  {
    slug: "fair-value",
    term: "Fair Value / Fairly Valued",
    category: "valuation",
    definition:
      "A stock is considered 'fairly valued' when its market price is approximately in line with its estimated intrinsic value — typically defined as within ±10% of the intrinsic value estimate. This implies the market is efficiently pricing the company based on available information. Fair value is not a permanent state; new information, earnings reports, or macro shifts can rapidly move a stock from fairly valued to under- or overvalued. EconoSift's composite fair value estimate provides a weighted-average fair value estimate from 8 models plus CAPM.",
    related: ["intrinsic-value", "axiom-fair-value", "undervalued", "overvalued"],
  },
  {
    slug: "undervalued",
    term: "Undervalued",
    category: "valuation",
    definition:
      "A stock is undervalued when its market price trades below its estimated intrinsic value, suggesting the market is not fully recognising the company's worth. On EconoSift, this is typically defined as intrinsic value > 110% of market price (more than 10% upside). Value investors seek undervalued stocks, believing the market will eventually correct the mispricing. However, stocks can remain undervalued for extended periods; a catalyst — such as an earnings beat, buyback announcement, or macro shift — is often needed to close the gap.",
    related: ["overvalued", "fair-value", "intrinsic-value", "axiom-fair-value"],
  },
  {
    slug: "overvalued",
    term: "Overvalued",
    category: "valuation",
    definition:
      "A stock is overvalued when its market price exceeds its estimated intrinsic value, typically by more than 10%. This can result from excessive optimism, momentum buying, or a deterioration in fundamentals that the market has not yet priced in. Overvalued stocks are candidates for selling or shorting, though timing is difficult — overvalued stocks can become even more overvalued in the short term. EconoSift flags overvalued stocks through its 8-model valuation engine, with the composite fair value estimate providing the summary verdict.",
    related: ["undervalued", "fair-value", "intrinsic-value", "axiom-fair-value"],
  },
  {
    slug: "axiom-fair-value",
    term: "EconoSift Composite Fair Value",
    category: "valuation",
    definition:
      "EconoSift Composite Fair Value is the weighted-average composite valuation from EconoSift's 8-model engine plus the CAPM implied return model. Each model's output is weighted (configurable by the user's trust in each methodology), and the weighted average is compared against the current market price to produce the upside/downside percentage and a verdict — from 'Significantly Undervalued' to 'Significantly Overvalued.' The composite is designed to be more robust than any single model by diversifying across valuation philosophies: discounted cash flow, relative multiples, dividend-based, and risk-based approaches.",
    related: ["intrinsic-value", "valuation-engine", "upside-downside", "fair-value"],
  },
  {
    slug: "sensitivity-grid",
    term: "Sensitivity Heatmap/Grid",
    category: "valuation",
    definition:
      "A sensitivity grid (or heatmap) is a matrix that shows how a DCF valuation changes across a range of two key input assumptions — typically WACC on one axis and terminal growth rate (or FCF growth) on the other. Each cell shows the resulting intrinsic value or upside/downside % for that combination. This visualisation makes clear which regions of the assumption space support a 'buy' vs 'sell' decision and highlights how sensitive the valuation is to small changes in inputs. A 'flat' grid (similar values across cells) suggests the valuation is robust; a steep gradient indicates fragility.",
    related: ["dcf", "wacc", "terminal-growth-rate", "two-stage-dcf"],
  },
  {
    slug: "valuation-engine",
    term: "8-Model Valuation Engine",
    category: "valuation",
    definition:
      "EconoSift's 8-Model Valuation Engine is a suite of 8 distinct valuation methodologies — including DCF, DDM, GGM, relative multiples (P/E, EV/EBITDA, P/B, P/S), and FCF yield — plus the CAPM implied return, aggregated into a composite EconoSift Composite Fair Value. Each model is independently computed; if an input is missing (e.g., no dividends for DDM), that model is 'locked' and excluded from the composite. The engine provides a diversified valuation view, reducing reliance on any single methodology's assumptions.",
    related: ["axiom-fair-value", "dcf", "ddm", "gordon-growth-model", "locked-model"],
  },
  {
    slug: "locked-model",
    term: "Locked Model",
    category: "valuation",
    definition:
      "A locked model is a valuation model within the 8-model engine that could not be computed because one or more required inputs were missing or invalid. For example, the DDM locks if the company does not pay a dividend, and the DCF locks if free cash flow data is unavailable. Locked models are excluded from the composite fair value estimate so they do not distort the final estimate. EconoSift displays which models are locked and the reason why, ensuring transparency.",
    related: ["valuation-engine", "axiom-fair-value", "dcf", "ddm"],
  },
  {
    slug: "equity-risk-premium",
    term: "Damodaran ERP (Equity Risk Premium)",
    category: "valuation",
    definition:
      "The Equity Risk Premium is the excess return that investing in the stock market provides over a risk-free rate — it is the premium investors demand for bearing equity risk. Professor Aswath Damodaran of NYU Stern publishes widely-referenced ERP estimates by country, updated regularly. For the US, the implied ERP has typically ranged between 4% and 6%. The ERP is a critical input in CAPM and DCF: a higher ERP raises the cost of equity, reduces DCF values, and makes stocks look less attractive on a risk-adjusted basis.",
    related: ["capm", "cost-of-equity", "wacc", "risk-free-rate"],
  },
  {
    slug: "sector-multiples",
    term: "Sector Multiples",
    category: "valuation",
    definition:
      "Sector multiples are industry-average valuation ratios — such as EV/EBITDA, P/E, P/B, and P/S — used for relative valuation. Comparing a company's multiple to its sector average reveals whether it trades at a premium or discount to peers. A tech company trading at 20× EV/EBITDA might look expensive against the broad market but cheap against a sector average of 28×. Sector multiples are essential context for relative valuation — absolute multiples are meaningless without industry benchmarks.",
    related: ["ev-to-ebitda", "pe-ratio", "pb-ratio", "ps-ratio"],
  },

  // ════════════════════════════════════════════════════════════════
  // 4. Fundamental Financial Ratios
  // ════════════════════════════════════════════════════════════════
  {
    slug: "pe-ratio",
    term: "P/E (Price-to-Earnings)",
    category: "ratios",
    definition:
      "The P/E ratio is the most widely cited valuation multiple, calculated as stock price divided by earnings per share (EPS). The trailing P/E uses the last four quarters of reported earnings; the forward P/E uses analyst estimates for the next fiscal year. A high P/E suggests the market expects strong future growth; a low P/E may indicate undervaluation or fundamental problems. P/E is most meaningful within an industry — comparing a utility (P/E ~15) to a software company (P/E ~30) without context is misleading.",
    related: ["forward-pe", "trailing-eps", "forward-eps", "peg-ratio"],
  },
  {
    slug: "forward-pe",
    term: "Forward P/E",
    category: "ratios",
    definition:
      "Forward P/E uses estimated future earnings (typically the consensus analyst estimate for the next fiscal year) as the denominator instead of historical earnings. It is inherently forward-looking and can make high-growth companies appear cheaper than their trailing P/E suggests. However, forward P/E relies on analyst estimates, which can be overly optimistic or pessimistic. A large gap between trailing and forward P/E often signals expected earnings growth or a pending earnings decline.",
    related: ["pe-ratio", "trailing-eps", "forward-eps"],
  },
  {
    slug: "trailing-eps",
    term: "Trailing EPS",
    category: "ratios",
    definition:
      "Trailing Earnings Per Share is the sum of a company's reported (GAAP) earnings per share over the most recent four quarters. It is backward-looking and factual — unlike forward EPS, it contains no estimates. Trailing EPS is the denominator in the standard trailing P/E ratio. During periods of rapid growth or decline, trailing EPS can significantly lag the current earnings reality, making forward P/E a more relevant metric in those situations.",
    related: ["pe-ratio", "forward-pe", "forward-eps", "eps-growth"],
  },
  {
    slug: "forward-eps",
    term: "Forward EPS",
    category: "ratios",
    definition:
      "Forward EPS is the consensus analyst estimate of earnings per share for the next fiscal year. It is the denominator in forward P/E and is a key input for growth-investor valuation. Forward estimates are aggregated from sell-side analyst models and can be subject to systematic biases — analysts tend to start optimistic and revise downward as the reporting date approaches. The direction and magnitude of forward EPS revisions are themselves a signal (earnings revision momentum).",
    related: ["forward-pe", "trailing-eps", "pe-ratio", "earnings-revision"],
  },
  {
    slug: "pb-ratio",
    term: "P/B (Price-to-Book)",
    category: "ratios",
    definition:
      "Price-to-Book compares a stock's market price to its book value per share (total assets minus intangible assets and liabilities, divided by shares outstanding). A P/B below 1.0 suggests the stock trades below its accounting liquidation value — a classic deep-value signal. However, book value is an accounting construct that may not reflect the true economic value of a company's assets, especially for asset-light businesses like technology and services firms. P/B is most meaningful for financials, real estate, and capital-intensive industries.",
    related: ["book-value", "deep-value", "pe-ratio", "roe"],
  },
  {
    slug: "ev-to-ebitda",
    term: "EV/EBITDA",
    category: "ratios",
    definition:
      "EV/EBITDA is an enterprise-value-based multiple that compares the total value of a company (including debt) to its earnings before interest, taxes, depreciation, and amortisation. Because it uses EV rather than market cap, it is capital-structure-neutral — making it the preferred multiple for comparing companies with different debt levels. It is especially popular in M&A, private equity, and capital-intensive industries. A lower EV/EBITDA generally indicates a cheaper valuation, though industry norms vary widely.",
    related: ["enterprise-value", "ebitda", "ev-to-fcf", "fcf-yield"],
  },
  {
    slug: "ev-to-fcf",
    term: "EV/FCF",
    category: "ratios",
    definition:
      "EV/FCF relates enterprise value to free cash flow, providing a capital-structure-neutral measure of how cheap or expensive a company is relative to the cash it actually generates. Unlike EV/EBITDA, FCF accounts for capital expenditures and working-capital changes, making it a stricter test of value. A low EV/FCF (e.g., below 15) is generally attractive, but sector norms differ significantly. EV/FCF is preferred over P/E by many value investors because cash flow is harder to manipulate than earnings.",
    related: ["enterprise-value", "fcf", "fcf-yield", "ev-to-ebitda"],
  },
  {
    slug: "fcf-yield",
    term: "FCF Yield",
    category: "ratios",
    definition:
      "FCF Yield is free cash flow per share divided by the stock price — essentially the cash-flow analogue of earnings yield. It answers: 'If I bought this company today, what percentage of my investment would be returned as free cash flow each year?' A high FCF yield (e.g., > 8%) is attractive, especially when combined with revenue growth. FCF yield can also be compared directly to bond yields — if a stock's FCF yield exceeds the 10-year Treasury yield by a wide margin, it may be undervalued.",
    related: ["fcf", "ev-to-fcf", "dividend-yield", "earnings-yield"],
  },
  {
    slug: "ps-ratio",
    term: "P/S Ratio (Price-to-Sales)",
    category: "ratios",
    definition:
      "The Price-to-Sales ratio divides market cap by annual revenue (or equivalently, stock price by revenue per share). It is most useful for valuing companies that have no earnings — early-stage growth companies, cyclicals in a trough, or turnarounds. Revenue is harder to manipulate than earnings, making P/S a 'cleaner' top-line metric. However, P/S ignores profitability entirely — two companies with identical revenue can have vastly different economics, so P/S should always be paired with margin analysis.",
    related: ["pe-ratio", "gross-margin", "net-margin", "revenue-growth"],
  },
  {
    slug: "dividend-yield",
    term: "Dividend Yield",
    category: "ratios",
    definition:
      "Dividend yield is the annual dividend per share divided by the stock price, expressed as a percentage. It represents the cash return an investor receives from dividends alone, independent of capital appreciation. A high dividend yield can signal value — or it can signal distress if the stock price has fallen and the dividend is at risk of being cut. Sustainable dividend yield should be assessed against the payout ratio and free cash flow coverage. On EconoSift, the dividend yield shown is corrected for yfinance's occasionally mis-scaled raw data.",
    related: ["payout-ratio", "fcf-yield", "ddm", "gordon-growth-model"],
  },
  {
    slug: "roe",
    term: "ROE (Return on Equity)",
    category: "ratios",
    definition:
      "Return on Equity measures how efficiently a company generates profit from its shareholders' equity: ROE = Net Income / Shareholders' Equity. It is one of the most important profitability metrics — Warren Buffett has cited a consistently high ROE (above 15%) as a hallmark of a quality business. However, ROE can be inflated by high leverage (debt reduces equity, boosting ROE), so it should be analysed alongside ROA and ROIC, and decomposed via DuPont analysis to understand the drivers.",
    related: ["roa", "roic", "dupont-analysis", "nopat"],
  },
  {
    slug: "roa",
    term: "ROA (Return on Assets)",
    category: "ratios",
    definition:
      "Return on Assets = Net Income / Total Assets. It measures how efficiently a company uses its entire asset base — not just equity — to generate profit. ROA is a cleaner measure of operational efficiency than ROE because it is not affected by leverage. Asset-heavy industries (utilities, industrials) naturally have lower ROA than asset-light ones (software, services). A declining ROA over time may indicate poor capital allocation or deteriorating competitive advantage.",
    related: ["roe", "roic", "asset-turnover", "nopat"],
  },
  {
    slug: "roic",
    term: "ROIC (Return on Invested Capital)",
    category: "ratios",
    definition:
      "ROIC = NOPAT / Invested Capital, where Invested Capital = Total Debt + Equity − Cash. It is the most comprehensive profitability metric — it measures how efficiently a company allocates capital to generate returns above its cost of capital. A company with ROIC > WACC is creating value; ROIC < WACC is destroying value. ROIC is central to EconoSift's quality growth screening preset and is considered by many professional investors to be the single most important measure of business quality.",
    related: ["nopat", "wacc", "roe", "invested-capital"],
  },
  {
    slug: "nopat",
    term: "NOPAT (Net Operating Profit After Tax)",
    category: "ratios",
    definition:
      "NOPAT is operating profit (EBIT) adjusted for taxes: NOPAT = EBIT × (1 − Tax Rate). It represents the profit a company would generate if it had no debt — that is, the earnings available to all capital providers. NOPAT is the numerator in ROIC and is preferred over net income for capital-efficiency analysis because it excludes the effects of capital structure. A company with high net income but low NOPAT may be benefiting from leverage rather than operational excellence.",
    related: ["roic", "ebitda", "invested-capital", "operating-margin"],
  },
  {
    slug: "invested-capital",
    term: "Invested Capital",
    category: "ratios",
    definition:
      "Invested Capital is the total amount of money deployed in a business by both equity holders and lenders: Invested Capital = Total Debt + Shareholders' Equity − Cash and Equivalents. It is the denominator in ROIC. Companies with high invested capital relative to NOPAT have low ROIC, indicating poor capital efficiency. The concept is that cash sitting idle is not 'invested,' so it is subtracted out.",
    related: ["roic", "nopat", "enterprise-value", "wacc"],
  },
  {
    slug: "gross-margin",
    term: "Gross Margin",
    category: "ratios",
    definition:
      "Gross Margin = (Revenue − Cost of Goods Sold) / Revenue. It measures how much of each revenue dollar remains after paying the direct costs of producing the product or service. A high and stable gross margin indicates pricing power and competitive advantage; a declining gross margin suggests rising input costs or pricing pressure. Software companies typically have gross margins above 70%, while retailers may be below 30%. Gross margin trends are often a leading indicator of future profitability.",
    related: ["operating-margin", "net-margin", "revenue-growth"],
  },
  {
    slug: "operating-margin",
    term: "Operating Margin",
    category: "ratios",
    definition:
      "Operating Margin = Operating Income / Revenue. It measures profitability from core business operations before interest and taxes, capturing both gross margin performance and operating expense efficiency. It is a purer measure of business performance than net margin because it excludes financing decisions (interest) and tax jurisdiction effects. Comparing operating margins across peers reveals who has the strongest business model within an industry.",
    related: ["gross-margin", "net-margin", "nopat", "ebitda"],
  },
  {
    slug: "net-margin",
    term: "Net Margin",
    category: "ratios",
    definition:
      "Net Margin = Net Income / Revenue. It is the bottom-line profitability metric — how much of each revenue dollar becomes profit after all expenses, interest, and taxes. While the most comprehensive profitability ratio, net margin can be distorted by one-time items, tax rate changes, and debt levels. It is best analysed as a trend over time and in conjunction with gross and operating margins to understand where in the income statement margin compression is occurring.",
    related: ["gross-margin", "operating-margin", "roe", "dupont-analysis"],
  },
  {
    slug: "revenue-growth",
    term: "Revenue Growth (%)",
    category: "ratios",
    definition:
      "Revenue Growth is the year-over-year percentage change in a company's top-line sales. It is the most fundamental growth metric — without revenue growth, profit growth is eventually capped by margin expansion limits. Revenue growth can be organic (from existing operations) or inorganic (from acquisitions). Analysts scrutinise the composition: organic growth is more highly valued because it reflects the underlying business momentum, while acquisition-driven growth can mask stagnation in the core business.",
    related: ["eps-growth", "gross-margin", "net-margin"],
  },
  {
    slug: "eps-growth",
    term: "EPS Growth (%)",
    category: "ratios",
    definition:
      "EPS Growth is the year-over-year percentage change in earnings per share. It can exceed revenue growth when margins expand or when share count decreases due to buybacks — and it can lag revenue growth when margins compress or dilution occurs. Sustainable EPS growth comes from revenue growth and margin improvement; EPS growth driven solely by buybacks is generally valued less highly. EPS growth is a key input into PEG ratio and growth-at-a-reasonable-price (GARP) screens.",
    related: ["revenue-growth", "pe-ratio", "forward-eps", "peg-ratio"],
  },
  {
    slug: "debt-to-equity",
    term: "Debt-to-Equity (D/E)",
    category: "ratios",
    definition:
      "The Debt-to-Equity ratio = Total Debt / Shareholders' Equity. It is the most common leverage metric — a D/E above 2.0 indicates the company is financed twice as much by debt as by equity. High D/E can amplify returns in good times but increases bankruptcy risk in downturns. Appropriate D/E levels vary by industry: utilities and telecoms often carry D/E > 2.0 due to stable cash flows, while technology companies frequently have D/E < 0.5. D/E should be assessed alongside interest coverage to gauge whether the debt load is sustainable.",
    related: ["debt-to-assets", "interest-coverage", "net-debt-to-ebitda"],
  },
  {
    slug: "debt-to-assets",
    term: "Debt-to-Assets",
    category: "ratios",
    definition:
      "Debt-to-Assets = Total Debt / Total Assets, showing what fraction of the company's asset base is financed by debt. A ratio above 0.5 means more than half of assets are debt-financed. This metric is broader than D/E because it includes all assets (not just equity) and is commonly used in credit analysis. A rising debt-to-assets ratio over time signals increasing financial risk.",
    related: ["debt-to-equity", "interest-coverage", "net-debt-to-ebitda"],
  },
  {
    slug: "interest-coverage",
    term: "Interest Coverage",
    category: "ratios",
    definition:
      "Interest Coverage = Operating Income / Interest Expense. It measures how easily a company can pay interest on its outstanding debt from its operating earnings. A ratio below 1.0 means the company is not generating enough operating income to cover its interest payments — a red flag. Most healthy companies maintain coverage above 3.0×. Creditors and bond investors watch this ratio closely; a declining interest coverage ratio often precedes credit rating downgrades.",
    related: ["debt-to-equity", "debt-to-assets", "net-debt-to-ebitda"],
  },
  {
    slug: "net-debt-to-ebitda",
    term: "Net Debt / EBITDA",
    category: "ratios",
    definition:
      "Net Debt / EBITDA = (Total Debt − Cash) / EBITDA. It is the most commonly used leverage ratio in credit analysis and M&A, measuring how many years of earnings it would take to pay off all net debt. A ratio below 2.0× is considered conservative; above 4.0× is considered highly leveraged. Unlike D/E (an accounting ratio), Net Debt/EBITDA is a cash-flow-based measure and is preferred by credit rating agencies.",
    related: ["debt-to-equity", "interest-coverage", "ebitda", "enterprise-value"],
  },
  {
    slug: "current-ratio",
    term: "Current Ratio",
    category: "ratios",
    definition:
      "Current Ratio = Current Assets / Current Liabilities. It measures a company's ability to pay its short-term obligations (due within one year) with its short-term assets. A ratio below 1.0 indicates potential liquidity problems. While a ratio above 2.0 is traditionally considered healthy, too high a ratio can indicate inefficient use of assets (e.g., excess inventory or idle cash). The current ratio is a blunt tool — it treats all current assets as equally liquid, which is rarely true.",
    related: ["quick-ratio", "cash-ratio", "operating-cf-ratio"],
  },
  {
    slug: "quick-ratio",
    term: "Quick Ratio",
    category: "ratios",
    definition:
      "Quick Ratio = (Current Assets − Inventory) / Current Liabilities. Also called the acid-test ratio, it is a stricter liquidity measure than the current ratio because inventory — the least liquid current asset — is excluded. A quick ratio below 1.0 suggests the company could not cover its immediate liabilities without selling inventory. It is especially relevant for industries where inventory is slow-moving or subject to obsolescence.",
    related: ["current-ratio", "cash-ratio", "operating-cf-ratio"],
  },
  {
    slug: "cash-ratio",
    term: "Cash Ratio",
    category: "ratios",
    definition:
      "Cash Ratio = Cash and Cash Equivalents / Current Liabilities. It is the most conservative liquidity metric, considering only the most liquid assets. A cash ratio above 0.5 is generally strong, but excessively high cash ratios suggest poor capital allocation — cash earning near-zero returns is a drag on ROE. The cash ratio is most useful during credit crunches when even receivables become difficult to collect quickly.",
    related: ["current-ratio", "quick-ratio"],
  },
  {
    slug: "operating-cf-ratio",
    term: "Operating CF Ratio",
    category: "ratios",
    definition:
      "Operating Cash Flow Ratio = Operating Cash Flow / Current Liabilities. Unlike the current and quick ratios (balance-sheet snapshots), this ratio uses cash flow from operations, showing how many times over current liabilities can be covered by actual cash generation. It is less susceptible to accounting manipulation than balance-sheet ratios. A ratio consistently above 1.0 indicates strong liquidity from ongoing operations.",
    related: ["current-ratio", "quick-ratio", "fcf"],
  },
  {
    slug: "asset-turnover",
    term: "Asset Turnover",
    category: "ratios",
    definition:
      "Asset Turnover = Revenue / Total Assets. It measures how efficiently a company uses its assets to generate sales — the 'asset sweating' ratio. A high turnover (e.g., > 1.0 for industrial companies) means the company generates significant revenue per dollar of assets. Asset turnover varies widely by industry: retailers have high turnover, while utilities and infrastructure companies have low turnover. It is a key component of DuPont analysis.",
    related: ["roe", "dupont-analysis", "inventory-turnover"],
  },
  {
    slug: "inventory-turnover",
    term: "Inventory Turnover",
    category: "ratios",
    definition:
      "Inventory Turnover = Revenue / Average Inventory (or COGS / Average Inventory). It measures how many times a company sells through its inventory in a period. High turnover indicates strong demand and efficient inventory management; low turnover may signal obsolescence, weak demand, or overstocking. The optimal level varies by product type — a grocery chain will have much higher turnover than a luxury goods retailer.",
    related: ["asset-turnover", "dio", "cash-conversion-cycle"],
  },
  {
    slug: "receivables-turnover",
    term: "Receivables Turnover",
    category: "ratios",
    definition:
      "Receivables Turnover = Revenue / Average Accounts Receivable. It measures how quickly a company collects cash from customers. A high turnover means customers pay quickly; a low or declining turnover may indicate loosening credit standards or collection problems. It is closely related to Days Sales Outstanding (DSO = 365 / Receivables Turnover).",
    related: ["dso", "cash-conversion-cycle", "asset-turnover"],
  },
  {
    slug: "short-float",
    term: "Short % of Float (Short Float)",
    category: "ratios",
    definition:
      "Short float is the percentage of a company's publicly available shares (the float) that have been sold short by investors betting on a price decline. A short float above 20% is considered high and can set the stage for a short squeeze — forced buying by shorts to cover their positions — if positive news triggers a price spike. High short interest reflects deep market scepticism and is often concentrated in companies with deteriorating fundamentals, controversial accounting, or binary-event risk.",
    related: ["short-ratio", "short-squeeze", "insider-buy-sell"],
  },
  {
    slug: "short-ratio",
    term: "Short Ratio (Days to Cover)",
    category: "ratios",
    definition:
      "The short ratio (also called days to cover) = Short Interest / Average Daily Volume. It measures how many trading days it would take for all short sellers to close their positions at the average daily volume. A ratio above 5 days is high and indicates that a short squeeze could be severe if buying pressure forces shorts to cover. The short ratio is a better measure of short-squeeze risk than short float alone because it incorporates liquidity.",
    related: ["short-float", "volume-ratio", "average-volume"],
  },
  {
    slug: "book-value",
    term: "Book Value",
    category: "ratios",
    definition:
      "Book value is the net asset value of a company as recorded on its balance sheet: Total Assets − Intangible Assets − Total Liabilities. It represents the accounting value that would theoretically remain for shareholders if the company were liquidated at balance-sheet values. Book value is the denominator in the P/B ratio. For asset-heavy industries, book value is a reasonable floor for valuation; for technology and service companies with significant intangible assets (brands, patents, software), book value drastically understates true economic worth.",
    related: ["pb-ratio", "market-cap", "tangible-book-value"],
  },
  {
    slug: "market-cap",
    term: "Market Cap (Market Capitalisation)",
    category: "ratios",
    definition:
      "Market capitalisation is the total market value of a company's outstanding shares: Share Price × Shares Outstanding. It is the most basic measure of a company's size and the starting point for most valuation metrics. Companies are classified by market cap: mega-cap (>$200B), large-cap ($10B–$200B), mid-cap ($2B–$10B), small-cap ($300M–$2B), and micro-cap (<$300M). Market cap is distinct from enterprise value, which also accounts for debt and cash.",
    related: ["enterprise-value", "equity-value", "book-value", "sp-500"],
  },
  {
    slug: "average-volume",
    term: "Average Volume",
    category: "ratios",
    definition:
      "Average volume is the mean number of shares traded per day over a specified period — typically the 20-day or 3-month average. It is a key liquidity metric: stocks with low average volume can be difficult to enter or exit without moving the price (slippage). Institutional investors often require a minimum average daily volume (e.g., $50M traded daily) for inclusion in their portfolios. Spikes in volume relative to the average can signal institutional activity or news-driven interest.",
    related: ["volume-ratio", "short-ratio", "liquidity"],
  },
  {
    slug: "volume-ratio",
    term: "Volume Ratio",
    category: "ratios",
    definition:
      "Volume Ratio = Current Day's Volume / Average Daily Volume. A ratio above 2.0 indicates 'unusual volume' — trading activity significantly above normal levels, often associated with earnings releases, news events, or institutional accumulation/distribution. It is a popular screener criterion because unusual volume often precedes significant price moves. The EconoSift screener includes an Unusual Volume preset that flags stocks with volume > 2× the 20-day average.",
    related: ["average-volume", "short-ratio", "obv"],
  },

  // ════════════════════════════════════════════════════════════════
  // 5. Risk Metrics
  // ════════════════════════════════════════════════════════════════
  {
    slug: "var",
    term: "Value at Risk (VaR)",
    category: "risk",
    definition:
      "Value at Risk estimates the maximum expected loss over a given time horizon at a specified confidence level. A daily VaR 95% of −2.5% means there is a 5% chance of losing more than 2.5% on any given day, based on historical return distributions. VaR is calculated using three methods: parametric (assumes normal distribution), historical (ranks actual past returns), and Monte Carlo simulation. While widely used by banks and regulators, VaR has a critical weakness — it says nothing about how bad losses can be beyond the threshold, which is why CVaR (Expected Shortfall) is often preferred.",
    related: ["cvar", "sharpe-ratio", "sortino-ratio", "maximum-drawdown", "monte-carlo"],
  },
  {
    slug: "cvar",
    term: "CVaR (Conditional VaR) / Expected Shortfall",
    category: "risk",
    definition:
      "CVaR (also called Expected Shortfall) answers the question VaR cannot: 'If things go wrong beyond the VaR threshold, how bad will it be?' It is the average of all losses that exceed the VaR level. For example, if VaR 95% is −3%, CVaR 95% might be −5%, meaning that in the worst 5% of days, the average loss is 5%. Regulators increasingly prefer CVaR over VaR because it is a 'coherent' risk measure — it accounts for tail risk and satisfies sub-additivity (diversification always reduces risk).",
    related: ["var", "maximum-drawdown", "tail-risk", "monte-carlo"],
  },
  {
    slug: "sharpe-ratio",
    term: "Sharpe Ratio",
    category: "risk",
    definition:
      "The Sharpe Ratio — developed by Nobel laureate William F. Sharpe — measures risk-adjusted return: (Portfolio Return − Risk-Free Rate) / Portfolio Volatility. It answers: 'How much excess return am I getting per unit of risk?' A Sharpe above 1.0 is considered good; above 2.0 is excellent. The Sharpe ratio's main weakness is that it penalises upside volatility equally with downside — a strategy with occasional large positive returns can have a deceptively low Sharpe. The Sortino ratio addresses this by using only downside deviation.",
    related: ["sortino-ratio", "treynor-ratio", "calmar-ratio", "omega-ratio", "risk-free-rate"],
  },
  {
    slug: "sortino-ratio",
    term: "Sortino Ratio",
    category: "risk",
    definition:
      "The Sortino ratio is a modification of the Sharpe ratio that uses only downside deviation (volatility of negative returns) in the denominator instead of total volatility. This makes it more relevant for investors who do not consider upside volatility to be 'risk.' A high Sortino relative to Sharpe indicates the strategy has had mostly positive volatility — large gains rather than large losses. It is named after Frank A. Sortino and is widely used in hedge fund and alternatives evaluation.",
    related: ["sharpe-ratio", "var", "cvar", "downside-deviation"],
  },
  {
    slug: "beta",
    term: "Beta (β)",
    category: "risk",
    definition:
      "Beta measures a stock's systematic risk — its sensitivity to movements in the overall market. A beta of 1.0 means the stock tends to move in lockstep with the market; beta > 1 implies amplification (a 1% market move translates to >1% stock move); beta < 1 implies dampening. Beta is the key input in CAPM and is calculated by regressing the stock's returns against the benchmark's returns. Beta is not static — it varies over time and with different lookback periods, which is why EconoSift provides rolling beta metrics.",
    related: ["alpha", "capm", "systematic-risk", "r-squared", "sharpe-ratio"],
  },
  {
    slug: "alpha",
    term: "Alpha (Jensen's Alpha)",
    category: "risk",
    definition:
      "Alpha is the excess return of an investment relative to what CAPM predicts based on its beta. A positive alpha means the investment outperformed after adjusting for market risk — it generated 'skill-based' return. Annualised alpha = Daily Alpha × 252. Alpha is the holy grail of active management, but distinguishing true skill from luck is statistically difficult — most apparent alpha disappears after accounting for additional risk factors (Fama-French) or adjusting for survivorship bias.",
    related: ["beta", "capm", "fama-french", "r-squared", "sharpe-ratio"],
  },
  {
    slug: "treynor-ratio",
    term: "Treynor Ratio",
    category: "risk",
    definition:
      "The Treynor Ratio = (Return − Risk-Free Rate) / Beta. Unlike the Sharpe ratio (which divides by total volatility), the Treynor ratio divides by systematic risk (beta). It is appropriate for evaluating diversified portfolios where idiosyncratic risk has been largely eliminated — only the non-diversifiable market risk remains. For individual stocks or concentrated portfolios, the Sharpe ratio is more appropriate because total risk matters.",
    related: ["sharpe-ratio", "sortino-ratio", "beta", "capm"],
  },
  {
    slug: "calmar-ratio",
    term: "Calmar Ratio",
    category: "risk",
    definition:
      "The Calmar Ratio = Annualised Return / Maximum Drawdown (absolute value). It is a risk-adjusted return measure focused on worst-case loss rather than volatility. A Calmar above 1.0 means the annual return exceeds the maximum historical drawdown. It is popular among CTA and trend-following strategies where deep drawdowns are the primary risk concern. The ratio is named after the California Managed Accounts Reports where it was popularised.",
    related: ["maximum-drawdown", "sharpe-ratio", "sortino-ratio", "omega-ratio"],
  },
  {
    slug: "omega-ratio",
    term: "Omega Ratio",
    category: "risk",
    definition:
      "The Omega Ratio is the probability-weighted ratio of gains to losses relative to a threshold return (often the risk-free rate or zero). Unlike the Sharpe ratio, Omega uses the entire return distribution — it captures skewness and kurtosis, not just mean and variance. An Omega > 1 means gains outweigh losses in probability-weighted terms. It is considered superior to Sharpe for non-normal return distributions, which are common in options strategies and alternative investments.",
    related: ["sharpe-ratio", "sortino-ratio", "calmar-ratio"],
  },
  {
    slug: "maximum-drawdown",
    term: "Maximum Drawdown",
    category: "risk",
    definition:
      "Maximum Drawdown is the largest peak-to-trough decline in portfolio or asset value over a specified period, expressed as a percentage. It measures the worst possible outcome an investor would have experienced — buying at the peak and selling at the trough. A 50% drawdown requires a 100% gain to recover. MDD is arguably the most psychologically relevant risk metric because it directly quantifies the pain of worst-case timing.",
    related: ["calmar-ratio", "underwater-curve", "var", "cvar"],
  },
  {
    slug: "annualised-volatility",
    term: "Annualised Volatility",
    category: "risk",
    definition:
      "Annualised volatility is the standard deviation of daily returns multiplied by √252 (the typical number of US trading days per year). It is the most common measure of total risk and the denominator in the Sharpe ratio. A volatility of 20% means, under a normal distribution assumption, roughly 68% of annual returns should fall within ±20% of the mean. Real-world returns exhibit fatter tails than the normal distribution implies, so volatility should not be the sole risk measure.",
    related: ["sharpe-ratio", "sortino-ratio", "beta", "garch"],
  },
  {
    slug: "annualised-return",
    term: "Annualised Return",
    category: "risk",
    definition:
      "Annualised return is the geometric average annual return over the period, compounding daily returns: (1 + Total Return)^(252/n) − 1. It standardises returns to a per-year basis for comparison across different holding periods. A 10% return over 6 months annualises to roughly 21%, assuming the same pace continues — which may or may not be realistic. Annualised return should not be confused with the simple arithmetic average of annual returns.",
    related: ["annualised-volatility", "sharpe-ratio", "total-return"],
  },
  {
    slug: "daily-mean-return",
    term: "Daily Mean Return",
    category: "risk",
    definition:
      "The daily mean return is the simple arithmetic average of all daily log returns in the analysis period. It is the raw input that gets annualised (× 252) to produce the annualised return estimate. Because it uses log returns, it is additive across periods. A positive daily mean indicates an upward drift; a negative one indicates a declining asset.",
    related: ["annualised-return", "annualised-volatility", "log-returns"],
  },
  {
    slug: "systematic-risk",
    term: "Systematic Variance / Risk",
    category: "risk",
    definition:
      "Systematic risk (or systematic variance) is the portion of an asset's total risk that is attributable to market-wide factors — it cannot be diversified away. It equals β² × Market Variance. In CAPM, only systematic risk is priced because idiosyncratic risk can be eliminated through diversification. The systematic risk percentage (systematic variance / total variance) = R² from the beta regression — a high R² means most of the stock's moves are market-driven.",
    related: ["idiosyncratic-risk", "beta", "r-squared", "capm"],
  },
  {
    slug: "idiosyncratic-risk",
    term: "Idiosyncratic Variance / Risk",
    category: "risk",
    definition:
      "Idiosyncratic risk is the portion of an asset's total variance that is unique to that asset and uncorrelated with the market. It equals Total Variance − Systematic Variance. Unlike systematic risk, idiosyncratic risk can be diversified away by holding a sufficiently broad portfolio. In CAPM, idiosyncratic risk is not compensated with higher expected return because rational investors would diversify it away rather than demand a premium for bearing it.",
    related: ["systematic-risk", "beta", "r-squared", "diversification"],
  },
  {
    slug: "r-squared",
    term: "R² (R-Squared)",
    category: "risk",
    definition:
      "R-squared in a risk context is the proportion of a stock's return variance explained by movements in the benchmark (typically the S&P 500). It ranges from 0 to 1: a value of 0.85 means 85% of the stock's price movement is market-driven and 15% is idiosyncratic. High R² stocks behave like 'the market on steroids' (if high beta) or 'the market diluted' (if low beta). Low R² stocks march to their own beat and offer more diversification benefit.",
    related: ["beta", "systematic-risk", "idiosyncratic-risk", "capm"],
  },
  {
    slug: "rolling-metrics",
    term: "Rolling Metrics",
    category: "risk",
    definition:
      "Rolling metrics compute risk statistics (volatility, beta, Sharpe, VaR, drawdown) over a sliding window — typically 20D, 60D, 120D, or 252D — that advances one period at a time. This produces a time series of each metric, revealing how risk has evolved rather than just a single point-in-time number. For example, rolling 60-day beta shows when a stock became more or less market-sensitive over time. EconoSift's Risk page provides rolling metrics across multiple windows for any ticker.",
    related: ["beta", "annualised-volatility", "sharpe-ratio", "var"],
  },
  {
    slug: "correlation-matrix",
    term: "Correlation Matrix",
    category: "risk",
    definition:
      "A correlation matrix is a table showing pairwise Pearson correlation coefficients between all assets in a portfolio, with values ranging from −1 (perfectly opposite) to +1 (perfectly together). It is the foundational input for portfolio diversification — assets with low or negative correlations provide greater diversification benefits. Correlations are not stable: they tend to rise during crises (the 'correlation to one' phenomenon), precisely when diversification is most needed. EconoSift's Risk page provides a visual colour-coded correlation heatmap.",
    related: ["pearson-correlation", "diversification", "efficient-frontier", "cointegration"],
  },
  {
    slug: "garch",
    term: "GARCH(1,1)",
    category: "risk",
    definition:
      "GARCH (Generalised Autoregressive Conditional Heteroskedasticity) is a statistical model that forecasts volatility by accounting for volatility clustering — the empirical observation that high-volatility periods tend to follow high-volatility periods, and low follows low. GARCH(1,1) has three parameters: omega (constant), alpha (response to recent shocks), and beta (persistence of past volatility). A high beta (close to 1) means volatility shocks decay slowly. GARCH is widely used in options pricing, VaR estimation, and risk management to produce forward-looking volatility estimates.",
    related: ["garch-alpha", "garch-beta", "garch-omega", "forecast-vol", "volatility", "hurst"],
  },
  {
    slug: "garch-omega",
    term: "Omega (GARCH Constant)",
    category: "risk",
    definition:
      "In GARCH(1,1), omega (ω) is the constant term representing the long-run unconditional variance floor — the minimum level volatility reverts to when there are no recent shocks. It is typically a small positive number. Omega divided by (1 − α − β) gives the long-run average variance. A higher omega indicates a structurally more volatile asset.",
    related: ["garch", "garch-alpha", "garch-beta", "forecast-vol"],
  },
  {
    slug: "garch-alpha",
    term: "Alpha (GARCH Shock Coefficient)",
    category: "risk",
    definition:
      "In GARCH(1,1), alpha (α) measures how much yesterday's squared return (the 'shock') feeds into today's variance forecast. A high alpha means volatility reacts quickly to new information — the model is 'jumpy.' Alpha + Beta must be < 1 for the variance process to be stationary (mean-reverting); if their sum is close to 1, volatility shocks are highly persistent.",
    related: ["garch", "garch-beta", "garch-omega", "forecast-vol"],
  },
  {
    slug: "garch-beta",
    term: "Beta (GARCH Persistence)",
    category: "risk",
    definition:
      "In GARCH(1,1), beta (β) measures how much of yesterday's variance forecast persists into today. A beta near 0.9 means volatility is highly persistent — once volatility spikes, it takes many periods to decay back to the long-run mean. Financial time series typically exhibit beta in the 0.85–0.95 range. The sum α + β measures overall volatility persistence.",
    related: ["garch", "garch-alpha", "garch-omega", "forecast-vol"],
  },
  {
    slug: "forecast-vol",
    term: "Forecast Vol (GARCH)",
    category: "risk",
    definition:
      "Forecast volatility from a GARCH model is the one-step-ahead conditional volatility prediction — the model's best estimate of tomorrow's volatility given today's information. It is forward-looking, unlike historical volatility which is purely backward-looking. GARCH forecasts adapt quickly to market conditions: a large price move today pushes tomorrow's forecast up automatically. At EconoSift, GARCH forecasts are computed on the Risk page via the 🟡 Calculate button.",
    related: ["garch", "volatility", "var", "options-iv"],
  },
  {
    slug: "hurst",
    term: "Hurst Exponent",
    category: "risk",
    definition:
      "The Hurst exponent (H) measures the long-term memory of a time series. H < 0.5 indicates a mean-reverting series (anti-persistent); H ≈ 0.5 indicates a random walk (geometric Brownian motion); H > 0.5 indicates a trending series (persistent). Financial series often show H > 0.5 over short horizons (trending) and H < 0.5 over long horizons (mean-reverting). The Hurst exponent is used in fractal market analysis and can inform strategy selection — trend-following suits persistent series, mean-reversion suits anti-persistent ones.",
    related: ["garch", "cointegration", "mean-reversion", "ou-process"],
  },
  {
    slug: "ou-process",
    term: "Ornstein-Uhlenbeck (OU) Process",
    category: "risk",
    definition:
      "The Ornstein-Uhlenbeck process is a mean-reverting stochastic process widely used in pairs trading and interest-rate modelling. It has three parameters: theta (mean-reversion speed), mu (long-run mean), and sigma (volatility). The half-life — the time for a deviation to revert halfway to the mean — is ln(2)/theta. Pairs with short half-lives (a few days) are good candidates for mean-reversion strategies. EconoSift's Risk page fits OU processes to pairs and reports the parameters.",
    related: ["cointegration", "hurst", "half-life", "theta-ou", "mu-ou"],
  },
  {
    slug: "theta-ou",
    term: "Theta (OU Mean-Reversion Speed)",
    category: "risk",
    definition:
      "In the OU process, theta (θ) is the speed of mean reversion — how strongly the process is pulled back toward its long-run mean. A higher theta means faster reversion. Theta is estimated by regressing changes in the spread on the lagged spread level. A negative and statistically significant theta confirms mean reversion.",
    related: ["ou-process", "half-life", "mu-ou", "cointegration"],
  },
  {
    slug: "mu-ou",
    term: "Mu (OU Long-Run Mean)",
    category: "risk",
    definition:
      "In the OU process, mu (μ) is the long-run mean level to which the process reverts. For a pairs-trading spread, mu is typically near zero — the historical average spread. Trading signals are generated when the spread deviates significantly from mu: go long the spread when it is far below mu (expecting it to rise back), and short when far above.",
    related: ["ou-process", "theta-ou", "half-life", "cointegration"],
  },
  {
    slug: "half-life",
    term: "Half-Life (OU)",
    category: "risk",
    definition:
      "Half-life is the time (in trading days) for a deviation from the OU long-run mean to revert halfway. Calculated as ln(2) / θ. A half-life of 5 days means if the spread is $2 away from its mean, it is expected to close to $1 away in about 5 days. Short half-lives are attractive for mean-reversion trading; long half-lives suggest the deviation may persist and the pair may not be suitable for mean-reversion strategies.",
    related: ["ou-process", "theta-ou", "mu-ou"],
  },
  {
    slug: "cointegration",
    term: "Cointegration Test (Engle-Granger)",
    category: "risk",
    definition:
      "Cointegration tests whether two or more non-stationary time series share a long-run equilibrium relationship — meaning a linear combination of them is stationary. This is the statistical foundation of pairs trading. The Engle-Granger two-step method regresses one series on the other, then tests the residuals for stationarity (using ADF test). If the residuals are stationary, the series are cointegrated. The regression coefficient gives the hedge ratio. Cointegration is related to but distinct from correlation: two series can be highly correlated without being cointegrated, and vice versa.",
    related: ["hedge-ratio", "spread-cointegration", "ou-process", "correlation", "hurst"],
  },
  {
    slug: "hedge-ratio",
    term: "Hedge Ratio (Cointegration)",
    category: "risk",
    definition:
      "The hedge ratio is the coefficient from regressing one asset's price on another's in a cointegrated pair. It tells you how many units of asset B to hold against one unit of asset A to create a stationary spread. For example, if regressing KO on PEP gives a coefficient of 1.2, you would short 1.2 shares of PEP for every share of KO you buy to create a market-neutral spread.",
    related: ["cointegration", "spread-cointegration", "pairs-trading"],
  },
  {
    slug: "spread-cointegration",
    term: "Spread (Cointegration)",
    category: "risk",
    definition:
      "In pairs trading, the spread is the residual series from the cointegration regression: Asset A price − Hedge Ratio × Asset B price. A stationary spread (confirmed by the ADF test) oscillates around zero, generating trading signals when it deviates significantly. Traders go long the spread (buy A, short B) when it is unusually low and short the spread when it is unusually high, betting on reversion.",
    related: ["cointegration", "hedge-ratio", "ou-process", "mean-reversion"],
  },
  {
    slug: "monte-carlo-risk",
    term: "Monte Carlo Simulation (Risk)",
    category: "risk",
    definition:
      "Monte Carlo simulation in risk analysis generates thousands of possible future price paths by randomly sampling from the historical return distribution (or a fitted parametric distribution), then aggregates outcomes to estimate worst-case losses, value distributions, and probability of hitting specific thresholds. Unlike parametric VaR, Monte Carlo does not assume normality — it can capture skew and fat tails from the empirical distribution. The main limitation is that it assumes the future will resemble the past, which may not hold during structural breaks.",
    related: ["var", "cvar", "stress-testing", "monte-carlo-portfolio"],
  },
  {
    slug: "stress-testing",
    term: "Stress Testing",
    category: "risk",
    definition:
      "Stress testing replays a portfolio through an actual historical crisis period — such as the 2008 Financial Crisis, the 2020 COVID crash, the 2022 rate-hike cycle, or the dot-com bust — to see how it would have performed. Unlike statistical models, stress tests use real data from extreme events, capturing correlations and liquidity dynamics that models miss. EconoSift offers four historical stress scenarios on the Risk page via the 🟡 Calculate button.",
    related: ["var", "cvar", "monte-carlo-risk", "maximum-drawdown"],
  },

  // ════════════════════════════════════════════════════════════════
  // 6. Options & Implied Volatility
  // ════════════════════════════════════════════════════════════════
  {
    slug: "implied-volatility",
    term: "IV (Implied Volatility)",
    category: "options",
    definition:
      "Implied volatility is the market's forecast of future volatility extracted from option prices by solving the Black-Scholes (or other pricing model) for the volatility parameter that makes the model price equal the market price. It reflects the collective expectations and uncertainty of option market participants. IV typically exceeds realised volatility — the difference is the volatility risk premium that option sellers earn. IV is not constant across strikes (the 'smile') or expirations (the 'term structure').",
    related: ["iv-rank", "iv-percentile", "black-scholes", "iv-smile", "iv-term-structure"],
  },
  {
    slug: "iv-rank",
    term: "IV Rank",
    category: "options",
    definition:
      "IV Rank normalises current implied volatility on a 0–100 scale relative to its range over the past year: (Current IV − 1Y Min IV) / (1Y Max IV − 1Y Min IV) × 100. An IV Rank of 90 means current IV is near the top of its annual range — options are expensive, favouring option-selling strategies. An IV Rank of 10 means options are cheap relative to their own history, favouring option-buying strategies. IV Rank is a more robust signal than absolute IV because different stocks have different normal IV ranges.",
    related: ["iv-percentile", "implied-volatility", "options-chain"],
  },
  {
    slug: "iv-percentile",
    term: "IV Percentile",
    category: "options",
    definition:
      "IV Percentile is the percentage of trading days over the past year when IV was below the current level. An IV Percentile of 85 means IV has been lower than today's level on 85% of days — options are expensive relative to recent history. IV Percentile is similar to IV Rank but less sensitive to outliers because it is based on count rather than range. Both are displayed on EconoSift's Options page.",
    related: ["iv-rank", "implied-volatility"],
  },
  {
    slug: "atm",
    term: "ATM (At-the-Money)",
    category: "options",
    definition:
      "An option is at-the-money when its strike price is equal (or closest) to the current underlying price. ATM options have the highest gamma — delta changes most rapidly near the money — and the highest time value (extrinsic value). They are the most liquid options and are used to calculate implied volatility benchmarks like IV30 and the VIX methodology.",
    related: ["itm", "otm", "moneyness", "delta", "gamma"],
  },
  {
    slug: "itm",
    term: "ITM (In-the-Money)",
    category: "options",
    definition:
      "An option is in-the-money when it has intrinsic value: a call is ITM when the underlying price is above the strike; a put is ITM when the underlying is below the strike. ITM options have delta approaching 1 (calls) or −1 (puts) as they go deeper ITM, behaving increasingly like the underlying stock. They have lower time value and higher absolute premium due to intrinsic value.",
    related: ["atm", "otm", "moneyness", "delta", "intrinsic-value-option"],
  },
  {
    slug: "otm",
    term: "OTM (Out-of-the-Money)",
    category: "options",
    definition:
      "An option is out-of-the-money when it has no intrinsic value — a call with strike above the spot price, or a put with strike below the spot price. OTM options are cheaper than ATM or ITM options but have a lower probability of expiring in-the-money. They are popular for directional speculation (leverage via low premium) and for hedging (OTM puts as tail-risk insurance). OTM options have the highest implied volatility in the volatility smile.",
    related: ["atm", "itm", "moneyness", "iv-smile"],
  },
  {
    slug: "moneyness",
    term: "Moneyness",
    category: "options",
    definition:
      "Moneyness is the ratio of the strike price to the underlying spot price (K/S). It provides a standardised way to compare options across strikes and underlyings. Moneyness < 1 for calls means ITM; > 1 means OTM (reverse for puts). The volatility smile is typically plotted against moneyness rather than absolute strike to make it comparable across different stocks and time periods.",
    related: ["atm", "itm", "otm", "iv-smile"],
  },
  {
    slug: "open-interest",
    term: "Open Interest (OI)",
    category: "options",
    definition:
      "Open Interest is the total number of outstanding option contracts for a specific strike and expiration that have not been closed or exercised. It is a measure of liquidity and market participation. Rising OI alongside rising price suggests new money entering a trend; rising OI alongside falling price can indicate bearish positioning. The OI profile — OI plotted against strikes — reveals where large positions are concentrated and where 'max pain' may exert a magnetic pull on price.",
    related: ["oi-profile", "put-call-oi-ratio", "max-pain", "options-chain"],
  },
  {
    slug: "put-call-oi-ratio",
    term: "Put/Call OI Ratio",
    category: "options",
    definition:
      "The Put/Call Open Interest Ratio compares total open interest in puts versus calls. A ratio above 1.0 indicates more puts outstanding than calls — typically a bearish sentiment signal. Extreme readings can be contrarian: very high put/call ratios may indicate excessive bearishness and a potential bounce. It is less noisy than the volume-based put/call ratio because OI represents position holdings rather than intraday flow.",
    related: ["open-interest", "oi-profile", "fear-greed"],
  },
  {
    slug: "max-pain",
    term: "Max Pain",
    category: "options",
    definition:
      "Max Pain is the strike price at which the total value of all outstanding options (calls + puts) would expire worthless, causing maximum financial loss to option buyers — and maximum profit to option sellers. The theory suggests that market makers, who are net short options, have an incentive to pin the underlying near max pain at expiration. While controversial, max pain levels often act as a rough magnet for price in the days leading up to expiration.",
    related: ["open-interest", "oi-profile", "options-chain", "expiry"],
  },
  {
    slug: "implied-move",
    term: "Implied Move",
    category: "options",
    definition:
      "The implied move is the expected price range (up or down) implied by the price of an at-the-money straddle — a long call + long put at the same strike and expiration. It is calculated as: Straddle Price / Underlying Price × 100%. It represents the market's expectation of the magnitude of the price move over the life of the option, regardless of direction. It is widely used around earnings announcements to size positions and set expectations.",
    related: ["straddle", "implied-volatility", "atm", "earnings-event"],
  },
  {
    slug: "straddle",
    term: "Straddle",
    category: "options",
    definition:
      "A straddle is an options strategy consisting of a long call and a long put at the same strike (usually ATM) and same expiration. It profits if the underlying moves significantly in either direction — a bet on volatility, not direction. The cost of the straddle is the combined premium, and the break-even points are strike ± total premium. Straddles are commonly traded around binary events like earnings, FDA decisions, or economic releases.",
    related: ["implied-move", "atm", "strangle", "vega"],
  },
  {
    slug: "delta",
    term: "Delta",
    category: "options",
    definition:
      "Delta measures how much an option's price changes for a $1 change in the underlying price. Call deltas range from 0 to 1; put deltas range from −1 to 0. An ATM call has delta ~0.5; a deep ITM call approaches 1.0 (behaving like the stock itself). Delta is also a rough proxy for the probability of expiring ITM — a 0.30 delta call has roughly a 30% chance of finishing in the money. Delta is the 'speed' component of option risk.",
    related: ["gamma", "theta", "vega", "rho", "greeks"],
  },
  {
    slug: "gamma",
    term: "Gamma",
    category: "options",
    definition:
      "Gamma is the rate of change of delta per $1 move in the underlying — the 'acceleration' of the option price. High gamma means delta changes rapidly, which is both an opportunity (quick profits on directional moves) and a risk (position needs frequent rebalancing). Gamma is highest for ATM options near expiration and lowest for deep ITM/OTM or long-dated options. Option sellers are short gamma, meaning their position worsens as the underlying moves against them.",
    related: ["delta", "theta", "vega", "greeks"],
  },
  {
    slug: "theta-option",
    term: "Theta (Time Decay)",
    category: "options",
    definition:
      "Theta measures how much an option loses in value each day due to the passage of time (time decay), all else equal. It is always negative for long option positions — every day that passes without a favourable move erodes the option's extrinsic value. Theta accelerates as expiration approaches: an ATM option loses more value per day with 5 days to expiry than with 30 days. Option sellers are long theta — they profit from time decay.",
    related: ["delta", "gamma", "vega", "expiry"],
  },
  {
    slug: "vega",
    term: "Vega",
    category: "options",
    definition:
      "Vega measures an option's sensitivity to a 1 percentage-point change in implied volatility. A vega of 0.20 means the option price changes by $0.20 for each 1% change in IV. Long options are long vega (profit from rising IV); short options are short vega. Vega is highest for long-dated ATM options and lowest for deep ITM/OTM or short-dated options. Vega risk dominates option portfolios around events that can cause IV spikes.",
    related: ["delta", "gamma", "theta-option", "implied-volatility"],
  },
  {
    slug: "rho",
    term: "Rho",
    category: "options",
    definition:
      "Rho measures an option's sensitivity to a 1% change in the risk-free interest rate. For most equity options, rho is the smallest and least important Greek — it matters most for very long-dated options (LEAPS) and for interest-rate-sensitive underlyings like bonds and currencies. Call rho is positive (higher rates increase call value by reducing the present value of the strike); put rho is negative.",
    related: ["delta", "gamma", "vega", "theta-option", "risk-free-rate"],
  },
  {
    slug: "black-scholes",
    term: "Black-Scholes Pricing Model",
    category: "options",
    definition:
      "The Black-Scholes model is the foundational mathematical framework for pricing European options, developed by Fischer Black, Myron Scholes, and Robert Merton in 1973. It uses five inputs — underlying price, strike, time to expiry, risk-free rate, and volatility — to produce a theoretical option price. Its key insight is that options can be perfectly hedged in continuous time, making their value independent of risk preferences. The model assumes constant volatility and continuous trading, which do not hold perfectly in reality, but it remains the industry standard and the basis for implied volatility calculation.",
    related: ["implied-volatility", "crr-binomial", "delta", "gamma"],
  },
  {
    slug: "crr-binomial",
    term: "CRR (Cox-Ross-Rubinstein) Binomial Tree",
    category: "options",
    definition:
      "The CRR binomial tree is a discrete-time option pricing model that builds a tree of possible future prices over the option's life, then works backward from expiration to calculate the option's present value. Unlike Black-Scholes, it can handle American-style (early-exercise) options and dividends. Each step splits into an up-move and down-move, with probabilities calibrated to match the risk-neutral world. EconoSift uses the CRR model to price American options alongside the Black-Scholes benchmark.",
    related: ["black-scholes", "american-option", "monte-carlo-options"],
  },
  {
    slug: "brents-method",
    term: "Brent's Method (IV Backsolve)",
    category: "options",
    definition:
      "Brent's method is a robust numerical root-finding algorithm used to back-solve implied volatility from an option's market price. Because the Black-Scholes formula cannot be inverted algebraically for volatility, an iterative search is required. Brent's method combines bisection, secant, and inverse quadratic interpolation for rapid and reliable convergence. This is the standard algorithm for IV backsolve and is used by EconoSift's options engine.",
    related: ["implied-volatility", "black-scholes", "iv-backsolve"],
  },
  {
    slug: "iv-smile",
    term: "IV Smile",
    category: "options",
    definition:
      "The IV smile is the pattern of implied volatility across different strike prices for the same expiration — typically higher IV for deep OTM puts (crash protection demand), slightly elevated for OTM calls, and lowest near the money. This shape violates the Black-Scholes assumption of constant volatility and reflects real-world risk preferences: investors pay a premium for downside protection. After the 1987 crash, the smile became notably steeper for puts — the 'skew' — which persists today.",
    related: ["iv-term-structure", "implied-volatility", "otm", "atm"],
  },
  {
    slug: "iv-term-structure",
    term: "IV Term Structure",
    category: "options",
    definition:
      "The IV term structure shows implied volatility across different expiration dates for the same (usually ATM) strike. Normally, longer-dated options have higher IV because uncertainty increases with time. An inverted term structure — near-term IV higher than longer-term IV — signals acute near-term fear, common around earnings or crisis events. The shape of the term structure is a powerful sentiment and event-risk indicator. EconoSift's Options page plots the full term structure.",
    related: ["iv-smile", "implied-volatility", "expiry", "contango-backwardation"],
  },
  {
    slug: "options-chain",
    term: "Options Chain",
    category: "options",
    definition:
      "An options chain is a table listing all available call and put options for a given ticker and expiration date, showing strike, bid, ask, last price, volume, open interest, and implied volatility for each. It is the primary interface for options trading. EconoSift's Options page displays the full chain with calculated Greeks and allows filtering by moneyness range.",
    related: ["open-interest", "oi-profile", "implied-volatility", "delta", "expiry"],
  },
  {
    slug: "monte-carlo-options",
    term: "Monte Carlo Options Pricing",
    category: "options",
    definition:
      "Monte Carlo option pricing simulates thousands of random price paths for the underlying, calculates the option payoff for each path, and averages the discounted payoffs to estimate the option's fair value. It is more flexible than Black-Scholes or binomial trees — it can handle path-dependent (exotic) options, stochastic volatility, and complex payoff structures. The trade-off is computational cost: many simulations are needed for precise estimates. EconoSift uses Monte Carlo for options pricing via the 🔴 Run Analysis button.",
    related: ["black-scholes", "crr-binomial", "monte-carlo-risk"],
  },
  {
    slug: "expiry",
    term: "Expiry (DTE — Days to Expiry)",
    category: "options",
    definition:
      "Days to Expiry (DTE) is the number of calendar days until an option contract expires and ceases to exist. As DTE decreases, time decay (theta) accelerates — the option's extrinsic value erodes increasingly rapidly in the final weeks. Options with fewer than 21 DTE are considered 'near-dated' and have the highest gamma risk. The standard monthly options expire on the third Friday of the month.",
    related: ["theta-option", "gamma", "options-chain"],
  },
  {
    slug: "oi-profile",
    term: "OI Profile",
    category: "options",
    definition:
      "The OI (Open Interest) Profile is a chart showing the concentration of open interest across different strike prices. Peaks in the OI profile often act as support or resistance — large put OI at a strike can create a 'put wall' that supports price; large call OI can create a 'call wall' that caps price. The OI profile is used alongside max pain to gauge potential price magnets and barriers. EconoSift's Options page plots the full OI profile.",
    related: ["open-interest", "max-pain", "put-call-oi-ratio", "options-chain"],
  },

  // ════════════════════════════════════════════════════════════════
  // 7. Macroeconomic Indicators
  // ════════════════════════════════════════════════════════════════
  {
    slug: "gdp",
    term: "GDP (Gross Domestic Product)",
    category: "macro",
    definition:
      "Gross Domestic Product is the total monetary value of all finished goods and services produced within a country's borders in a specific time period — the broadest measure of economic output. It can be measured via three approaches: production (output by industry), expenditure (consumption + investment + government spending + net exports), and income (wages + profits + rents). Real GDP adjusts for inflation to measure actual output growth; nominal GDP uses current prices. GDP growth is the most important single indicator of economic health.",
    related: ["gdp-growth", "gdp-per-capita", "nominal-gdp", "real-gdp"],
  },
  {
    slug: "gdp-growth",
    term: "GDP Growth (YoY)",
    category: "macro",
    definition:
      "GDP Growth is the year-over-year percentage change in real (inflation-adjusted) Gross Domestic Product. Positive growth indicates economic expansion; two consecutive quarters of negative growth is the traditional (though unofficial) definition of a recession. The long-run trend growth rate for developed economies is roughly 2–3%; emerging economies often grow faster. GDP growth drives corporate earnings, employment, and eventually central bank policy.",
    related: ["gdp", "recession", "unemployment-rate", "regime-clock"],
  },
  {
    slug: "gdp-per-capita",
    term: "GDP Per Capita",
    category: "macro",
    definition:
      "GDP per capita is GDP divided by the country's population — a rough measure of average living standards and economic productivity. It is widely used for cross-country comparisons because it normalises for population size. However, it is an average that says nothing about inequality: a country can have high GDP per capita alongside widespread poverty. It is one of the six indicators on EconoSift's Atlas page.",
    related: ["gdp", "atlas", "purchasing-power-parity"],
  },
  {
    slug: "cpi",
    term: "CPI (Consumer Price Index)",
    category: "macro",
    definition:
      "The Consumer Price Index measures the average change over time in the prices paid by urban consumers for a fixed basket of goods and services — food, housing, transportation, medical care, and more. It is the most widely followed inflation gauge. CPI is reported monthly by the Bureau of Labor Statistics; the year-over-year change is the headline inflation rate. Core CPI excludes volatile food and energy prices to reveal underlying inflation trends.",
    related: ["cpi-yoy", "core-cpi", "pce", "inflation"],
  },
  {
    slug: "cpi-yoy",
    term: "CPI YoY (CPI Inflation)",
    category: "macro",
    definition:
      "CPI year-over-year is the percentage change in the Consumer Price Index compared to the same month one year ago. It is the headline inflation number reported in the news. The Federal Reserve targets 2% inflation (using PCE, not CPI), but CPI is more widely followed by markets and the public. Sustained CPI above trend can trigger Fed tightening, which typically pressures equity valuations.",
    related: ["cpi", "core-cpi", "pce", "fed-funds-rate", "inflation"],
  },
  {
    slug: "core-cpi",
    term: "Core CPI",
    category: "macro",
    definition:
      "Core CPI is the Consumer Price Index excluding food and energy prices, which are volatile and can obscure the underlying inflation trend. Central bankers focus on core inflation to gauge persistent price pressures. If headline CPI is high but core is stable, the spike may be transitory (e.g., an oil price shock). If core is rising, it signals broad-based inflation that may require policy response.",
    related: ["cpi", "cpi-yoy", "core-pce", "pce"],
  },
  {
    slug: "pce",
    term: "PCE (Personal Consumption Expenditures)",
    category: "macro",
    definition:
      "The Personal Consumption Expenditures price index is the Federal Reserve's preferred inflation measure. Unlike CPI, which uses a fixed basket, PCE accounts for substitution effects — consumers switching to cheaper alternatives when prices rise. As a result, PCE typically runs slightly below CPI. Core PCE (excluding food and energy) is the specific metric the Fed targets at 2%. PCE is released monthly as part of the Personal Income and Outlays report.",
    related: ["core-pce", "cpi", "fed-funds-rate", "inflation"],
  },
  {
    slug: "core-pce",
    term: "Core PCE",
    category: "macro",
    definition:
      "Core PCE is the PCE price index excluding food and energy, and it is the Federal Reserve's official 2% inflation target. It is arguably the single most important inflation metric for US monetary policy. The Fed watches the monthly and year-over-year changes in core PCE closely. Sustained core PCE above target prompts rate hikes; sustained below-target readings can justify easing.",
    related: ["pce", "cpi", "fed-funds-rate", "core-cpi"],
  },
  {
    slug: "ppi",
    term: "PPI (Producer Price Index)",
    category: "macro",
    definition:
      "The Producer Price Index measures the average change in selling prices received by domestic producers for their output — essentially wholesale inflation. It is considered a leading indicator for CPI because producer price changes tend to flow through to consumer prices eventually (though not always one-to-one). PPI is broken down by industry and stage of processing (crude, intermediate, finished goods).",
    related: ["cpi", "pce", "inflation"],
  },
  {
    slug: "unemployment-rate",
    term: "Unemployment Rate",
    category: "macro",
    definition:
      "The unemployment rate is the percentage of the labour force that is jobless and actively seeking work. It is one of the most politically sensitive economic indicators and a key input to Fed policy via its dual mandate (maximum employment + stable prices). The 'natural rate of unemployment' (NAIRU) is estimated around 3.5–4.5% for the US. Very low unemployment can signal an overheating economy and wage-driven inflation.",
    related: ["nfp", "sahm-rule", "labor-force-participation", "phillips-curve"],
  },
  {
    slug: "nfp",
    term: "NFP (Non-Farm Payrolls)",
    category: "macro",
    definition:
      "Non-Farm Payrolls is the monthly change in US employment excluding farm workers, government, private household, and non-profit employees — the most important monthly economic release for financial markets. It covers roughly 80% of US workers. A strong NFP print (above ~150K) is generally positive for risk assets but can be negative if it fuels expectations of aggressive Fed tightening. NFP is released on the first Friday of each month by the BLS.",
    related: ["unemployment-rate", "initial-jobless-claims", "jolts", "phillips-curve"],
  },
  {
    slug: "initial-jobless-claims",
    term: "Initial Jobless Claims",
    category: "macro",
    definition:
      "Initial jobless claims are the number of new unemployment benefit applications filed in a given week. It is the most timely labour-market indicator — released weekly, every Thursday. Rising claims signal softening labour demand and often precede turning points in the unemployment rate. A sustained level above 300K is considered recessionary territory; readings below 200K indicate a very tight labour market.",
    related: ["unemployment-rate", "nfp", "sahm-rule"],
  },
  {
    slug: "labor-force-participation",
    term: "Labor Force Participation Rate",
    category: "macro",
    definition:
      "The labour force participation rate is the percentage of the working-age civilian population that is either employed or actively seeking work. It declined structurally after the 2008 crisis and again after COVID, partly due to an ageing population. A falling participation rate can make the unemployment rate appear artificially low. The prime-age (25–54) participation rate strips out demographic effects.",
    related: ["unemployment-rate", "nfp"],
  },
  {
    slug: "sahm-rule",
    term: "Sahm Rule",
    category: "macro",
    definition:
      "The Sahm Rule — developed by economist Claudia Sahm — identifies the start of a recession when the three-month moving average of the unemployment rate rises by 0.50 percentage points or more above its low over the prior 12 months. It is simple, timely, and has accurately identified every US recession since 1970 with few false positives. It is used as a real-time recession indicator on EconoSift's Macro page.",
    related: ["unemployment-rate", "recession", "nfp"],
  },
  {
    slug: "jolts",
    term: "JOLTS Openings and Quits",
    category: "macro",
    definition:
      "JOLTS (Job Openings and Labor Turnover Survey) is a monthly BLS report showing job openings, hires, quits, layoffs, and discharges. Job openings indicate labour demand; the quits rate (voluntary resignations as % of employment) is a leading wage-growth indicator — workers quit more when they are confident of finding better-paying jobs. The ratio of openings to unemployed persons is closely watched by the Fed as a measure of labour-market tightness.",
    related: ["unemployment-rate", "nfp", "initial-jobless-claims"],
  },
  {
    slug: "industrial-production",
    term: "Industrial Production (IndProd)",
    category: "macro",
    definition:
      "Industrial Production measures the real output of US manufacturing, mining, and electric and gas utilities. It is a monthly indicator of the goods-producing side of the economy. Manufacturing, the largest component, is sensitive to the business cycle — falling industrial production is a classic recession signal. The Fed reports it monthly alongside capacity utilisation.",
    related: ["capacity-utilisation", "ism-pmi", "gdp"],
  },
  {
    slug: "capacity-utilisation",
    term: "Capacity Utilisation",
    category: "macro",
    definition:
      "Capacity utilisation is the percentage of the US industrial sector's productive capacity currently in use. A rate above 80% historically signals a tight economy that may generate inflationary pressures. Below 75% indicates economic slack. It is released monthly by the Federal Reserve alongside industrial production.",
    related: ["industrial-production", "ism-pmi", "inflation"],
  },
  {
    slug: "existing-home-sales",
    term: "Existing Home Sales",
    category: "macro",
    definition:
      "Existing home sales measure the number of previously owned homes (single-family, condos, co-ops) sold during the month, reported at a seasonally adjusted annualised rate. It is the largest component of the US housing market (~90% of sales). Sales are sensitive to mortgage rates, employment, and consumer confidence. EconoSift displays existing home sales on the Housing tab of the Macro page.",
    related: ["housing-starts", "mortgage-rate", "case-shiller"],
  },
  {
    slug: "housing-starts",
    term: "Housing Starts",
    category: "macro",
    definition:
      "Housing starts count the number of new residential construction projects that began in a given month, annualised. It is a leading indicator for the construction industry and the broader economy — housing starts typically peak before a recession and trough before a recovery. Building permits, a related statistic, are even more forward-looking. Housing starts data is released monthly by the Census Bureau.",
    related: ["existing-home-sales", "mortgage-rate", "case-shiller"],
  },
  {
    slug: "case-shiller",
    term: "Case-Shiller Home Price Index (YoY)",
    category: "macro",
    definition:
      "The S&P CoreLogic Case-Shiller Index tracks changes in US residential real estate prices using a repeat-sales methodology — comparing sale prices of the same properties over time. The 20-city composite is the most quoted measure. Year-over-year changes of >10% indicate a hot housing market; negative readings signal a housing downturn. Home prices affect consumer wealth, confidence, and spending through the wealth effect.",
    related: ["existing-home-sales", "housing-starts", "mortgage-rate", "inflation"],
  },
  {
    slug: "mortgage-rate",
    term: "Mortgage Rate (30Y Fixed)",
    category: "macro",
    definition:
      "The 30-year fixed mortgage rate is the average interest rate on a conventional 30-year fixed-rate home loan, reported weekly by Freddie Mac. It is the most important determinant of housing affordability for most Americans. Mortgage rates closely track the 10-year Treasury yield plus a spread. Rising mortgage rates cool the housing market by reducing buyers' purchasing power.",
    related: ["existing-home-sales", "housing-starts", "case-shiller", "tnx"],
  },
  {
    slug: "wti-crude",
    term: "WTI Crude Oil",
    category: "macro",
    definition:
      "West Texas Intermediate (WTI) is the benchmark US crude oil grade, priced at Cushing, Oklahoma. Oil prices affect inflation directly (through gasoline and heating costs) and indirectly (via transportation and production inputs for nearly all goods). Sustained high oil prices act as a tax on consumers and can precipitate recessions. WTI is traded on NYMEX and is one of the most important global macro variables.",
    related: ["commodities", "inflation", "cpi", "gold"],
  },
  {
    slug: "gold",
    term: "Gold Spot Price",
    category: "macro",
    definition:
      "Gold is a precious metal that serves as a store of value, inflation hedge, and safe-haven asset. Unlike fiat currencies, gold supply is relatively fixed and cannot be printed by central banks. Gold prices tend to rise when real interest rates fall, when the USD weakens, and during periods of geopolitical uncertainty. It is inversely correlated with real yields — when TIPS yields go negative, gold becomes more attractive.",
    related: ["wti-crude", "commodities", "real-yield", "dxy"],
  },
  {
    slug: "commodities",
    term: "Commodities (Broad)",
    category: "macro",
    definition:
      "Commodities are raw materials — energy (oil, natural gas), metals (gold, copper, silver), and agricultural products (wheat, corn, soybeans). They are the building blocks of the global economy and tend to outperform during inflationary periods. Commodity prices are driven by supply and demand dynamics, not discounted cash flows like equities, making them effective portfolio diversifiers. Copper is particularly notable as an economic bellwether ('Dr. Copper') due to its widespread industrial use.",
    related: ["wti-crude", "gold", "copper", "inflation", "ppi"],
  },

  // ════════════════════════════════════════════════════════════════
  // 8. Yield Curve & Fixed Income
  // ════════════════════════════════════════════════════════════════
  {
    slug: "yield-curve",
    term: "Yield Curve",
    category: "yieldcurve",
    definition:
      "The yield curve is a graph plotting government bond yields across different maturities — from 1-month bills to 30-year bonds — at a single point in time. Normally it slopes upward (longer maturities pay higher yields to compensate for duration and inflation risk). The curve's shape contains a wealth of information about growth and inflation expectations, monetary policy expectations, and recession probability. The US Treasury yield curve is the most important in global finance.",
    related: ["10y2y-spread", "inverted-yield-curve", "treasury-yield", "tenor"],
  },
  {
    slug: "treasury-yield",
    term: "Treasury Yield",
    category: "yieldcurve",
    definition:
      "A Treasury yield is the annualised return an investor earns by holding a US government bond to maturity, assuming all coupon payments are reinvested at the same rate. Because US Treasuries are considered free of default risk, their yields serve as the risk-free benchmark for all other assets. Yields move inversely to bond prices: when demand for safety rises, Treasury prices go up and yields go down (a 'flight to quality').",
    related: ["yield-curve", "tnx", "tenor", "tips"],
  },
  {
    slug: "tenor",
    term: "Tenor",
    category: "yieldcurve",
    definition:
      "Tenor is the length of time until a bond's maturity. Common Treasury tenors include 1-month, 3-month, 6-month, 1-year, 2-year, 5-year, 10-year, and 30-year. Each tenor's yield conveys different information: the 3-month reflects immediate Fed policy expectations; the 2-year reflects policy expectations ~2 years out; the 10-year reflects long-term growth and inflation expectations. The 10-year is the most important benchmark for mortgage rates and equity valuations.",
    related: ["yield-curve", "treasury-yield", "10y2y-spread"],
  },
  {
    slug: "10y2y-spread",
    term: "10Y-2Y Spread (2s10s)",
    category: "yieldcurve",
    definition:
      "The 10-year minus 2-year Treasury yield spread (2s10s) is the most closely watched recession indicator in bond markets. A negative (inverted) spread — where short-term yields exceed long-term yields — has preceded every US recession since the 1950s with only one false signal. It reflects bond market expectations that the Fed will need to cut rates in the future because economic weakness is coming. The lead time from inversion to recession is variable, typically 6–24 months.",
    related: ["inverted-yield-curve", "yield-curve", "3m10y-spread", "recession"],
  },
  {
    slug: "3m10y-spread",
    term: "3M-10Y Spread (3m10y)",
    category: "yieldcurve",
    definition:
      "The 3-month minus 10-year Treasury spread is an alternative recession indicator — some economists, including those at the New York Fed, prefer it to the 2s10s spread. It is more directly tied to the Fed's policy rate (the 3-month bill closely tracks the Fed Funds rate). An inversion here indicates the market believes the Fed will need to cut rates significantly in the future.",
    related: ["10y2y-spread", "inverted-yield-curve", "fed-funds-rate"],
  },
  {
    slug: "inverted-yield-curve",
    term: "Inverted Yield Curve",
    category: "yieldcurve",
    definition:
      "An inverted yield curve occurs when short-term bond yields exceed long-term yields — the opposite of the normal upward-sloping curve. It signals that the bond market expects economic slowdown or recession, which will eventually force the central bank to cut short-term rates. The inversion does not cause the recession; it reflects market expectations. Historically, yield curve inversions have been the most reliable single predictor of US recessions.",
    related: ["10y2y-spread", "3m10y-spread", "yield-curve", "recession"],
  },
  {
    slug: "tips",
    term: "TIPS (Treasury Inflation-Protected Securities)",
    category: "yieldcurve",
    definition:
      "TIPS are US government bonds whose principal adjusts with the Consumer Price Index (CPI), protecting investors from inflation. The yield quoted on TIPS is the 'real yield' — the return above inflation. The difference between a nominal Treasury yield and the TIPS yield of the same maturity is the 'breakeven inflation rate' — the market's implied inflation forecast. TIPS are essential for understanding real interest rates versus nominal rates.",
    related: ["real-yield", "breakeven-inflation", "cpi", "yield-curve"],
  },
  {
    slug: "real-yield",
    term: "Real Yield (TIPS Yield)",
    category: "yieldcurve",
    definition:
      "Real yields are the yields on TIPS — the return investors earn after accounting for expected inflation. When real yields are negative, investors are effectively paying the government to hold their money, which typically supports gold, equities, and other risk assets. Rising real yields tighten financial conditions by increasing the real cost of borrowing. The 10-year TIPS real yield is a critical macro variable.",
    related: ["tips", "breakeven-inflation", "gold", "financial-conditions"],
  },
  {
    slug: "breakeven-inflation",
    term: "Breakeven Inflation Rate",
    category: "yieldcurve",
    definition:
      "Breakeven inflation is the difference between a nominal Treasury yield and the TIPS yield of the same maturity — the inflation rate that would make an investor indifferent between holding the nominal bond and the TIPS. It represents the market's inflation expectation over that horizon. The 5-year and 10-year breakevens are the most quoted. A rising breakeven signals increasing inflation expectations; a falling breakeven signals disinflationary expectations.",
    related: ["tips", "real-yield", "5y5y-forward", "inflation"],
  },
  {
    slug: "5y5y-forward",
    term: "5Y5Y Forward Breakeven",
    category: "yieldcurve",
    definition:
      "The 5-year, 5-year forward breakeven inflation rate is the market-implied expected inflation rate for the 5-year period starting 5 years from now. It strips out near-term inflation noise to reveal longer-term inflation expectations — the key metric the Fed watches to assess whether inflation expectations remain 'anchored.' If 5Y5Y is stable around 2–2.5%, the Fed can be patient; if it drifts significantly above or below, policy action may be warranted.",
    related: ["breakeven-inflation", "tips", "fed-funds-rate"],
  },
  {
    slug: "acm-term-premium",
    term: "ACM Term Premium",
    category: "yieldcurve",
    definition:
      "The ACM (Adrian-Crump-Moench) term premium decomposes the 10-year Treasury yield into two components: the expectations component (average expected future short-term rates) and the term premium (extra yield investors demand for bearing duration risk). A negative term premium — which has been common since the 2008 crisis — means investors are paying a premium for the safety and duration of long-term bonds beyond what rate expectations alone would justify. The New York Fed publishes ACM estimates monthly.",
    related: ["yield-curve", "tnx", "treasury-yield", "quantitative-easing"],
  },
  {
    slug: "us-spot-curve",
    term: "US Spot Curve",
    category: "yieldcurve",
    definition:
      "The US spot curve shows current Treasury yields across the full maturity spectrum — typically 11 standard tenors from 1-month to 30-year. It is the 'live' yield curve, updated with each day's closing yields. EconoSift's Yield page displays the US spot curve alongside foreign 10-year yields, TIPS real yields, and breakeven inflation rates.",
    related: ["yield-curve", "treasury-yield", "foreign-10y", "tenor"],
  },
  {
    slug: "foreign-10y",
    term: "Foreign 10-Year Yields",
    category: "yieldcurve",
    definition:
      "Foreign 10-year yields are the benchmark government bond yields for major developed economies — Germany (Bund), UK (Gilt), Japan (JGB), France (OAT), Italy (BTP), Canada, and Australia. Spreads versus the US 10-year reflect relative credit risk, growth expectations, and monetary policy divergence. Widening spreads for peripheral Eurozone countries (Italy, Spain) signal rising sovereign stress.",
    related: ["yield-curve", "us-spot-curve", "sovereign-risk", "spread-vs-us"],
  },
  {
    slug: "ig-oas",
    term: "IG OAS (Investment Grade Option-Adjusted Spread)",
    category: "yieldcurve",
    definition:
      "The Investment Grade OAS is the yield spread of investment-grade corporate bonds (rated BBB- and above) over comparable-maturity Treasuries, adjusted for embedded options. It measures the additional compensation investors demand for bearing corporate credit risk. IG spreads widening signals increasing concern about corporate defaults; narrowing signals improving credit confidence. The ICE BofA US Corporate Index is the standard source.",
    related: ["hy-oas", "bbb-spread", "credit-risk", "ted-spread"],
  },
  {
    slug: "hy-oas",
    term: "HY OAS (High Yield Option-Adjusted Spread)",
    category: "yieldcurve",
    definition:
      "The High Yield OAS is the spread of speculative-grade (junk) bonds over Treasuries. HY spreads are much wider and more volatile than IG spreads because default risk is significantly higher. HY OAS above 800–1,000 basis points historically signals recession fears or credit stress. It is a key component of EconoSift's Financial Conditions monitoring.",
    related: ["ig-oas", "bbb-spread", "credit-risk", "financial-conditions"],
  },
  {
    slug: "ted-spread",
    term: "TED Spread",
    category: "yieldcurve",
    definition:
      "The TED spread is the difference between the 3-month LIBOR (interbank lending rate) and the 3-month T-bill rate. It measures perceived credit risk in the banking system — a widening TED spread signals banks are reluctant to lend to each other, as during the 2008 crisis when it spiked to over 450 basis points. With LIBOR being phased out, SOFR-based equivalents are replacing it, but the concept remains relevant.",
    related: ["sofr", "ig-oas", "credit-risk", "financial-conditions"],
  },
  {
    slug: "sofr",
    term: "SOFR (Secured Overnight Financing Rate)",
    category: "yieldcurve",
    definition:
      "SOFR is the benchmark US overnight interest rate that replaced LIBOR. It is based on actual transactions in the Treasury repurchase (repo) market — secured by US government debt — making it more robust and harder to manipulate than LIBOR. The SOFR-Fed Funds spread indicates repo market stress: a wide spread signals liquidity tightness. SOFR is the reference rate for trillions of dollars of floating-rate debt and derivatives.",
    related: ["fed-funds-rate", "ted-spread", "funding-spread"],
  },
  {
    slug: "funding-spread",
    term: "Funding Spread",
    category: "yieldcurve",
    definition:
      "A funding spread is the difference between a short-term funding rate (like SOFR, LIBOR, or commercial paper) and the risk-free benchmark (typically the T-bill rate or Fed Funds). Widening funding spreads signal stress in short-term funding markets and reduced liquidity. EconoSift's Policy page tracks multiple funding spreads — SOFR-FF, CP spread, and the TED spread — to monitor financial system health.",
    related: ["sofr", "fed-funds-rate", "ted-spread", "cp-spread"],
  },
  {
    slug: "m2-money-supply",
    term: "M2 Money Supply",
    category: "yieldcurve",
    definition:
      "M2 is the broad measure of US money supply, encompassing cash, checking deposits, savings deposits, money market securities, and other near-money assets. It expanded dramatically during 2020–2021 due to pandemic stimulus, contributing to the subsequent inflation surge. The year-over-year change in M2 is tracked on EconoSift's Funding & Liquidity tab as a gauge of monetary conditions and future inflation pressure.",
    related: ["m2-yoy", "inflation", "quantity-theory", "fed-balance-sheet"],
  },

  // ════════════════════════════════════════════════════════════════
  // 9. Central Banks & Monetary Policy
  // ════════════════════════════════════════════════════════════════
  {
    slug: "central-bank",
    term: "Central Bank",
    category: "centralbanks",
    definition:
      "A central bank is a national institution responsible for managing a country's currency, money supply, and interest rates. Its primary mandates typically include price stability (controlling inflation) and often maximum employment (the Fed's 'dual mandate'). Central banks conduct monetary policy by setting short-term policy rates, conducting open market operations, and sometimes quantitative easing/tightening. Seven major central banks — the Fed, ECB, BoE, BoJ, BoC, RBA, and SNB — are tracked on EconoSift's Central Banks tab.",
    related: ["fed", "ecb", "policy-rate", "monetary-policy"],
  },
  {
    slug: "fed",
    term: "Fed (Federal Reserve)",
    category: "centralbanks",
    definition:
      "The Federal Reserve System is the central bank of the United States, established in 1913. Its dual mandate from Congress is maximum employment and stable prices (interpreted as 2% inflation). The Fed sets the federal funds rate, regulates banks, and serves as lender of last resort. The Federal Open Market Committee (FOMC) meets 8 times per year to set policy. The Fed's decisions are the single most important driver of global financial conditions.",
    related: ["fed-funds-rate", "fomc", "ecb", "central-bank", "dual-mandate"],
  },
  {
    slug: "ecb",
    term: "ECB (European Central Bank)",
    category: "centralbanks",
    definition:
      "The European Central Bank is the central bank for the 20 countries of the Eurozone. It has a single primary mandate — price stability, defined as 2% inflation over the medium term. The ECB sets three key rates: the main refinancing rate, the deposit facility rate, and the marginal lending rate. Governing Council meetings occur roughly every 6 weeks.",
    related: ["fed", "central-bank", "policy-rate", "ecb-main-refinancing-rate"],
  },
  {
    slug: "policy-rate",
    term: "Policy Rate",
    category: "centralbanks",
    definition:
      "The policy rate is the key interest rate set by a central bank to influence economic activity and inflation. It is the rate at which the central bank lends to commercial banks or the target for overnight interbank lending. Changes in the policy rate ripple through the entire economy: mortgage rates, corporate borrowing costs, bond yields, and equity valuations all adjust. EconoSift's Central Banks tab tracks policy rates for 7 major central banks from 2005 to present.",
    related: ["fed-funds-rate", "ecb-main-refinancing-rate", "central-bank", "tightening", "easing"],
  },
  {
    slug: "fed-funds-rate",
    term: "Fed Funds Rate (FEDFUNDS)",
    category: "centralbanks",
    definition:
      "The federal funds rate is the interest rate at which US depository institutions lend reserve balances to each other overnight. It is the Fed's primary monetary policy tool. The FOMC sets a target range (e.g., 5.25–5.50%). Changes in the fed funds rate are the most consequential policy decisions in global finance — they affect the discount rate for all USD-denominated assets and ripple out to global markets through carry trades and capital flows.",
    related: ["fed", "policy-rate", "fomc", "tightening", "easing"],
  },
  {
    slug: "ecb-main-refinancing-rate",
    term: "ECB Main Refinancing Rate (ECBMRRFR)",
    category: "centralbanks",
    definition:
      "The ECB's main refinancing rate is the rate at which Eurozone banks can borrow from the ECB on a weekly basis through regular refinancing operations. It is the ECB's primary policy rate and the benchmark for Eurozone interest rates. The ECB also sets a deposit facility rate (what banks earn on overnight deposits) and a marginal lending rate (emergency overnight borrowing).",
    related: ["ecb", "policy-rate", "central-bank"],
  },
  {
    slug: "tightening",
    term: "Tightening (Monetary Policy)",
    category: "centralbanks",
    definition:
      "Monetary tightening — or contractionary policy — occurs when a central bank raises interest rates, reduces its balance sheet, or otherwise makes money more expensive to slow the economy and combat inflation. Tightening typically causes bond yields to rise, equity valuations to compress (via higher discount rates), and the currency to strengthen. Aggressive tightening cycles, like the Fed's 2022 cycle, can trigger recessions.",
    related: ["easing", "fed-funds-rate", "policy-rate", "quantitative-tightening"],
  },
  {
    slug: "easing",
    term: "Easing (Monetary Policy)",
    category: "centralbanks",
    definition:
      "Monetary easing — or expansionary policy — occurs when a central bank lowers interest rates, expands its balance sheet (QE), or provides liquidity to stimulate the economy. Easing supports risk assets by lowering discount rates, reducing borrowing costs, and encouraging risk-taking. The zero lower bound (ZLB) is the practical limit of conventional easing — once rates hit zero, central banks turn to unconventional tools like QE and forward guidance.",
    related: ["tightening", "fed-funds-rate", "quantitative-easing", "policy-rate"],
  },
  {
    slug: "divergence-score",
    term: "Divergence Score",
    category: "centralbanks",
    definition:
      "The central bank divergence score measures how much each G7 central bank's policy rate deviates from the G7 average. A positive score means the bank is tighter than peers; a negative score means looser. Divergence drives FX markets — currencies of hawkish (tighter) central banks tend to strengthen against those of dovish (looser) central banks. EconoSift's Policy page displays the divergence score for all major CBs.",
    related: ["policy-rate", "fx-carry", "central-bank", "eur-usd"],
  },
  {
    slug: "fed-balance-sheet",
    term: "Fed Balance Sheet (WALCL)",
    category: "centralbanks",
    definition:
      "The Fed's balance sheet (FRED series WALCL) shows total assets held by the Federal Reserve — currently $6–8 trillion, reflecting Treasury and MBS holdings accumulated through quantitative easing (QE). Expanding the balance sheet is stimulative (QE); shrinking it is contractionary (QT). Balance sheet changes affect long-term interest rates, financial conditions, and risk asset valuations. EconoSift displays the Fed balance sheet in trillions of dollars on the Central Banks and Financial Conditions tabs.",
    related: ["quantitative-easing", "quantitative-tightening", "fed", "financial-conditions"],
  },
  {
    slug: "cb-meeting",
    term: "CB Meeting Calendar",
    category: "centralbanks",
    definition:
      "The central bank meeting calendar lists the scheduled policy meetings for the Fed, ECB, BoE, BoJ, BoC, RBA, and SNB. Markets price rate expectations ahead of these meetings, and surprises can cause large asset moves. EconoSift's Central Banks tab shows upcoming meetings with the days remaining, tracked via a curated JSON dataset of 52 CB meetings.",
    related: ["fed", "ecb", "policy-rate", "calendar"],
  },
  {
    slug: "taylor-rule",
    term: "Taylor Rule",
    category: "centralbanks",
    definition:
      "The Taylor Rule is a formula developed by economist John Taylor that prescribes what the policy rate 'should be' based on inflation and the output gap: r = neutral rate + actual inflation + 0.5 × (inflation gap) + 0.5 × (output gap). It provides a benchmark for judging whether monetary policy is too tight or too loose. When the actual policy rate is far below the Taylor Rule implied rate, policy is considered accommodative.",
    related: ["taylor-rule-implied-rate", "fed-funds-rate", "policy-rate", "inflation"],
  },
  {
    slug: "quantitative-easing",
    term: "Quantitative Easing (QE)",
    category: "centralbanks",
    definition:
      "Quantitative Easing is an unconventional monetary policy where the central bank purchases large quantities of government bonds (and sometimes corporate bonds or MBS) to inject liquidity, lower long-term interest rates, and stimulate the economy when short-term rates are already at zero. QE expands the central bank's balance sheet. It has been used extensively by the Fed, ECB, BoJ, and BoE since 2008. QE tends to boost asset prices by reducing yields and forcing investors into riskier assets (the 'portfolio balance channel').",
    related: ["quantitative-tightening", "fed-balance-sheet", "easing", "financial-conditions"],
  },

  // ════════════════════════════════════════════════════════════════
  // 10. Foreign Exchange (FX)
  // ════════════════════════════════════════════════════════════════
  {
    slug: "fx-rate",
    term: "FX Rate (Foreign Exchange Rate)",
    category: "fx",
    definition:
      "A foreign exchange rate is the price of one currency expressed in terms of another. It is the most liquid and deepest financial market, with over $7 trillion traded daily. FX rates are driven by interest rate differentials, inflation differentials, current account balances, geopolitical stability, and central bank policy. They are quoted in pairs — EUR/USD, GBP/USD, USD/JPY, etc. — and are the foundation for international trade and investment.",
    related: ["fx-pair", "spot-rate", "base-currency", "quote-currency"],
  },
  {
    slug: "fx-pair",
    term: "FX Pair",
    category: "fx",
    definition:
      "An FX pair consists of two currencies: the base currency (first) and the quote currency (second). EUR/USD = 1.10 means €1 buys $1.10. Major pairs all involve USD; crosses (e.g., EUR/GBP) do not. The G10 currency pairs are the most liquid: EUR/USD, USD/JPY, GBP/USD, USD/CHF, AUD/USD, USD/CAD, NZD/USD. EconoSift's FX Heatmap shows daily changes across all major crosses.",
    related: ["fx-rate", "base-currency", "quote-currency", "g10-currencies"],
  },
  {
    slug: "spot-rate",
    term: "Spot Rate",
    category: "fx",
    definition:
      "The spot exchange rate is the current price for immediate delivery of a currency pair — settlement typically occurs T+2 (two business days after the trade). It is distinct from the forward rate, which is the price for delivery at a future date. The spot rate is the most basic FX quote and the starting point for all FX derivatives.",
    related: ["fx-rate", "fx-pair", "forward-rate"],
  },
  {
    slug: "base-currency",
    term: "Base Currency",
    category: "fx",
    definition:
      "In an FX pair, the base currency is the first currency listed (e.g., EUR in EUR/USD). The exchange rate tells you how much of the quote currency is needed to buy one unit of the base. A rising EUR/USD means the base (EUR) is strengthening relative to the quote (USD). Convention dictates which currency is the base in each pair (e.g., EUR is always base in EUR/USD; USD is base in USD/JPY).",
    related: ["quote-currency", "fx-pair", "eur-usd"],
  },
  {
    slug: "quote-currency",
    term: "Quote Currency",
    category: "fx",
    definition:
      "In an FX pair, the quote currency (or counter currency) is the second currency listed. The exchange rate tells you how many units of the quote currency are needed to buy one unit of the base. In EUR/USD = 1.10, the quote currency is USD — €1 costs $1.10. A rising rate means the quote currency is weakening relative to the base.",
    related: ["base-currency", "fx-pair", "eur-usd"],
  },
  {
    slug: "g10-currencies",
    term: "G10 Currencies",
    category: "fx",
    definition:
      "The G10 currencies are the ten most liquid and widely traded developed-market currencies: US Dollar (USD), Euro (EUR), Japanese Yen (JPY), British Pound (GBP), Swiss Franc (CHF), Canadian Dollar (CAD), Australian Dollar (AUD), New Zealand Dollar (NZD), Swedish Krona (SEK), and Norwegian Krone (NOK). They form the core of the global FX market and are the universe for EconoSift's FX Carry strategy and FX Heatmap.",
    related: ["fx-carry", "fx-pair", "dxy", "carry-trade"],
  },
  {
    slug: "eur-usd",
    term: "EUR/USD",
    category: "fx",
    definition:
      "EUR/USD is the most traded currency pair in the world, representing the euro against the US dollar. It accounts for roughly 25% of all FX turnover. EUR/USD is driven by US-Eurozone interest rate differentials, growth differentials, trade balances, and relative central bank posture (Fed vs ECB). Because the euro has the largest weight in the DXY (57.6%), EUR/USD movements dominate the Dollar Index.",
    related: ["dxy", "fx-pair", "base-currency", "ecb", "fed"],
  },
  {
    slug: "fx-carry",
    term: "FX Carry",
    category: "fx",
    definition:
      "FX carry is an investment strategy of borrowing in a low-interest-rate currency (funding currency) and lending in a high-interest-rate currency (target currency), profiting from the interest rate differential — the 'carry.' For example, borrowing JPY at 0% and investing in AUD at 4% earns a 4% annualised carry. The risk is that the target currency depreciates enough to wipe out the carry (a 'carry crash'). EconoSift's Research Hub provides a G10 carry table and a long-top-3/short-bottom-3 backtest.",
    related: ["carry-trade", "g10-currencies", "carry-annualised", "vol-adjusted-carry"],
  },
  {
    slug: "carry-annualised",
    term: "Carry (Annualised)",
    category: "fx",
    definition:
      "Annualised carry is the interest rate differential between two currencies expressed as an annual percentage. For AUD/JPY, if AUD's policy rate is 4.35% and JPY's is 0.25%, the annualised carry is approximately 4.1%. Carry is earned by being long the higher-yielding currency and short the lower-yielding one. Carry trades tend to perform well in calm, low-volatility environments and suffer during risk-off episodes.",
    related: ["fx-carry", "vol-adjusted-carry", "carry-trade"],
  },
  {
    slug: "vol-adjusted-carry",
    term: "Vol-Adjusted Carry",
    category: "fx",
    definition:
      "Vol-adjusted carry divides the annualised carry by the FX pair's volatility, producing a risk-adjusted measure of carry attractiveness. A pair with high carry but extremely high volatility may have a lower vol-adjusted carry than a pair with moderate carry and low volatility. This metric helps avoid the classic carry trade pitfall of picking up pennies in front of a steamroller.",
    related: ["fx-carry", "carry-annualised", "sharpe-ratio"],
  },
  {
    slug: "ppp",
    term: "PPP (Purchasing Power Parity)",
    category: "fx",
    definition:
      "Purchasing Power Parity is the exchange rate at which a basket of identical goods would cost the same in two different countries. It is a long-run equilibrium concept — if a Big Mac costs $5 in the US and €4 in the Eurozone, PPP would imply EUR/USD = 1.25. Currencies that are far from their PPP-implied rate are considered overvalued or undervalued in the long run. EconoSift's Macro page provides PPP estimates for 8 major pairs using FRED exchange rates and CPI data.",
    related: ["ppp-overvaluation", "fx-rate", "real-effective-exchange-rate", "cpi"],
  },
  {
    slug: "real-effective-exchange-rate",
    term: "Real Effective Exchange Rate (REER)",
    category: "fx",
    definition:
      "The Real Effective Exchange Rate is the trade-weighted average of a country's currency against a basket of other currencies, adjusted for inflation differentials. It is a broad measure of currency competitiveness — a rising REER means the currency is becoming more expensive relative to trading partners, potentially hurting exports. The BIS and IMF publish REER indices for most countries.",
    related: ["ppp", "dxy", "fx-rate", "inflation"],
  },
  {
    slug: "fx-heatmap",
    term: "FX Heatmap",
    category: "fx",
    definition:
      "An FX heatmap is a colour-coded grid showing 1-day percentage changes across all major currency crosses. Green cells indicate the base currency strengthening (positive change); red cells indicate weakening. The heatmap provides an at-a-glance view of FX market dynamics — which currencies are strong and which are weak on the day. EconoSift's Macro page features an FX heatmap powered by FRED DEX exchange rate series.",
    related: ["fx-rate", "fx-pair", "g10-currencies", "dxy"],
  },

  // ════════════════════════════════════════════════════════════════
  // 11. Portfolio Theory & Analytics
  // ════════════════════════════════════════════════════════════════
  {
    slug: "efficient-frontier",
    term: "Efficient Frontier",
    category: "portfolio",
    definition:
      "The efficient frontier is the set of portfolios that offer the highest expected return for each level of risk (standard deviation) — or equivalently, the lowest risk for each level of return. It is derived from mean-variance optimisation, developed by Harry Markowitz in 1952 (for which he won the Nobel Prize). Portfolios below the frontier are suboptimal; portfolios on the frontier represent the best possible risk-return trade-offs given the available assets. EconoSift's Portfolio page computes and plots the efficient frontier for user-defined holdings.",
    related: ["mean-variance-optimisation", "max-sharpe-portfolio", "global-minimum-variance"],
  },
  {
    slug: "mean-variance-optimisation",
    term: "Mean-Variance Optimisation (MVO)",
    category: "portfolio",
    definition:
      "Mean-variance optimisation is the mathematical framework that finds portfolio weights maximising expected return for a given level of variance (risk) — or minimising variance for a target return. It requires estimates of expected returns, volatilities, and correlations for all assets. MVO's main practical weakness is that it is highly sensitive to input estimates — small changes in expected return assumptions can produce wildly different optimal weights (the 'error maximisation' problem).",
    related: ["efficient-frontier", "max-sharpe-portfolio", "black-litterman"],
  },
  {
    slug: "max-sharpe-portfolio",
    term: "Max Sharpe Portfolio (Tangency Portfolio)",
    category: "portfolio",
    definition:
      "The Max Sharpe portfolio — also called the tangency portfolio — is the point on the efficient frontier with the highest Sharpe ratio. It is the optimal risky portfolio for any investor who can borrow and lend at the risk-free rate, according to the Capital Allocation Line (CAL) framework. In practice, it is the default 'optimal' portfolio for investors who care about risk-adjusted returns.",
    related: ["efficient-frontier", "sharpe-ratio", "global-minimum-variance", "mean-variance-optimisation"],
  },
  {
    slug: "global-minimum-variance",
    term: "Global Minimum Variance Portfolio (GMV)",
    category: "portfolio",
    definition:
      "The Global Minimum Variance portfolio is the leftmost point on the efficient frontier — the portfolio with the absolute lowest possible volatility given the asset universe. It does not depend on expected return estimates (only on the covariance matrix), which makes it more robust than other MVO portfolios. The GMV is often used as a conservative benchmark and is the starting point for risk-parity analysis.",
    related: ["efficient-frontier", "max-sharpe-portfolio", "risk-parity", "mean-variance-optimisation"],
  },
  {
    slug: "black-litterman",
    term: "Black-Litterman Model",
    category: "portfolio",
    definition:
      "The Black-Litterman model — developed by Fischer Black and Robert Litterman at Goldman Sachs — addresses the instability of mean-variance optimisation by starting with equilibrium market-cap weights (implied by CAPM) and blending them with the investor's specific views (e.g., 'Tech will outperform by 5%'). The resulting expected returns are more stable and intuitive than raw historical estimates. EconoSift's Portfolio page implements Black-Litterman via the 🟡 Calculate button.",
    related: ["mean-variance-optimisation", "efficient-frontier", "bl-return", "capm"],
  },
  {
    slug: "bl-return",
    term: "BL Return (Black-Litterman Return)",
    category: "portfolio",
    definition:
      "Black-Litterman adjusted returns are the expected return estimates that result from blending equilibrium (CAPM-implied) returns with the investor's explicit views, weighted by the confidence in each view. They provide more sensible inputs for mean-variance optimisation than raw historical returns. The degree of adjustment depends on view confidence — a strongly held view pulls the BL return closer to the view; a weakly held view leaves it near equilibrium.",
    related: ["black-litterman", "equilibrium-return", "capm"],
  },
  {
    slug: "optimal-weights",
    term: "Optimal Weights",
    category: "portfolio",
    definition:
      "Optimal weights are the portfolio allocation percentages that maximise the objective function — typically Sharpe ratio, risk-adjusted return, or a utility function. They are the output of portfolio optimisation. At EconoSift, optimal weights are displayed for both Black-Litterman-adjusted optimisation and standard mean-variance optimisation, allowing comparison.",
    related: ["mean-variance-optimisation", "black-litterman", "efficient-frontier"],
  },
  {
    slug: "monte-carlo-portfolio",
    term: "Monte Carlo Simulation (Portfolio)",
    category: "portfolio",
    definition:
      "Monte Carlo simulation for portfolios generates thousands of random portfolio return outcomes by drawing from the estimated multivariate return distribution, producing a distribution of possible future portfolio values. It answers questions like 'What is the probability of a 20% loss over the next year?' Unlike parametric methods, Monte Carlo can incorporate non-normal distributions and complex interactions. EconoSift's Portfolio page offers Monte Carlo simulation for forward-looking risk estimation.",
    related: ["monte-carlo-risk", "var", "efficient-frontier", "stress-testing"],
  },
  {
    slug: "kelly-criterion",
    term: "Kelly Criterion",
    category: "portfolio",
    definition:
      "The Kelly Criterion is a formula for optimal bet sizing to maximise the long-run growth rate of capital. Kelly Fraction = (Expected Return − Risk-Free Rate) / Variance. Betting more than the Kelly fraction reduces long-run growth; betting less is conservative but safer. The full Kelly is considered aggressive — many practitioners use 'half-Kelly' to reduce volatility while retaining most of the growth benefit. EconoSift's Portfolio page displays the Kelly fraction for each holding.",
    related: ["kelly-fraction", "sharpe-ratio", "position-sizing"],
  },
  {
    slug: "kelly-fraction",
    term: "Kelly Fraction",
    category: "portfolio",
    definition:
      "The Kelly fraction is the optimal percentage of capital to allocate to a position according to the Kelly Criterion. A Kelly fraction of 0.25 means the investor should allocate 25% of their capital to this position for maximum long-run growth. It is derived from the asset's expected excess return divided by its variance. Individual Kelly fractions may sum to more than 100%, requiring scaling or constraints.",
    related: ["kelly-criterion", "position-sizing", "sharpe-ratio"],
  },
  {
    slug: "fama-french",
    term: "Fama-French Factor Models",
    category: "portfolio",
    definition:
      "The Fama-French models explain portfolio returns using multiple risk factors beyond just market beta. The 3-factor model adds SMB (small minus big, the size premium) and HML (high minus low, the value premium). The 5-factor model further adds RMW (profitability) and CMA (investment). These models capture well-documented return patterns that CAPM cannot explain. EconoSift provides Fama-French 3-factor and 5-factor attribution for any portfolio or ticker.",
    related: ["smb", "hml", "rmw", "cma", "factor-loading", "capm"],
  },
  {
    slug: "smb",
    term: "SMB (Small Minus Big)",
    category: "portfolio",
    definition:
      "SMB is the Fama-French size factor — the return of small-cap stocks minus the return of large-cap stocks. A positive loading on SMB means the portfolio tilts toward smaller companies, which have historically earned a size premium. The SMB factor captures the empirical observation that small-cap stocks tend to outperform large-caps over long periods, though the premium has diminished since its discovery.",
    related: ["fama-french", "hml", "rmw", "cma", "factor-loading"],
  },
  {
    slug: "hml",
    term: "HML (High Minus Low)",
    category: "portfolio",
    definition:
      "HML is the Fama-French value factor — the return of high book-to-market (value) stocks minus the return of low book-to-market (growth) stocks. A positive HML loading means the portfolio tilts toward value stocks. The value premium is one of the most robust and well-documented factor returns in finance, though it can underperform for extended periods.",
    related: ["fama-french", "smb", "factor-loading", "value-investing"],
  },
  {
    slug: "rmw",
    term: "RMW (Robust Minus Weak)",
    category: "portfolio",
    definition:
      "RMW is the Fama-French profitability factor — the return of stocks with robust (high) operating profitability minus the return of stocks with weak (low) profitability. A positive RMW loading means the portfolio favours highly profitable companies. Quality/profitability has been a strong factor, particularly in the post-2000 period.",
    related: ["fama-french", "cma", "factor-loading", "roe", "roic"],
  },
  {
    slug: "cma",
    term: "CMA (Conservative Minus Aggressive)",
    category: "portfolio",
    definition:
      "CMA is the Fama-French investment factor — the return of companies with conservative (low) asset growth minus those with aggressive (high) asset growth. Companies that invest conservatively have historically outperformed those that invest aggressively, possibly because rapid asset expansion often leads to overinvestment and poor returns on capital.",
    related: ["fama-french", "rmw", "factor-loading"],
  },
  {
    slug: "factor-loading",
    term: "Factor Loading (Beta Coefficient)",
    category: "portfolio",
    definition:
      "A factor loading is the coefficient from regressing a portfolio's returns on a factor's returns — it measures the portfolio's sensitivity to that factor. A loading of 0.5 on SMB means the portfolio gains (loses) 0.5% for every 1% that small-cap stocks outperform (underperform) large caps. Factor loadings reveal a portfolio's true risk exposures beyond what the top-level holdings suggest.",
    related: ["fama-french", "beta", "t-stat", "r-squared"],
  },
  {
    slug: "t-stat",
    term: "t-Statistic",
    category: "portfolio",
    definition:
      "The t-statistic tests whether a coefficient (like a factor loading or alpha) is statistically significantly different from zero. It is calculated as Coefficient / Standard Error. A t-stat above 2.0 (in absolute value) is roughly the threshold for statistical significance at the 95% confidence level. t-stats below 1.5 suggest the estimated coefficient could easily be noise.",
    related: ["p-value", "factor-loading", "alpha", "significance-stars"],
  },
  {
    slug: "risk-contribution",
    term: "Risk Contribution (% Contrib)",
    category: "portfolio",
    definition:
      "Risk contribution is the percentage of total portfolio variance (or volatility) attributable to each holding. It depends on the holding's weight, its own volatility, and its correlations with all other assets. A well-balanced risk portfolio aims for roughly equal risk contributions across holdings (the risk parity philosophy). A concentrated risk contribution — one stock driving 50% of portfolio risk — signals poor diversification.",
    related: ["marginal-risk-contribution", "risk-parity", "diversification", "correlation"],
  },
  {
    slug: "marginal-risk-contribution",
    term: "Marginal Risk Contribution",
    category: "portfolio",
    definition:
      "Marginal risk contribution is the change in total portfolio risk (standard deviation) from a small increase in an asset's weight. It is the derivative of portfolio risk with respect to weight. Assets with high marginal risk contributions are the ones where adding more weight most increases portfolio risk. In an optimal portfolio, all marginal risk contributions should be equalised.",
    related: ["risk-contribution", "risk-parity", "mean-variance-optimisation"],
  },
  {
    slug: "correlation",
    term: "Correlation",
    category: "portfolio",
    definition:
      "Correlation measures how two assets move together, ranging from −1 (perfectly opposite) to +1 (perfectly together) with 0 indicating no linear relationship. Diversification works best with low or negative correlations between assets. However, correlations are not constant — they tend to spike toward +1 during market crises, exactly when diversification is most needed. This 'correlation breakdown' is a key limitation of portfolio theory.",
    related: ["pearson-correlation", "correlation-matrix", "diversification", "cointegration"],
  },
  {
    slug: "pearson-correlation",
    term: "Pearson Correlation",
    category: "portfolio",
    definition:
      "Pearson correlation is the standard linear correlation coefficient — it measures the strength and direction of a linear relationship between two variables. It is the default correlation measure in finance for portfolio construction. Its limitation is that it only captures linear relationships: two assets can have zero Pearson correlation but be perfectly related through a non-linear dependence (e.g., quadratic).",
    related: ["correlation", "correlation-matrix", "spearman-correlation"],
  },
  {
    slug: "underwater-curve",
    term: "Underwater Curve / Drawdown Chart",
    category: "portfolio",
    definition:
      "The underwater curve (or drawdown chart) plots the portfolio's decline from its peak value over time, showing every drawdown period and its depth. It is arguably the most psychologically honest way to visualise portfolio risk — it shows exactly how much money was 'underwater' at each point. A long, deep underwater period is more damaging to investor behaviour than high volatility with quick recoveries.",
    related: ["maximum-drawdown", "calmar-ratio", "total-return"],
  },
  {
    slug: "total-return",
    term: "Total Return",
    category: "portfolio",
    definition:
      "Total return is the cumulative percentage return over the entire analysis period, accounting for both price appreciation and dividends (if applicable). It is the most intuitive performance metric — 'how much money did I make?' — but should always be viewed alongside risk metrics like maximum drawdown, Sharpe ratio, and annualised volatility to contextualise how that return was achieved.",
    related: ["annualised-return", "contribution", "maximum-drawdown"],
  },
  {
    slug: "contribution",
    term: "Contribution (Portfolio Return Attribution)",
    category: "portfolio",
    definition:
      "Return contribution is each holding's weight multiplied by its total return over the period — showing how much each position contributed to the overall portfolio return. It answers 'which holdings drove performance?' A position with a small weight but huge return can contribute as much as a large-weight position with modest return. EconoSift's Portfolio page provides full contribution breakdowns.",
    related: ["total-return", "risk-contribution", "portfolio"],
  },

  // ════════════════════════════════════════════════════════════════
  // 12. Research Strategies
  // ════════════════════════════════════════════════════════════════
  {
    slug: "risk-parity",
    term: "Risk Parity",
    category: "research",
    definition:
      "Risk parity is a portfolio construction approach that allocates risk — not capital — equally across assets. In a traditional 60/40 portfolio, equities contribute ~90% of the risk because they are far more volatile than bonds. Risk parity equalises risk contributions, typically resulting in much higher bond allocations (often levered to match return targets). The two main methods are inverse-volatility weighting (simpler) and Equal Risk Contribution via optimisation (more precise, using SLSQP solver). EconoSift's Research Hub implements both.",
    related: ["erc", "inverse-vol-weighting", "60-40-benchmark", "risk-contribution"],
  },
  {
    slug: "erc",
    term: "ERC (Equal Risk Contribution)",
    category: "research",
    definition:
      "ERC is the mathematically rigorous approach to risk parity: find portfolio weights such that each asset contributes the same percentage of total portfolio risk. This is solved via constrained optimisation (SLSQP) — minimising the sum of squared differences between risk contributions. Unlike inverse-vol weighting, ERC accounts for correlations between assets, so two highly correlated assets will each receive less weight than they would under naive 1/σ weighting.",
    related: ["risk-parity", "inverse-vol-weighting", "marginal-risk-contribution"],
  },
  {
    slug: "inverse-vol-weighting",
    term: "Inverse Vol Weighting",
    category: "research",
    definition:
      "Inverse-vol weighting assigns portfolio weights proportional to 1/σ (one divided by volatility). The least volatile asset gets the largest weight. It is a simple, model-free approximation of risk parity that ignores correlations. While less precise than ERC, it is robust and less prone to estimation error. EconoSift's Research Hub uses inverse-vol as the baseline risk parity method.",
    related: ["risk-parity", "erc", "volatility"],
  },
  {
    slug: "60-40-benchmark",
    term: "60/40 Benchmark",
    category: "research",
    definition:
      "The 60/40 portfolio — 60% equities (usually SPY) and 40% bonds (usually AGG) — is the classic balanced portfolio benchmark. It has historically delivered equity-like returns with significantly lower volatility. However, in rising-rate environments where stock-bond correlations turn positive, the diversification benefit diminishes. EconoSift's risk parity backtest compares risk parity strategies against a 60/40 benchmark over multiple periods.",
    related: ["risk-parity", "spy", "agg", "monthly-rebalance"],
  },
  {
    slug: "monthly-rebalance",
    term: "Monthly Rebalance",
    category: "research",
    definition:
      "Monthly rebalancing resets portfolio weights to their target allocation at the start of each month, selling assets that have appreciated and buying those that have declined. It imposes discipline and systematically harvests the mean-reversion tendency of asset returns. More frequent rebalancing captures smaller dislocations but incurs higher transaction costs; monthly is the most common institutional cadence.",
    related: ["risk-parity", "60-40-benchmark", "rebalancing"],
  },
  {
    slug: "carry-trade",
    term: "FX Carry Trade",
    category: "research",
    definition:
      "The FX carry trade strategy involves going long the highest-yielding G10 currencies and short the lowest-yielding ones, capturing the interest rate differential. EconoSift's implementation goes long the top 3 highest-carry currencies (equally weighted) and short the bottom 3 lowest-carry currencies, rebalanced monthly, and plotted against the DXY for comparison. Carry trades historically generate steady positive returns punctuated by sharp crashes during risk-off events.",
    related: ["fx-carry", "carry-annualised", "g10-currencies", "vol-adjusted-carry"],
  },
  {
    slug: "cross-sectional-momentum",
    term: "Cross-Sectional Momentum",
    category: "research",
    definition:
      "Cross-sectional momentum ranks stocks within a universe by their past return over a lookback period (1-month, 3-month, 6-month, or 12-month-minus-1-month), then sorts them into deciles from weakest (decile 1) to strongest (decile 10). The strategy is long the top decile and short the bottom decile. It is distinct from time-series momentum (trend-following) — cross-sectional momentum is about relative performance within a group. EconoSift's Research Hub implements this for Dow 30 (default) with Nasdaq and S&P 500 available via 🔴 button.",
    related: ["momentum-signal", "deciles", "12m1m-momentum", "realized-moments"],
  },
  {
    slug: "momentum-signal",
    term: "Signal (Momentum Lookback)",
    category: "research",
    definition:
      "The momentum signal is the prior return period used to rank stocks: 1-month, 3-month, 6-month, or 12-month-minus-1-month (skip-month). The 12M-1M signal — classic academic momentum — uses the prior 12 months of returns excluding the most recent month, which avoids the short-term reversal effect. Different signals work better in different market regimes; the 6-month and 12M-1M signals are the most widely used.",
    related: ["cross-sectional-momentum", "12m1m-momentum", "deciles"],
  },
  {
    slug: "deciles",
    term: "Deciles (Momentum)",
    category: "research",
    definition:
      "In momentum analysis, deciles divide the ranked universe into 10 equal-sized groups: decile 1 contains the weakest prior returns (losers), decile 10 contains the strongest (winners). The difference between the top and bottom decile's forward returns measures the momentum premium. A healthy momentum strategy shows a monotonic increase in forward returns from decile 1 to decile 10.",
    related: ["cross-sectional-momentum", "momentum-signal", "12m1m-momentum"],
  },
  {
    slug: "12m1m-momentum",
    term: "12M-1M (Skip-Month Momentum)",
    category: "research",
    definition:
      "The 12-month-minus-1-month momentum signal uses the prior 12 months of total return excluding the most recent month. Skipping the most recent month avoids the short-term reversal effect — stocks that performed well over the last month tend to underperform the next month (and vice versa), which would dilute the momentum signal. This methodology was established by Jegadeesh and Titman (1993) in their foundational momentum paper.",
    related: ["cross-sectional-momentum", "momentum-signal", "deciles"],
  },
  {
    slug: "realized-moments",
    term: "Realized Moments",
    category: "research",
    definition:
      "Realized moments are statistical properties — variance, skewness, and excess kurtosis — computed from historical daily price data over rolling windows (21, 63, 252 trading days). Unlike theoretical moments of a distribution, these are 'realised' from actual observed returns. They provide a richer characterisation of return behaviour than just mean and variance. EconoSift's Research Hub provides realised moments for any ticker, using Garman-Klass variance for improved efficiency.",
    related: ["garman-klass-variance", "realized-skewness", "realized-kurtosis", "cross-sectional-momentum"],
  },
  {
    slug: "garman-klass-variance",
    term: "Garman-Klass Variance",
    category: "research",
    definition:
      "The Garman-Klass estimator is an OHLC-based realised variance formula: σ² = 0.5 × ln(H/L)² − (2·ln(2) − 1) × ln(C/O)². It uses opening, high, low, and closing prices to produce a more efficient variance estimate than the standard close-to-close estimator — it extracts additional information from intraday range. Garman-Klass can occasionally produce negative values (when the overnight gap dominates), which EconoSift clips at zero before taking the square root.",
    related: ["realized-moments", "realized-skewness", "realized-kurtosis", "volatility"],
  },
  {
    slug: "realized-skewness",
    term: "Realized Skewness",
    category: "research",
    definition:
      "Realized skewness measures the asymmetry of the daily return distribution over a rolling window. Positive skewness means the distribution has a longer right tail (more large positive returns than negative ones of the same magnitude); negative skewness means fatter left tail (crash risk). Investors generally prefer positive skewness — lottery-like upside — but many assets, especially equities, exhibit negative skewness. EconoSift's Research Hub reports rolling realized skewness at 21D, 63D, and 252D windows.",
    related: ["realized-moments", "realized-kurtosis", "garman-klass-variance"],
  },
  {
    slug: "realized-kurtosis",
    term: "Realized Excess Kurtosis",
    category: "research",
    definition:
      "Realized excess kurtosis measures the 'tailedness' of the return distribution beyond what a normal distribution would predict. Excess kurtosis > 0 indicates fatter tails (more extreme events) than normal — which is nearly universal in financial returns. High kurtosis warns that extreme moves (crashes or rallies) occur more frequently than standard risk models assume. EconoSift reports rolling realized excess kurtosis at 21D, 63D, and 252D windows.",
    related: ["realized-moments", "realized-skewness", "garch", "fat-tails"],
  },
  {
    slug: "cross-sectional-tail",
    term: "Cross-Sectional Tail-Return Test",
    category: "research",
    definition:
      "The cross-sectional tail-return test sorts stocks by their prior 1-month realised skewness and measures the forward 1-month return of each skewness decile. It tests whether stocks with lottery-like positive skew in the recent past subsequently underperform (the MAX effect) — the finding that high-skew, high-volatility stocks tend to deliver poor future returns as investors overpay for lottery-like payoffs.",
    related: ["realized-skewness", "cross-sectional-momentum", "realized-moments"],
  },

  // ════════════════════════════════════════════════════════════════
  // 13. Sector & Industry Analysis
  // ════════════════════════════════════════════════════════════════
  {
    slug: "spdr-sector-etfs",
    term: "SPDR Sector ETFs",
    category: "sectors",
    definition:
      "The Select Sector SPDRs are a family of 11 ETFs that each track a specific S&P 500 GICS sector: XLK (Technology), XLF (Financials), XLV (Health Care), XLE (Energy), XLI (Industrials), XLY (Consumer Discretionary), XLP (Consumer Staples), XLB (Materials), XLRE (Real Estate), XLC (Communication Services), and XLU (Utilities). They provide pure-play sector exposure with high liquidity and are the foundation of EconoSift's Sectors page for sector rotation analysis.",
    related: ["xlk", "xlf", "sector-rotation", "aum"],
  },
  {
    slug: "xlk",
    term: "XLK (Technology Sector SPDR)",
    category: "sectors",
    definition:
      "XLK is the largest SPDR sector ETF by market cap, tracking the Technology sector of the S&P 500. Its top holdings are dominated by Apple, Microsoft, and Nvidia. Technology has been the best-performing S&P 500 sector over the past two decades, driven by secular digitisation trends. XLK's performance is heavily influenced by semiconductor cycles, cloud computing spending, and AI-related investment.",
    related: ["spdr-sector-etfs", "xlf", "xly", "sector-rotation"],
  },
  {
    slug: "xlf",
    term: "XLF (Financials Sector SPDR)",
    category: "sectors",
    definition:
      "XLF tracks the Financials sector — banks, insurance companies, capital markets firms, and diversified financials. It is highly sensitive to interest rates (banks earn more when rates are higher, all else equal) and the shape of the yield curve. Financials tend to outperform in early-cycle and rising-rate environments. Top holdings include Berkshire Hathaway, JPMorgan, and Visa.",
    related: ["spdr-sector-etfs", "xlk", "yield-curve", "sector-rotation"],
  },
  {
    slug: "aum",
    term: "AUM (Assets Under Management)",
    category: "sectors",
    definition:
      "Assets Under Management is the total market value of all investments managed by a fund, ETF, or asset manager. For sector ETFs, AUM indicates the popularity and liquidity of the fund — larger AUM generally means tighter bid-ask spreads and lower risk of fund closure. AUM changes are driven by both market movements and investor flows (new money entering or leaving).",
    related: ["spdr-sector-etfs", "etf", "market-cap"],
  },
  {
    slug: "sector-rotation",
    term: "Sector Rotation Clock (Sam Stovall)",
    category: "sectors",
    definition:
      "The sector rotation clock — popularised by Sam Stovall of S&P Capital IQ — maps typical sector leadership to four phases of the business cycle. Early cycle favours Consumer Discretionary, Financials, Real Estate, and Industrials. Mid cycle favours Technology, Communication Services, and Industrials. Late cycle favours Energy, Materials, Consumer Staples, and Health Care. Recession favours defensives: Consumer Staples, Health Care, and Utilities. The EconoSift Sectors page visualises the current rotation positioning.",
    related: ["early-cycle", "mid-cycle", "late-cycle", "recession-phase", "regime-clock"],
  },
  {
    slug: "early-cycle",
    term: "Early Cycle",
    category: "sectors",
    definition:
      "The early cycle phase of the business cycle occurs as the economy emerges from recession — characterised by low interest rates, improving consumer confidence, and rising industrial production. Sectors that benefit most are those sensitive to the initial recovery in spending and credit: Consumer Discretionary, Financials, Real Estate, and Industrials. This phase historically offers the strongest equity returns.",
    related: ["sector-rotation", "mid-cycle", "late-cycle", "recession-phase"],
  },
  {
    slug: "mid-cycle",
    term: "Mid Cycle",
    category: "sectors",
    definition:
      "The mid cycle is typically the longest phase — characterised by steady growth, stable inflation, and a maturing expansion. Technology, Communication Services, and Industrials tend to lead as businesses invest in productivity and consumers upgrade. Credit conditions remain favourable. Mid-cycle is generally supportive for equities but with more moderate returns than the early cycle.",
    related: ["sector-rotation", "early-cycle", "late-cycle", "recession-phase"],
  },
  {
    slug: "late-cycle",
    term: "Late Cycle",
    category: "sectors",
    definition:
      "The late cycle occurs when the economy begins to overheat — growth is above trend, inflation is rising, and the central bank is tightening. Energy, Materials, Consumer Staples, and Health Care tend to lead as input costs rise and investors rotate toward defensives. Equity returns become more volatile and the risk of recession increases.",
    related: ["sector-rotation", "early-cycle", "mid-cycle", "recession-phase", "tightening"],
  },
  {
    slug: "recession-phase",
    term: "Recession Phase",
    category: "sectors",
    definition:
      "The recession phase is characterised by contracting economic activity, falling corporate earnings, and rising unemployment. Defensive sectors — Consumer Staples, Health Care, and Utilities — tend to outperform because demand for their products is relatively inelastic. Financials can also perform if the yield curve steepens in anticipation of recovery. Equity returns are typically negative in this phase.",
    related: ["sector-rotation", "late-cycle", "regime-clock", "recession"],
  },
  {
    slug: "industry-drill-down",
    term: "Industry Drill-Down",
    category: "sectors",
    definition:
      "Industry drill-down is the process of decomposing a broad sector into its constituent industries and individual stocks. For example, the Technology sector can be broken into Semiconductors, Software, Hardware, and IT Services. This reveals which specific industries are driving sector performance and enables more targeted analysis. EconoSift's Sectors page offers an industry drill-down for each sector ETF.",
    related: ["sectors", "spdr-sector-etfs", "sector-returns"],
  },
  {
    slug: "sector-returns",
    term: "Sector Returns by Period",
    category: "sectors",
    definition:
      "Sector returns by period shows the performance of each sector across different time horizons — 1 day, 1 week, 1 month, 3 months, YTD, and 1 year. This multi-period view reveals whether sector leadership is consistent (a sector leading across all periods) or rotating (different leaders at different horizons). EconoSift's Sectors page displays sector returns alongside relative performance versus the S&P 500 (vs SPY).",
    related: ["sector-rotation", "spdr-sector-etfs", "vs-spy"],
  },
  {
    slug: "vs-spy",
    term: "vs SPY (Relative to S&P 500)",
    category: "sectors",
    definition:
      "vs SPY is the relative return of a sector compared to the S&P 500 — simply the sector's return minus SPY's return over the same period. A positive vs-SPY number means the sector outperformed the broad market; negative means it underperformed. Relative performance is more informative than absolute performance for sector allocation decisions because it shows whether the sector is gaining or losing market leadership.",
    related: ["sector-returns", "spy", "relative-strength"],
  },

  // ════════════════════════════════════════════════════════════════
  // 14. Screening & Signals
  // ════════════════════════════════════════════════════════════════
  {
    slug: "stock-screener",
    term: "Stock Screener",
    category: "screening",
    definition:
      "A stock screener is a tool that filters a universe of stocks based on user-defined fundamental, technical, and sentiment criteria. It answers questions like 'Which S&P 500 stocks have P/E < 15, dividend yield > 3%, and are above their 200-day SMA?' EconoSift's Screener covers the S&P 500, Nasdaq 100, and Dow 30 with 20+ preset signals and an overnight-warmed cache for instant results across 9 result tabs.",
    related: ["preset", "screener-universe", "screening-signals"],
  },
  {
    slug: "preset",
    term: "Preset (Screening Signal)",
    category: "screening",
    definition:
      "Presets are predefined screening criteria that capture common investment themes — 'Golden Cross,' 'Undervalued,' 'High Dividend,' 'Quality Growth,' 'High Short Interest,' and more. Each preset translates to specific numeric filters (e.g., RSI > 70, P/E < 15). Presets allow users to run sophisticated screens without manually constructing filter logic. EconoSift offers 20+ presets on the Screener page.",
    related: ["stock-screener", "screening-signals", "golden-cross"],
  },
  {
    slug: "top-gainers",
    term: "Top Gainers",
    category: "screening",
    definition:
      "Top gainers are the stocks with the highest positive daily percentage return within a given universe. They represent the strongest momentum on the day and are often driven by earnings beats, analyst upgrades, or sector-wide catalysts. EconoSift's Screener includes a Top Gainers tab for each index universe.",
    related: ["top-losers", "screener", "momentum-signal"],
  },
  {
    slug: "near-52-week-high",
    term: "Near 52-Week High",
    category: "screening",
    definition:
      "A stock is 'near its 52-week high' when its current price is within a small threshold — typically 5% — of the highest price it has traded at over the past 52 weeks. These stocks are exhibiting price strength and are often in established uptrends. The EconoSift screener includes a Near 52-Week High preset. However, stocks near highs can be overextended; the signal is best combined with valuation and fundamental filters.",
    related: ["near-52-week-low", "52-week-high-low", "week-52-position"],
  },
  {
    slug: "near-52-week-low",
    term: "Near 52-Week Low",
    category: "screening",
    definition:
      "A stock is 'near its 52-week low' when its price is within 5% of the lowest price over the past year. These stocks may represent value opportunities — or they may be 'value traps' with deteriorating fundamentals. Screening for near-52-week-low stocks combined with strong fundamentals (high ROIC, low debt) can isolate genuine turnaround candidates from terminal decliners.",
    related: ["near-52-week-high", "52-week-high-low", "deep-value"],
  },
  {
    slug: "overbought",
    term: "Overbought (RSI > 70)",
    category: "screening",
    definition:
      "A stock is considered overbought when its RSI-14 exceeds 70, suggesting the price may have risen too far, too fast and could be due for a pullback. However, in strong uptrends, stocks can remain overbought for extended periods — RSI can reach 80+ and stay there while price continues rising. Overbought is best used as a caution flag rather than a standalone sell signal.",
    related: ["oversold", "rsi", "stochastic-rsi"],
  },
  {
    slug: "oversold",
    term: "Oversold (RSI < 30)",
    category: "screening",
    definition:
      "A stock is oversold when RSI-14 falls below 30, indicating the price may have declined too sharply and could bounce. Oversold conditions often occur during panic selling. Like overbought, oversold can persist — in a crash, RSI can stay below 30 while price continues falling. The best oversold signals occur when RSI crosses back above 30 (exit from oversold territory).",
    related: ["overbought", "rsi", "stochastic-rsi"],
  },
  {
    slug: "high-beta",
    term: "High Beta (>1.5)",
    category: "screening",
    definition:
      "High-beta stocks have a beta greater than 1.5, meaning they amplify market moves — a 1% S&P 500 move translates to >1.5% for the stock, on average. In bull markets, high-beta stocks tend to outperform; in bear markets, they underperform sharply. The EconoSift screener includes a High Beta preset for identifying amplified-market-exposure names.",
    related: ["beta", "low-volatility", "capm"],
  },
  {
    slug: "undervalued-screener",
    term: "Undervalued (Screen)",
    category: "screening",
    definition:
      "The Undervalued preset on EconoSift's Screener filters for stocks with P/E below 15 and P/B below 1.5 — classic value criteria. These stocks trade at low multiples of earnings and book value, suggesting the market may be undervaluing them. Low multiples alone are not enough; the best value opportunities also show earnings stability, manageable debt, and a catalyst for re-rating.",
    related: ["deep-value", "pe-ratio", "pb-ratio", "value-investing"],
  },
  {
    slug: "high-dividend",
    term: "High Dividend Yield (>3%)",
    category: "screening",
    definition:
      "The High Dividend preset screens for stocks with dividend yields above 3%. These are typically mature, cash-generative companies returning capital to shareholders. The key risk with high-dividend screens is that a stock's yield may be high because the price has fallen due to fundamental deterioration — the dividend may be unsustainable. Always cross-check dividend yield with payout ratio and FCF coverage.",
    related: ["dividend-yield", "payout-ratio", "fcf-yield"],
  },
  {
    slug: "quality-growth",
    term: "Quality Growth",
    category: "screening",
    definition:
      "Quality Growth combines profitability and growth criteria: ROE > 15%, Revenue Growth > 10%, and Net Margin > 10%. It identifies companies that are both highly profitable and expanding — the 'compounders.' These are the businesses most likely to create sustainable long-term shareholder value. EconoSift's Screener includes Quality Growth as a preset signal.",
    related: ["roe", "revenue-growth", "net-margin", "roic"],
  },
  {
    slug: "deep-value",
    term: "Deep Value",
    category: "screening",
    definition:
      "Deep Value is an aggressive value screen: P/B < 1.0 (trading below book value) and P/E < 10. These stocks are priced as if the market expects little to no future value creation. Some are genuine bargains; others are value traps — cheap for good reason. Deep value investing requires discriminating between temporary distress and terminal decline. Classic practitioners include Benjamin Graham and Walter Schloss.",
    related: ["undervalued-screener", "pb-ratio", "pe-ratio", "book-value"],
  },
  {
    slug: "high-short-interest",
    term: "High Short Interest",
    category: "screening",
    definition:
      "The High Short Interest preset flags stocks with short float above 20% — meaning more than one-fifth of available shares have been sold short. High short interest indicates deep market scepticism and carries both opportunity (short squeeze potential) and risk (the shorts may be right). Stocks with high short interest and improving fundamentals are the classic short-squeeze candidates.",
    related: ["short-float", "short-ratio", "short-squeeze"],
  },
  {
    slug: "unusual-volume",
    term: "Unusual Volume",
    category: "screening",
    definition:
      "The Unusual Volume preset identifies stocks where today's trading volume exceeds 2× the 20-day average. Elevated volume often accompanies institutional accumulation or distribution, earnings surprises, or news catalysts. It is a useful flag for identifying stocks 'in play' — something is happening that warrants attention. EconoSift screens for unusual volume across all index universes.",
    related: ["volume-ratio", "average-volume", "obv"],
  },
  {
    slug: "earnings-revision",
    term: "Earnings Revision (30d)",
    category: "screening",
    definition:
      "The Earnings Revision preset screens for stocks where analyst EPS estimates have changed significantly over the past 30 days. Upward revisions (positive earnings momentum) are a powerful signal — stocks with rising estimates tend to outperform, as the revision trend often precedes actual earnings beats. Downward revisions are a red flag. The magnitude and breadth of revisions matter more than the direction alone.",
    related: ["forward-eps", "analyst-estimates", "forward-pe"],
  },

  // ════════════════════════════════════════════════════════════════
  // 15. ESG & Fraud Detection
  // ════════════════════════════════════════════════════════════════
  {
    slug: "piotroski-f-score",
    term: "Piotroski F-Score",
    category: "esg",
    definition:
      "The Piotroski F-Score is a 9-point fundamental strength scoring system developed by accounting professor Joseph Piotroski. It awards one point for each of nine criteria across three categories: profitability (ROA, operating cash flow, change in ROA, accruals), leverage/liquidity (change in leverage, change in current ratio, share dilution), and operating efficiency (gross margin change, asset turnover change). A score of 8–9 indicates strong financial health; 0–2 signals distress. The F-Score was designed to separate value-stock winners from losers.",
    related: ["altman-z-score", "beneish-m-score", "ohlson-o-score", "dupont-analysis"],
  },
  {
    slug: "altman-z-score",
    term: "Altman Z-Score",
    category: "esg",
    definition:
      "The Altman Z-Score is a bankruptcy prediction model developed by NYU professor Edward Altman in 1968. It combines five financial ratios — working capital/total assets, retained earnings/total assets, EBIT/total assets, market value of equity/total liabilities, and sales/total assets — into a single score. Z < 1.8 indicates distress (high bankruptcy risk); Z > 3.0 indicates safety. It remains one of the most widely used credit risk models, though the original coefficients were calibrated for manufacturing firms.",
    related: ["piotroski-f-score", "beneish-m-score", "ohlson-o-score"],
  },
  {
    slug: "beneish-m-score",
    term: "Beneish M-Score",
    category: "esg",
    definition:
      "The Beneish M-Score is an earnings manipulation detection model developed by professor Messod Beneish. It uses eight financial ratios — including days sales in receivables index, gross margin index, asset quality index, sales growth index, depreciation index, SG&A index, leverage index, and total accruals to total assets — to identify companies likely to be manipulating earnings. An M-Score greater than −2.22 flags a company as a likely manipulator. It gained fame for flagging Enron before its collapse.",
    related: ["piotroski-f-score", "altman-z-score", "ohlson-o-score", "earnings-quality"],
  },
  {
    slug: "ohlson-o-score",
    term: "Ohlson O-Score",
    category: "esg",
    definition:
      "The Ohlson O-Score is a bankruptcy probability model developed by James Ohlson in 1980. Unlike the Altman Z-Score, it uses a logistic regression framework and includes variables like size (log of total assets), total liabilities/total assets, working capital/total assets, and net income. The output is a default probability — higher scores indicate greater bankruptcy risk. It is one of several distress models available on EconoSift's valuation pages.",
    related: ["piotroski-f-score", "altman-z-score", "beneish-m-score"],
  },
  {
    slug: "dupont-analysis",
    term: "DuPont Analysis",
    category: "esg",
    definition:
      "DuPont analysis decomposes ROE into its component drivers to understand what is powering — or dragging — a company's profitability. The 3-factor DuPont: ROE = Net Margin × Asset Turnover × Equity Multiplier (leverage). The 5-factor DuPont adds tax burden and interest burden for a finer-grained view. A company with high ROE driven by leverage (high equity multiplier) is riskier than one driven by high margins or asset efficiency. EconoSift provides both 3-factor and 5-factor DuPont decompositions.",
    related: ["roe", "net-margin", "asset-turnover", "debt-to-equity"],
  },
  {
    slug: "cash-conversion-cycle",
    term: "CCC (Cash Conversion Cycle)",
    category: "esg",
    definition:
      "The Cash Conversion Cycle measures how long — in days — it takes a company to convert its investments in inventory and other resources into cash from sales. CCC = Days Inventory Outstanding (DIO) + Days Sales Outstanding (DSO) − Days Payables Outstanding (DPO). A shorter CCC means the company is more efficient at turning working capital into cash. Negative CCC — common for companies like Amazon that collect from customers before paying suppliers — means the business is funded by its suppliers.",
    related: ["dso", "dio", "dpo", "working-capital"],
  },
  {
    slug: "dso",
    term: "DSO (Days Sales Outstanding)",
    category: "esg",
    definition:
      "Days Sales Outstanding = (Accounts Receivable / Revenue) × 365. It measures how many days on average it takes a company to collect payment after a sale. A rising DSO suggests the company is extending more credit or having collection problems — a potential red flag. Industry norms vary significantly: a manufacturer might have DSO of 45 days; a retailer mostly paid in cash has DSO near 0.",
    related: ["cash-conversion-cycle", "dio", "dpo", "receivables-turnover"],
  },
  {
    slug: "dio",
    term: "DIO (Days Inventory Outstanding)",
    category: "esg",
    definition:
      "Days Inventory Outstanding = (Average Inventory / COGS) × 365. It measures how many days on average inventory sits before being sold. High or rising DIO can signal overstocking, obsolescence risk, or weak demand. Low DIO generally indicates efficient inventory management, though too low a DIO could mean the company is understocked and missing sales opportunities.",
    related: ["cash-conversion-cycle", "dso", "dpo", "inventory-turnover"],
  },
  {
    slug: "dpo",
    term: "DPO (Days Payables Outstanding)",
    category: "esg",
    definition:
      "Days Payables Outstanding = (Accounts Payable / COGS) × 365. It measures how long a company takes to pay its suppliers. A higher DPO is generally beneficial — the company is using supplier credit as free financing. However, extremely high DPO can signal cash flow problems or strained supplier relationships. DPO is subtracted in the CCC formula because delaying payments shortens the cash cycle.",
    related: ["cash-conversion-cycle", "dso", "dio"],
  },

  // ════════════════════════════════════════════════════════════════
  // 16. Snowflake Composite Score
  // ════════════════════════════════════════════════════════════════
  {
    slug: "snowflake-score",
    term: "Snowflake Composite Score",
    category: "snowflake",
    definition:
      "The Snowflake Score is EconoSift's 5-axis composite stock quality assessment scored 0–10 across five dimensions: Value (valuation attractiveness), Growth (revenue/earnings trajectory), Performance (historical risk-adjusted returns), Health (balance sheet strength), and Dividend (yield and sustainability). The Overall Score is a weighted average of all five axes, giving a holistic quality assessment. A score of 8+ suggests a high-quality stock; below 4 signals significant concerns. The Snowflake is visualised as a radar chart with a summary verdict.",
    related: ["value-axis", "growth-axis", "performance-axis", "health-axis", "dividend-axis"],
  },
  {
    slug: "value-axis",
    term: "Value Axis (Snowflake)",
    category: "snowflake",
    definition:
      "The Value axis of the Snowflake score assesses a stock's valuation attractiveness using metrics like P/E, P/B, EV/EBITDA, FCF yield, and the upside/downside from EconoSift's DCF engine. A high Value score means the stock appears cheap on multiple valuation dimensions. A low score suggests the stock is expensive — which may be justified by high growth, but the Snowflake separates value from growth for clarity.",
    related: ["snowflake-score", "growth-axis", "pe-ratio", "dcf"],
  },
  {
    slug: "growth-axis",
    term: "Growth Axis (Snowflake)",
    category: "snowflake",
    definition:
      "The Growth axis evaluates a company's revenue and earnings growth trajectory — both historical (past 3–5 years) and forward (analyst estimates). It considers the level, consistency, and quality of growth. High and consistent growth earns a high score; stagnant or declining companies score low. Growth and Value axes are often inversely related — the Snowflake makes this trade-off explicit.",
    related: ["snowflake-score", "value-axis", "revenue-growth", "eps-growth"],
  },
  {
    slug: "performance-axis",
    term: "Performance Axis (Snowflake)",
    category: "snowflake",
    definition:
      "The Performance axis scores historical risk-adjusted returns — incorporating Sharpe ratio, Sortino ratio, and total return relative to the market. It rewards stocks that have delivered strong returns efficiently, without excessive volatility. A high Performance score with a low Value score may indicate strong momentum but expensive valuation.",
    related: ["snowflake-score", "sharpe-ratio", "sortino-ratio", "beta"],
  },
  {
    slug: "health-axis",
    term: "Health Axis (Snowflake)",
    category: "snowflake",
    definition:
      "The Health axis assesses balance sheet strength using debt ratios (D/E, Net Debt/EBITDA), liquidity ratios (current, quick), interest coverage, and fraud-risk scores (Altman Z, Piotroski F, Beneish M). A high Health score means the company has a strong, low-risk financial position. This is the most defensive of the five Snowflake axes.",
    related: ["snowflake-score", "debt-to-equity", "altman-z-score", "piotroski-f-score"],
  },
  {
    slug: "dividend-axis",
    term: "Dividend Axis (Snowflake)",
    category: "snowflake",
    definition:
      "The Dividend axis scores dividend yield and sustainability — incorporating dividend yield, payout ratio, dividend growth history, and FCF coverage of dividends. A high score indicates an attractive, well-covered dividend. Companies that do not pay dividends score zero on this axis but can still achieve high overall Snowflake scores from the other four axes.",
    related: ["snowflake-score", "dividend-yield", "payout-ratio", "fcf-yield"],
  },
  {
    slug: "snowflake-verdict",
    term: "Verdict (Snowflake)",
    category: "snowflake",
    definition:
      "The Snowflake verdict is a textual summary of the composite analysis — ranging from 'Strong Buy' (overall score ≥ 8) through 'Buy,' 'Neutral,' 'Sell,' to 'Strong Sell' (overall score < 3). It provides an at-a-glance recommendation. The verdict is accompanied by the Top Rewards (highest-scoring components) and Top Risks (lowest-scoring components), giving investors a balanced view of strengths and weaknesses.",
    related: ["snowflake-score", "top-rewards", "top-risks"],
  },

  // ════════════════════════════════════════════════════════════════
  // 17. Dashboard & Market Breadth
  // ════════════════════════════════════════════════════════════════
  {
    slug: "market-breadth",
    term: "Market Breadth",
    category: "dashboard",
    definition:
      "Market breadth measures the number of stocks participating in a market move — advancing versus declining issues within an index. Strong breadth (many stocks rising together) confirms a healthy rally; weak breadth (a few large-caps driving the index while most stocks fall) warns that the rally may be fragile. Breadth indicators are among the most reliable leading indicators of market turning points. EconoSift's Dashboard displays breadth for the S&P 500.",
    related: ["advancing-declining", "mcclellan-oscillator", "cumulative-ad-line", "new-highs-new-lows"],
  },
  {
    slug: "mcclellan-oscillator",
    term: "McClellan Oscillator",
    category: "dashboard",
    definition:
      "The McClellan Oscillator is a market breadth indicator calculated as the difference between the 19-day EMA and the 39-day EMA of daily advancing minus declining issues on the NYSE. Positive readings indicate short-term breadth momentum is above the longer-term trend (bullish); negative readings indicate the opposite. Extreme readings (>+100 or <−100) signal overbought or oversold conditions for the broad market.",
    related: ["mcclellan-summation-index", "market-breadth", "advancing-declining"],
  },
  {
    slug: "mcclellan-summation-index",
    term: "McClellan Summation Index",
    category: "dashboard",
    definition:
      "The McClellan Summation Index is the cumulative running total of the McClellan Oscillator. It provides a longer-term breadth perspective — a rising Summation Index confirms a bull market; a declining one signals deteriorating breadth and potential trend change. Divergences between the Summation Index and the S&P 500 can be powerful warning signals.",
    related: ["mcclellan-oscillator", "cumulative-ad-line", "market-breadth"],
  },
  {
    slug: "cumulative-ad-line",
    term: "Cumulative A-D Line",
    category: "dashboard",
    definition:
      "The Cumulative Advance-Decline Line is the running sum of (advancing issues − declining issues) each day. It is the simplest and most intuitive breadth indicator. If the A-D line is rising alongside the index, the rally is broad-based and healthy. If the index makes a new high but the A-D line does not — a 'breadth divergence' — it is a classic warning that the rally is narrowing and may reverse.",
    related: ["market-breadth", "mcclellan-oscillator", "advancing-declining"],
  },
  {
    slug: "new-highs-new-lows",
    term: "New Highs / New Lows",
    category: "dashboard",
    definition:
      "New highs and new lows track the number of stocks hitting 52-week highs or 52-week lows on a given day. The ratio of new highs to new lows is a powerful trend confirmation tool. In a healthy bull market, new highs consistently outnumber new lows. When new lows start expanding while the index is still near highs, it signals internal deterioration. How EconoSift counts them: S&P 500 members on that session (point-in-time membership) whose intraday high (low) reaches the highest high (lowest low) of the trailing 252 sessions, using prices as traded; a session that ties its 52-week extreme counts, and a member needs at least 30 sessions of history. Published counts use their own windows, universes and close-vs-intraday rules, so the numbers can differ from a newspaper or exchange figure.",
    related: ["market-breadth", "52-week-high-low", "advancing-declining"],
  },
  {
    slug: "fear-greed",
    term: "Fear & Greed Index",
    category: "dashboard",
    definition:
      "The Fear & Greed Index is a composite sentiment indicator that aggregates multiple market signals — stock price breadth, market momentum, junk bond demand, safe haven demand, put/call ratio, and market volatility — into a single 0–100 scale. 0 represents Extreme Fear (oversold, potentially a buying opportunity); 100 represents Extreme Greed (overbought, potentially due for a pullback). It is a contrarian indicator: extreme fear often precedes rallies; extreme greed often precedes corrections. EconoSift's Dashboard displays the index with its sub-component breakdown.",
    related: ["market-breadth", "put-call-oi-ratio", "vix", "movers"],
  },
  {
    slug: "top-movers",
    term: "Top Movers",
    category: "dashboard",
    definition:
      "Top movers are the best and worst performing stocks within an index for the current trading day. They provide a real-time pulse on which names and sectors are driving (or dragging) market performance. EconoSift's Dashboard displays the top 10 gainers and losers for the selected index, with percentage changes and brief fundamental snapshots.",
    related: ["top-gainers", "top-losers", "market-breadth"],
  },
  {
    slug: "global-indices",
    term: "Global Indices",
    category: "dashboard",
    definition:
      "Global indices tracked on the Dashboard include the S&P 500 (US), FTSE 100 (UK), Nikkei 225 (Japan), DAX (Germany), Shanghai Composite (China), and others. They provide a worldwide equity market snapshot — showing which regions are leading or lagging. Major divergences between US and international indices can signal shifting global capital flows.",
    related: ["sp-500", "dow-30", "nasdaq-composite", "benchmark"],
  },
  {
    slug: "us-markets-session",
    term: "US Markets Session",
    category: "dashboard",
    definition:
      "The US Markets Session indicator shows whether US equity markets are currently open, closed, or in pre-market/after-hours trading. Regular trading hours are 9:30 AM to 4:00 PM ET, Monday through Friday (excluding holidays). Knowing the session status is important because price data and liquidity characteristics differ significantly between regular and extended-hours trading.",
    related: ["market-breadth", "sp-500", "calendar"],
  },
  {
    slug: "advancing-declining",
    term: "Advancing / Declining / Unchanged",
    category: "dashboard",
    definition:
      "These are the three categories of daily stock movement within an index: advancing (closed higher), declining (closed lower), and unchanged (closed flat). The net advance-decline (advancing minus declining) is the fundamental building block of all breadth indicators. A day with more advancers than decliners is positive for breadth, even if the index itself is flat or slightly down.",
    related: ["market-breadth", "cumulative-ad-line", "mcclellan-oscillator"],
  },

  // ════════════════════════════════════════════════════════════════
  // 18. Macro Regime Classification
  // ════════════════════════════════════════════════════════════════
  {
    slug: "regime-quadrant",
    term: "Regime (Quadrant)",
    category: "regime",
    definition:
      "A macro regime is an economic state classification based on the combination of GDP growth and CPI inflation relative to thresholds. The four regimes — Goldilocks, Overheating, Slowdown, and Stagflation — each have distinct implications for asset allocation. The regime framework simplifies complex macro conditions into actionable investment context. EconoSift's Macro page displays the current regime and its historical evolution via the regime clock.",
    related: ["goldilocks", "overheating", "slowdown", "stagflation", "regime-clock"],
  },
  {
    slug: "goldilocks",
    term: "Goldilocks",
    category: "regime",
    definition:
      "Goldilocks is the ideal macro regime: GDP growth above trend (typically > 2%) AND inflation below threshold (typically < 2.5%) — an economy that is neither too hot nor too cold. This is the most favourable environment for equities, as growth supports earnings while low inflation keeps interest rates and discount rates low. Growth stocks tend to perform particularly well in Goldilocks environments.",
    related: ["overheating", "slowdown", "stagflation", "regime-quadrant"],
  },
  {
    slug: "overheating",
    term: "Overheating",
    category: "regime",
    definition:
      "Overheating is the regime of strong growth AND high inflation — the economy is running above capacity, and price pressures are building. This typically prompts central bank tightening, which compresses equity valuations. Commodities, value stocks, and inflation-hedging assets tend to outperform. Overheating often precedes a transition to slowdown or stagflation as rate hikes bite.",
    related: ["goldilocks", "stagflation", "slowdown", "tightening", "regime-quadrant"],
  },
  {
    slug: "slowdown",
    term: "Slowdown",
    category: "regime",
    definition:
      "Slowdown (or disinflationary bust) is below-trend growth with low inflation — the post-tightening economic cooling. Defensive sectors (Consumer Staples, Health Care, Utilities) and bonds tend to outperform. Central banks typically shift from tightening to neutral or even easing in this regime. It can be a challenging environment for equities overall, though falling bond yields provide some valuation support.",
    related: ["goldilocks", "overheating", "stagflation", "recession-phase", "regime-quadrant"],
  },
  {
    slug: "stagflation",
    term: "Stagflation",
    category: "regime",
    definition:
      "Stagflation is the worst macro regime: weak or negative growth combined with high inflation. It is rare but devastating — central banks cannot easily cut rates to stimulate growth because inflation is already high. The 1970s oil shocks are the classic stagflationary episodes. Commodities and hard assets tend to perform best; equities and bonds both struggle.",
    related: ["goldilocks", "overheating", "slowdown", "regime-quadrant"],
  },
  {
    slug: "regime-clock",
    term: "Regime Clock",
    category: "regime",
    definition:
      "The regime clock is a 2×2 scatter plot with GDP growth on the horizontal axis and CPI inflation on the vertical axis, divided into four colour-coded quadrants. Historical data points trace the economy's path through the quadrants over time, with the most recent point highlighted as the current regime. EconoSift's regime clock provides a visual macro context for investment decisions.",
    related: ["regime-quadrant", "goldilocks", "overheating", "sector-rotation"],
  },
  {
    slug: "gdp-threshold",
    term: "GDP Threshold",
    category: "regime",
    definition:
      "The GDP threshold is the growth rate boundary used to classify the economy as 'above trend' (right side of the regime clock) or 'below trend' (left side). The default threshold on EconoSift is 2.0% real GDP growth, roughly the long-run US trend. Adjusting the threshold changes regime classifications: a higher threshold shrinks the 'Goldilocks' and 'Overheating' zones.",
    related: ["regime-clock", "cpi-threshold", "regime-quadrant", "gdp-growth"],
  },
  {
    slug: "cpi-threshold",
    term: "CPI Threshold",
    category: "regime",
    definition:
      "The CPI threshold separates 'low inflation' (bottom half of the regime clock) from 'high inflation' (top half). EconoSift's default is 2.5% — slightly above the Fed's 2% PCE target to allow for the typical CPI-PCE spread. Raising the threshold makes Goldilocks more common; lowering it makes Overheating and Stagflation more frequent.",
    related: ["regime-clock", "gdp-threshold", "regime-quadrant", "cpi-yoy"],
  },
  {
    slug: "ism-pmi",
    term: "ISM PMI (Purchasing Managers' Index)",
    category: "regime",
    definition:
      "The ISM Manufacturing PMI is a monthly survey-based diffusion index of US manufacturing activity. Readings above 50 indicate expansion; below 50 indicate contraction. It is one of the most timely and market-moving economic indicators — released on the first business day of each month. The new orders component is particularly forward-looking. PMI is tracked on EconoSift's Macro and Leading Indicators tabs.",
    related: ["leading-indicators", "cfnai", "industrial-production"],
  },
  {
    slug: "cfnai",
    term: "CFNAI (Chicago Fed National Activity Index)",
    category: "regime",
    definition:
      "The Chicago Fed National Activity Index is a weighted average of 85 existing monthly indicators of US economic activity. A zero reading indicates the economy is expanding at trend; positive values indicate above-trend growth; negative values indicate below-trend. The CFNAI-MA3 (three-month moving average) is used as a recession indicator — values below −0.7 historically signal recession.",
    related: ["ism-pmi", "leading-indicators", "gdp-growth"],
  },
  {
    slug: "gsci",
    term: "GSCPI (Global Supply Chain Pressure Index)",
    category: "regime",
    definition:
      "The GSCPI is a New York Fed index aggregating global transportation costs and supply chain indicators into a single measure. Positive readings indicate above-average supply chain pressure (delays, bottlenecks, rising shipping costs). It spiked dramatically during COVID and was a key leading indicator of the subsequent inflation surge. EconoSift tracks GSCPI on the Macro Leading Indicators tab.",
    related: ["ism-pmi", "ppi", "inflation"],
  },
  {
    slug: "is-lm-pc",
    term: "IS-LM-PC Framework",
    category: "regime",
    definition:
      "The IS-LM-PC framework is a macroeconomic model integrating the Goods Market (IS curve: investment-savings equilibrium), Money Market (LM curve: liquidity preference-money supply equilibrium), and Phillips Curve (PC: inflation-unemployment relationship). It explains how fiscal policy shifts the IS curve, monetary policy shifts the LM curve, and the resulting output-inflation dynamics. EconoSift's Macro Lab tab displays IS and LM curves normalised to a base year.",
    related: ["phillips-curve", "quantity-theory", "econ-lab"],
  },
  {
    slug: "phillips-curve",
    term: "Phillips Curve",
    category: "regime",
    definition:
      "The Phillips Curve describes the historical inverse relationship between unemployment and inflation — lower unemployment tends to coincide with higher inflation, and vice versa. It is a key building block of central bank policy: when unemployment is very low, central banks anticipate rising inflation and tighten preemptively. The relationship has flattened in recent decades, but it remains central to monetary policy frameworks.",
    related: ["is-lm-pc", "unemployment-rate", "inflation", "fed"],
  },
  {
    slug: "quantity-theory",
    term: "Quantity Theory of Money",
    category: "regime",
    definition:
      "The Quantity Theory of Money — expressed as MV = PQ — states that Money Supply (M) × Velocity (V) = Price Level (P) × Real Output (Q). It implies that, all else equal, an increase in the money supply leads to proportional inflation. EconoSift's Macro Inflation tab plots M2 money supply and GDP side by side to visualise the relationship. The theory is a long-run framework; in the short run, velocity can change and break the simple proportionality.",
    related: ["m2-money-supply", "inflation", "gdp", "is-lm-pc"],
  },

  // ════════════════════════════════════════════════════════════════
  // 19. Financial Conditions & Credit
  // ════════════════════════════════════════════════════════════════
  {
    slug: "nfci",
    term: "NFCI (National Financial Conditions Index)",
    category: "credit",
    definition:
      "The Chicago Fed's National Financial Conditions Index aggregates 105 indicators of US financial conditions in money markets, debt and equity markets, and the banking system. Negative values indicate financial conditions are looser than average (accommodative); positive values indicate tighter-than-average conditions. A reading above 0 signals financial stress. The NFCI is updated weekly and is a key input to Fed policy decisions.",
    related: ["stlfsi", "financial-conditions", "credit-spread", "fed"],
  },
  {
    slug: "stlfsi",
    term: "STLFSI (St. Louis Fed Financial Stress Index)",
    category: "credit",
    definition:
      "The St. Louis Fed Financial Stress Index measures the degree of financial stress in US markets using 18 weekly data series — including interest rates, yield spreads, and volatility indicators. A value of zero represents normal conditions; positive values indicate above-average stress. Spikes above 2–3 historically coincide with major financial disruptions. EconoSift uses the STLFSI alongside the NFCI on the Financial Conditions tab.",
    related: ["nfci", "financial-conditions", "ted-spread", "vix"],
  },
  {
    slug: "financial-conditions",
    term: "Financial Conditions",
    category: "credit",
    definition:
      "Financial conditions describe the overall ease or tightness of financing in the economy — encompassing interest rates, credit spreads, equity market conditions, and lending standards. Easy financial conditions support economic growth and risk-taking; tight conditions constrain activity. Central banks influence financial conditions directly through policy rates and balance sheet operations. EconoSift's Policy page provides a dedicated Financial Conditions tab with multiple indicators.",
    related: ["nfci", "stlfsi", "ig-oas", "fed-funds-rate"],
  },
  {
    slug: "epu",
    term: "EPU (Economic Policy Uncertainty Index)",
    category: "credit",
    definition:
      "The Economic Policy Uncertainty Index — developed by Baker, Bloom, and Davis — quantifies policy-related economic uncertainty by analysing newspaper coverage frequency of terms related to the economy, policy, and uncertainty. Elevated EPU is associated with lower investment, reduced hiring, and higher risk premia. The index spikes around elections, major legislation, and geopolitical crises. EconoSift displays EPU with a log-scale toggle on the Financial Conditions panel.",
    related: ["financial-conditions", "vix", "stlfsi"],
  },
  {
    slug: "cot",
    term: "COT (Commitments of Traders)",
    category: "credit",
    definition:
      "The Commitments of Traders report is a weekly CFTC publication showing the aggregate positions of different trader categories — commercial hedgers, large speculators, and small traders — in US futures markets. The net speculative position (long minus short) reveals where 'smart money' and 'dumb money' are positioned in assets like currencies, commodities, and Treasury futures. Extreme net speculative positions can be contrarian signals. EconoSift's Positioning tab on the Macro page displays COT data for major markets.",
    related: ["net-speculative-position", "net-commercial-position", "cot-index", "fx"],
  },
  {
    slug: "13f",
    term: "13F Filings",
    category: "credit",
    definition:
      "13F filings are quarterly SEC reports disclosing the long equity holdings of institutional investment managers with over $100 million in assets. They are filed 45 days after quarter-end, so the data is always slightly stale. Despite the lag, 13F data reveals institutional positioning trends — which stocks the 'whales' are accumulating or distributing. EconoSift's Markets page provides 13F analysis for individual tickers.",
    related: ["form-4", "insider-buy-sell", "institutional-ownership"],
  },
  {
    slug: "form-4",
    term: "Form 4 (Insider Transactions)",
    category: "credit",
    definition:
      "Form 4 is an SEC filing that corporate insiders — executives, directors, and 10%+ owners — must file within two business days of trading their company's stock. Insider buying is generally considered a stronger signal than selling (which can occur for diversification or tax reasons). Clusters of insider buying — multiple insiders buying near the same time — are considered particularly bullish. EconoSift's Markets page tracks Form 4 filings.",
    related: ["13f", "insider-buy-sell", "short-float"],
  },
  {
    slug: "insider-buy-sell",
    term: "Insider Buy / Sell",
    category: "credit",
    definition:
      "Insider transactions are stock purchases or sales by a company's officers, directors, or major shareholders. Insider buying is viewed as a vote of confidence — insiders only buy because they believe the stock will appreciate. Insider selling is more ambiguous: it may signal concern, but can also reflect pre-scheduled diversification, tax planning, or option exercise. The ratio of insider buying to selling is tracked as a market sentiment indicator.",
    related: ["form-4", "13f", "sentiment"],
  },

  // ════════════════════════════════════════════════════════════════
  // 20. Sovereign & Country Risk
  // ════════════════════════════════════════════════════════════════
  {
    slug: "sovereign-risk",
    term: "Sovereign Risk",
    category: "sovereign",
    definition:
      "Sovereign risk is the risk that a national government will default on its debt obligations or restructure them on terms unfavourable to creditors. It is assessed using a combination of fiscal metrics (debt/GDP, fiscal balance), external metrics (current account, foreign reserves), and market-based signals (CDS spreads, bond yield spreads versus safe havens). EconoSift's Sovereign page provides a traffic-light risk dashboard for 8 major developed economies using World Bank indicators.",
    related: ["debt-to-gdp", "current-account", "fiscal-balance", "traffic-light"],
  },
  {
    slug: "debt-to-gdp",
    term: "Debt/GDP",
    category: "sovereign",
    definition:
      "The government debt-to-GDP ratio is the most widely used metric of sovereign indebtedness — total gross government debt divided by annual nominal GDP. Japan has the highest among developed nations (>250%), while the US is above 120%. There is no magic threshold for danger — Japan has sustained high debt/GDP for decades due to domestic ownership and low rates — but rising ratios without a credible fiscal path eventually concern markets.",
    related: ["sovereign-risk", "fiscal-balance", "country-risk"],
  },
  {
    slug: "current-account",
    term: "Current Account (% of GDP)",
    category: "sovereign",
    definition:
      "The current account balance — expressed as % of GDP — measures a country's trade balance plus net income and transfers from abroad. A persistent deficit means the country is consuming more than it produces and must finance the gap through foreign borrowing. Large deficits (e.g., >5% of GDP) can signal vulnerability to sudden capital outflows. Surpluses indicate the country is a net lender to the rest of the world.",
    related: ["sovereign-risk", "fiscal-balance", "foreign-reserves"],
  },
  {
    slug: "fiscal-balance",
    term: "Fiscal Balance (% of GDP)",
    category: "sovereign",
    definition:
      "The fiscal balance is government revenue minus expenditure, as a percentage of GDP. A negative fiscal balance is a deficit — the government is borrowing to cover the gap. Persistent large deficits (>3% of GDP) add to the debt stock each year. A positive balance (surplus) is rare and signals fiscal discipline. Fiscal balance is a key World Bank indicator in EconoSift's sovereign risk panel.",
    related: ["debt-to-gdp", "sovereign-risk", "country-risk"],
  },
  {
    slug: "foreign-reserves",
    term: "Foreign Reserves Growth",
    category: "sovereign",
    definition:
      "Foreign reserves are central bank holdings of foreign currencies, gold, and SDRs used to back liabilities and influence exchange rate policy. Reserves growth (year-over-year) indicates whether a country is building or depleting its external buffers. Declining reserves — especially in emerging markets — is a classic warning sign of impending currency or debt crisis. It is one of the six KPIs in EconoSift's sovereign risk panel.",
    related: ["sovereign-risk", "current-account", "central-bank"],
  },
  {
    slug: "traffic-light",
    term: "Traffic-Light System (Risk)",
    category: "sovereign",
    definition:
      "The traffic-light system classifies sovereign risk indicators as Green (safe), Yellow (watch), or Red (warning) based on predefined thresholds. For example, Debt/GDP > 100% might be Yellow, > 150% Red. The system provides an intuitive visual dashboard: a country with all greens is in strong fiscal health; multiple reds signal serious concerns. EconoSift's Sovereign page uses traffic lights for 6 KPIs across 8 countries.",
    related: ["sovereign-risk", "country-risk", "composite-score-sovereign"],
  },
  {
    slug: "spread-vs-us",
    term: "Spread vs US (Sovereign Yield Spread)",
    category: "sovereign",
    definition:
      "The spread vs US is a country's 10-year government bond yield minus the US 10-year Treasury yield. It measures the credit risk premium markets demand for holding that country's debt instead of US debt. Germany and Japan often have negative spreads (their bonds yield less than US Treasuries). Widening spreads — particularly for Italy, Spain, or emerging markets — signal rising sovereign stress. EconoSift's Sovereign page calculates and ranks spreads for 8 major economies.",
    related: ["sovereign-risk", "foreign-10y", "yield-10y", "country-risk"],
  },
  {
    slug: "composite-score-sovereign",
    term: "Composite Score (Sovereign)",
    category: "sovereign",
    definition:
      "The sovereign composite score combines a market-implied risk score (from yield spreads vs US) with a fundamentals-based score (from World Bank indicator traffic lights) into a 0–100 aggregate. Lower scores indicate lower risk. A score below 30 is green (safe); 30–60 is yellow (watching); above 60 is red (high risk). This composite provides a balanced view that neither markets nor fundamentals alone can give.",
    related: ["spread-vs-us", "traffic-light", "sovereign-risk"],
  },

  // ════════════════════════════════════════════════════════════════
  // 21. Econometric Lab
  // ════════════════════════════════════════════════════════════════
  {
    slug: "pooled-ols",
    term: "Pooled OLS",
    category: "econlab",
    definition:
      "Pooled Ordinary Least Squares is a regression technique that estimates a single equation using panel data — combining cross-sectional (multiple countries) and time-series (multiple years) observations into one dataset. It treats all observations as independent, ignoring country-specific fixed effects. While simple, it can suffer from omitted variable bias if country-specific factors are important. EconoSift's Econometric Lab implements pooled OLS using numpy + scipy (no statsmodels dependency).",
    related: ["dependent-variable", "independent-variable", "coefficient", "r-squared-econ"],
  },
  {
    slug: "dependent-variable",
    term: "Dependent Variable (Y)",
    category: "econlab",
    definition:
      "The dependent variable is the outcome being explained or predicted in a regression model. In EconoSift's Econometric Lab, the user selects Y from available World Bank indicators (e.g., GDP Growth, Inflation, Unemployment). The regression estimates how changes in the independent variable(s) are associated with changes in the dependent variable.",
    related: ["independent-variable", "pooled-ols", "coefficient"],
  },
  {
    slug: "independent-variable",
    term: "Independent Variable (X)",
    category: "econlab",
    definition:
      "Independent variables (also called predictors or regressors) are the factors used to explain or predict the dependent variable. A user might regress GDP Growth (Y) on Investment/GDP, Education Spending, and Political Stability (Xs) to understand growth determinants. The Econometric Lab supports multiple independent variables in a single pooled OLS regression.",
    related: ["dependent-variable", "pooled-ols", "coefficient"],
  },
  {
    slug: "coefficient",
    term: "Coefficient (β)",
    category: "econlab",
    definition:
      "A regression coefficient estimates how much the dependent variable changes for a one-unit change in the independent variable, holding all other variables constant. A coefficient of 0.5 on 'Investment/GDP' means that a 1 percentage-point increase in the investment ratio is associated with 0.5 percentage points higher GDP growth, on average. The coefficient's practical importance depends on its magnitude, statistical significance, and the units of measurement.",
    related: ["standard-error", "t-statistic", "p-value", "pooled-ols"],
  },
  {
    slug: "standard-error",
    term: "Standard Error (SE)",
    category: "econlab",
    definition:
      "The standard error measures the precision of a coefficient estimate — how much the estimated coefficient would vary across different samples. A small SE relative to the coefficient suggests the estimate is precise; a large SE indicates uncertainty. The standard error is used to calculate t-statistics and confidence intervals. It is affected by sample size (more data → smaller SE) and the variance of the independent variable.",
    related: ["coefficient", "t-statistic", "p-value", "pooled-ols"],
  },
  {
    slug: "t-statistic",
    term: "t-Statistic (t-Stat)",
    category: "econlab",
    definition:
      "The t-statistic = Coefficient / Standard Error. It tests the null hypothesis that the true coefficient is zero (no relationship). As a rule of thumb, |t| > 2.0 is statistically significant at the 95% confidence level. The t-stat is the most commonly reported test statistic in regression output. EconoSift's Econometric Lab computes t-statistics using numpy linear algebra and scipy.stats.t for p-values.",
    related: ["p-value", "coefficient", "standard-error", "significance-stars"],
  },
  {
    slug: "p-value",
    term: "p-Value",
    category: "econlab",
    definition:
      "The p-value is the probability of observing a test statistic as extreme as the one computed, assuming the null hypothesis (coefficient = 0) is true. A p-value below 0.05 means there is less than a 5% chance the result is a statistical fluke — the standard threshold for 'statistical significance.' Lower p-values provide stronger evidence against the null hypothesis. A high p-value (>0.10) suggests the observed relationship could easily be noise.",
    related: ["t-statistic", "coefficient", "significance-stars", "standard-error"],
  },
  {
    slug: "significance-stars",
    term: "Significance Stars",
    category: "econlab",
    definition:
      "Significance stars are a visual shorthand for p-value thresholds: *** for p < 0.01 (highly significant), ** for p < 0.05 (significant), * for p < 0.10 (marginally significant). They appear alongside coefficients in regression tables. While convenient, they should not be used mechanically — a statistically significant coefficient with a tiny economic magnitude may be meaningless, while an insignificant coefficient with a large magnitude may reflect noisy data rather than no relationship.",
    related: ["p-value", "t-statistic", "coefficient"],
  },
  {
    slug: "r-squared-econ",
    term: "R² (R-Squared) — Econometric",
    category: "econlab",
    definition:
      "In regression, R² measures the proportion of variance in the dependent variable explained by the independent variable(s). An R² of 0.70 means 70% of the variation in Y is explained by the Xs. R² always increases when adding more variables (even irrelevant ones), which is why Adjusted R² — which penalises for the number of predictors — is often preferred for model comparison. Low R² is common in cross-country regressions where many unmeasured factors influence outcomes.",
    related: ["adjusted-r-squared", "aic", "bic", "pooled-ols"],
  },
  {
    slug: "adjusted-r-squared",
    term: "Adjusted R²",
    category: "econlab",
    definition:
      "Adjusted R² = 1 − [(1 − R²)(n − 1) / (n − k − 1)], where n is the number of observations and k is the number of independent variables. It penalises the addition of unhelpful variables — Adjusted R² can decrease when irrelevant variables are added, unlike regular R². It is a better measure for comparing models with different numbers of predictors.",
    related: ["r-squared-econ", "aic", "bic", "pooled-ols"],
  },
  {
    slug: "aic",
    term: "AIC (Akaike Information Criterion)",
    category: "econlab",
    definition:
      "AIC = 2k − 2·ln(L̂), where k is the number of parameters and L̂ is the maximised likelihood. It balances model fit against complexity — a lower AIC indicates a better model, all else equal. AIC is used for model selection: when choosing between several regression specifications, the one with the lowest AIC is preferred. BIC is similar but imposes a larger penalty for complexity.",
    related: ["bic", "adjusted-r-squared", "r-squared-econ", "pooled-ols"],
  },
  {
    slug: "bic",
    term: "BIC (Bayesian Information Criterion)",
    category: "econlab",
    definition:
      "BIC = k·ln(n) − 2·ln(L̂). Like AIC, it balances fit vs complexity, but BIC's penalty for additional parameters grows with the sample size (n), making it more conservative — BIC favours simpler models than AIC for large datasets. Lower BIC is better. Both AIC and BIC are reported in EconoSift's Econometric Lab regression output.",
    related: ["aic", "adjusted-r-squared", "r-squared-econ", "pooled-ols"],
  },
  {
    slug: "residuals",
    term: "Residuals",
    category: "econlab",
    definition:
      "Residuals are the differences between actual Y values and the model's predicted Y values: eᵢ = Yᵢ − Ŷᵢ. They represent what the model cannot explain. A good regression model has residuals that are randomly scattered around zero with no discernible pattern. Patterns in residuals — like a funnel shape or curvature — indicate model misspecification. EconoSift's Econometric Lab provides a residual scatter plot for visual diagnosis.",
    related: ["pooled-ols", "r-squared-econ", "ssr"],
  },
  {
    slug: "singular-matrix",
    term: "LinAlgError / Singular Matrix",
    category: "econlab",
    definition:
      "A singular matrix error occurs in regression when the independent variables are perfectly or near-perfectly collinear — meaning one X can be expressed as a linear combination of the others. This makes the design matrix non-invertible and the coefficients undefined. In practice, this happens when variables are redundant (e.g., including both 'Total Population' and 'Urban Population' when they are nearly proportional). EconoSift's Econometric Lab detects and flags near-singular design matrices.",
    related: ["pooled-ols", "multicollinearity", "coefficient"],
  },

  // ════════════════════════════════════════════════════════════════
  // 22. Atlas (Global Macro Map)
  // ════════════════════════════════════════════════════════════════
  {
    slug: "choropleth",
    term: "Choropleth Map",
    category: "atlas",
    definition:
      "A choropleth map is a thematic map where geographic regions (countries) are shaded or coloured in proportion to a statistical variable. Darker or more intense colours represent higher values. EconoSift's Atlas page uses a choropleth world map to display 6 macro indicators — GDP Growth, Inflation, Unemployment, Debt/GDP, Current Account, and GDP Per Capita — across ~200 countries, with colour coding from cool (low) to warm (high).",
    related: ["atlas-indicators", "regional-blocs", "year-slider", "kpi-strip"],
  },
  {
    slug: "atlas-indicators",
    term: "Atlas Indicators (6)",
    category: "atlas",
    definition:
      "EconoSift's Atlas page maps 6 key macroeconomic indicators using World Bank data: GDP Growth (annual %), Inflation (CPI, annual %), Unemployment (% of labour force), Debt/GDP (central government debt as % of GDP), Current Account (% of GDP), and GDP Per Capita (current US$). These six indicators provide a comprehensive cross-section of a country's economic health — growth, prices, labour, fiscal, external, and prosperity.",
    related: ["choropleth", "atlas", "world-bank"],
  },
  {
    slug: "regional-blocs",
    term: "Regional Blocs",
    category: "atlas",
    definition:
      "EconoSift's Atlas allows filtering by predefined regional groupings: G7 (the 7 largest advanced economies), G20 (major advanced and emerging economies), Eurozone (the 20 euro-using EU members), and Emerging Markets. Filtering to a bloc highlights just those countries on the map and recalculates the KPI strip and Top-10/Bottom-10 rankings accordingly.",
    related: ["atlas", "choropleth", "g7", "g20"],
  },
  {
    slug: "year-slider",
    term: "Year Slider (Atlas)",
    category: "atlas",
    definition:
      "The year slider on the Atlas page allows users to animate the choropleth map across time from 2000 to 2024. Dragging the slider changes the indicator values displayed for all countries, revealing trends — such as the global disinflation of the 2010s, the COVID growth shock of 2020, or the post-COVID inflation surge. It turns a static map into a dynamic data exploration tool.",
    related: ["choropleth", "atlas-indicators", "kpi-strip"],
  },
  {
    slug: "kpi-strip",
    term: "KPI Strip (Atlas)",
    category: "atlas",
    definition:
      "The KPI strip on the Atlas page displays summary statistics for the currently selected indicator and region: the global average, the median value, the highest country, the lowest country, and the count of countries with available data. It provides a quick numerical context alongside the visual map. The strip updates dynamically when changing indicators, years, or regional filters.",
    related: ["choropleth", "atlas-indicators", "top-10-bottom-10"],
  },
  {
    slug: "top-10-bottom-10",
    term: "Top-10 / Bottom-10 Rankings (Atlas)",
    category: "atlas",
    definition:
      "The Top-10 and Bottom-10 panels on the Atlas page list the highest-ranked and lowest-ranked countries for the selected indicator. For GDP Growth, the top 10 are the fastest-growing economies; for Unemployment, the bottom 10 are those with the lowest jobless rates. These rankings complement the map by putting specific country names and values to the colour gradient.",
    related: ["choropleth", "atlas-indicators", "kpi-strip"],
  },

  // ════════════════════════════════════════════════════════════════
  // 23. Economic Calendar
  // ════════════════════════════════════════════════════════════════
  {
    slug: "macro-event",
    term: "Macro Event (Economic Calendar)",
    category: "calendar",
    definition:
      "A macro event is a scheduled economic data release — such as CPI, NFP, GDP, FOMC decisions, ISM PMI, or retail sales — displayed on EconoSift's Calendar page. Each event is tagged by country, date, impact level (1–3 stars), and source (FRED or Finnhub). Macro events are the primary drivers of short-term market volatility, and traders monitor the calendar to anticipate and position for key releases.",
    related: ["impact-level", "fred-calendar", "finnhub-calendar", "earnings-event"],
  },
  {
    slug: "earnings-event",
    term: "Earnings Event",
    category: "calendar",
    definition:
      "An earnings event is a company's scheduled quarterly earnings report, displayed on the Calendar with the ticker, reporting time (BMO — before market open, or AMC — after market close), EPS estimate, and actual EPS (once reported). Earnings events are the most important recurring catalysts for individual stocks. EconoSift sources earnings dates from Finnhub and displays them alongside macro events on the unified Calendar page.",
    related: ["bmo-amc", "eps-estimate-actual", "surprise-pct", "macro-event"],
  },
  {
    slug: "dividend-event",
    term: "Dividend Event (Ex-Dividend Date)",
    category: "calendar",
    definition:
      "The ex-dividend date (ex-date) is the first day a stock trades without the right to receive its upcoming dividend. To receive the dividend, an investor must purchase the stock before the ex-date. On the ex-date, the stock price typically drops by approximately the dividend amount (all else equal). EconoSift's Calendar page lists upcoming ex-dividend dates sourced from Finnhub.",
    related: ["dividend-yield", "calendar", "earnings-event"],
  },
  {
    slug: "impact-level",
    term: "Impact Level (1–3 Stars)",
    category: "calendar",
    definition:
      "Each macro event on EconoSift's Calendar is assigned an impact rating of 1 to 3 stars, reflecting its typical market-moving significance. ⭐⭐⭐ events — NFP, FOMC decisions, CPI — consistently move markets. ⭐⭐ events — retail sales, industrial production, PPI — are significant but less consistently disruptive. ⭐ events — smaller country releases, secondary indicators — typically have limited market impact. The rating helps users prioritise which events to watch.",
    related: ["macro-event", "calendar", "fred-calendar"],
  },
  {
    slug: "bmo-amc",
    term: "BMO / AMC (Before Market Open / After Market Close)",
    category: "calendar",
    definition:
      "BMO and AMC indicate the timing of an earnings release. BMO (Before Market Open) — typically 7:00–9:30 AM ET — means the report is released before regular trading begins, giving the market the full trading day to digest the news. AMC (After Market Close) — typically 4:00–4:30 PM ET — means the report drops after the close, and the initial reaction occurs in after-hours trading. The timing affects volatility patterns around the event.",
    related: ["earnings-event", "calendar"],
  },
  {
    slug: "eps-estimate-actual",
    term: "EPS Estimate / Actual",
    category: "calendar",
    definition:
      "For each earnings event, the Calendar displays the consensus analyst EPS estimate (expected) and — once reported — the actual EPS. The difference drives the immediate stock price reaction. A large beat (actual significantly higher than estimate) typically results in a positive price move; a miss (actual below estimate) typically results in a sell-off. The surprise percentage quantifies the magnitude of the beat or miss.",
    related: ["earnings-event", "surprise-pct", "beat-miss-inline"],
  },
  {
    slug: "surprise-pct",
    term: "Surprise %",
    category: "calendar",
    definition:
      "Surprise % = (Actual EPS − Estimated EPS) / |Estimated EPS| × 100. A surprise of +10% means the company beat estimates by 10%. Consistently positive earnings surprises are a hallmark of high-quality companies with conservative guidance. Large negative surprises often trigger sharp sell-offs and analyst downgrades. EconoSift tracks earnings surprises on both the Calendar and Markets (Analyst) pages.",
    related: ["eps-estimate-actual", "beat-miss-inline", "earnings-event"],
  },
  {
    slug: "beat-miss-inline",
    term: "Beat / Miss / Inline",
    category: "calendar",
    definition:
      "These three terms describe an earnings result relative to consensus estimates. A 'beat' means the company exceeded EPS and/or revenue estimates. A 'miss' means it fell short. 'Inline' means results matched expectations. Beats tend to drive stocks higher, misses lower — but the reaction also depends on guidance, the magnitude of the surprise, and whether the beat/miss was already priced in ahead of the release.",
    related: ["surprise-pct", "eps-estimate-actual", "earnings-event"],
  },
  {
    slug: "fred-calendar",
    term: "FRED Calendar",
    category: "calendar",
    definition:
      "The FRED (Federal Reserve Economic Data) calendar provides release dates for US economic data published by the Federal Reserve, BLS, BEA, Census Bureau, and other US statistical agencies. EconoSift uses the FRED API to populate the Calendar with US macro event dates — including CPI, NFP, GDP, FOMC meetings, and more. A valid FRED_API_KEY is required for this feature.",
    related: ["macro-event", "calendar", "fred", "finnhub-calendar"],
  },

  // ════════════════════════════════════════════════════════════════
  // 24. Treemap Visualization
  // ════════════════════════════════════════════════════════════════
  {
    slug: "treemap",
    term: "Treemap (Squarified)",
    category: "treemap",
    definition:
      "A treemap is a data visualisation that displays hierarchical data as nested rectangles — each rectangle's area is proportional to a quantitative variable. EconoSift's Treemap page applies this to stock market indices: each box represents a stock, the box area is proportional to log(market cap), the colour represents return over the selected period (green for positive, red for negative), and boxes are grouped by GICS sector. The squarified algorithm produces rectangles as close to squares as possible, improving readability.",
    related: ["area-market-cap", "color-return", "sector-grouping"],
  },
  {
    slug: "area-market-cap",
    term: "Area = log(Market Cap)",
    category: "treemap",
    definition:
      "On EconoSift's Treemap, each stock's box area is determined by the logarithm of its market capitalisation, not its raw market cap. This log scaling prevents mega-cap stocks (Apple, $3T+) from completely dominating the map while still making larger companies visibly larger than smaller ones. Without log scaling, a handful of large companies would fill most of the treemap, making the rest invisible.",
    related: ["treemap", "color-return", "market-cap"],
  },
  {
    slug: "color-return",
    term: "Color = Return %",
    category: "treemap",
    definition:
      "Each treemap box is coloured by the stock's return over the selected time period (1D, 1W, 1M, 3M, YTD, 1Y). A green-to-red gradient maps positive returns to green (darker = stronger) and negative returns to red. This makes it instantly visible which sectors and stocks are driving performance — a field of green in Technology, red in Energy, communicates the day's narrative in a single glance.",
    related: ["treemap", "area-market-cap", "sector-grouping"],
  },
  {
    slug: "sector-grouping",
    term: "Sector Grouping (Treemap)",
    category: "treemap",
    definition:
      "The treemap groups stocks by GICS sector, with each sector in a clearly delineated region. This hierarchical organisation reveals sector-level patterns: are all tech stocks green, or is the sector's performance being carried by just one giant? The grouping can be toggled to industry-level drill-down for finer granularity. EconoSift supports S&P 500, Nasdaq 100, and Dow 30 treemap views.",
    related: ["treemap", "area-market-cap", "spdr-sector-etfs", "industry-drill-down"],
  },

  // ════════════════════════════════════════════════════════════════
  // 25. Risk Stress Testing & Monte Carlo
  // ════════════════════════════════════════════════════════════════
  {
    slug: "stress-scenario",
    term: "Stress Scenario (Historical)",
    category: "stress",
    definition:
      "A stress scenario replays a portfolio through an actual historical crisis to estimate potential losses. EconoSift offers four scenarios: the 2008 Financial Crisis (peak-to-trough ~2007–2009), the COVID Crash (Feb–Mar 2020), the 2022 Rate Hike cycle (Fed tightening), and the Dot-Com Bust (2000–2002). Each scenario applies the actual daily returns from that crisis period to the current portfolio weights, showing what the maximum drawdown and total loss would have been.",
    related: ["stress-testing", "monte-carlo-risk", "maximum-drawdown", "var"],
  },
  {
    slug: "2008-crisis",
    term: "2008 Financial Crisis",
    category: "stress",
    definition:
      "The 2008 Global Financial Crisis stress scenario replays the period from the pre-crisis peak (October 2007) to the trough (March 2009), during which the S&P 500 fell ~57%. It was characterised by systemic banking failures, a credit freeze, and forced deleveraging. The scenario tests how a portfolio would perform under extreme systemic risk when all risk assets fall together and correlations spike toward 1 — the most damaging environment for diversification-based strategies.",
    related: ["stress-scenario", "covid-crash", "2022-rate-hike", "dot-com-bust"],
  },
  {
    slug: "covid-crash",
    term: "COVID Crash (2020)",
    category: "stress",
    definition:
      "The COVID crash replays the February 19 – March 23, 2020 period when the S&P 500 fell ~34% in just 23 trading days — the fastest bear market in history. It was driven by an exogenous shock (pandemic lockdowns) rather than financial system instability. The crash was followed by an equally rapid recovery driven by unprecedented fiscal and monetary stimulus. This scenario tests resilience to sudden, sharp, liquidity-driven selloffs.",
    related: ["stress-scenario", "2008-crisis", "2022-rate-hike"],
  },
  {
    slug: "2022-rate-hike",
    term: "2022 Rate Hike Cycle",
    category: "stress",
    definition:
      "The 2022 rate hike stress scenario replays the Fed's most aggressive tightening cycle in 40 years — from January to October 2022, during which the S&P 500 fell ~25% and the NASDAQ ~33%. Unlike 2008 or 2020, this was a valuation-driven bear market: rising interest rates compressed P/E multiples, particularly for growth stocks. Bonds also fell (a rare simultaneous equity-bond decline), making it a particularly challenging environment for balanced portfolios.",
    related: ["stress-scenario", "2008-crisis", "covid-crash", "tightening"],
  },
  {
    slug: "dot-com-bust",
    term: "Dot-Com Bust (2000–2002)",
    category: "stress",
    definition:
      "The dot-com bust replays the March 2000 – October 2002 period when the S&P 500 fell ~49% and the NASDAQ ~78%. It was a grinding, multi-year bear market driven by the collapse of extreme technology valuations. Unlike the rapid V-shaped crashes of 2008 and 2020, the dot-com bust was a slow, relentless decline punctuated by false rallies. It tests resilience to a prolonged bear market where 'buy the dip' repeatedly fails.",
    related: ["stress-scenario", "2008-crisis", "covid-crash", "2022-rate-hike"],
  },
  {
    slug: "simulation-count",
    term: "Simulation Count (Monte Carlo)",
    category: "stress",
    definition:
      "The simulation count is the number of random paths generated in a Monte Carlo simulation. More simulations produce more stable and reliable estimates. EconoSift uses 10,000 simulations by default for portfolio Monte Carlo analysis, which is sufficient for most practical purposes. Higher counts (100K+) reduce sampling error but increase computation time. For options pricing, the count is adjusted via the 🔴 Run Analysis button.",
    related: ["monte-carlo-risk", "monte-carlo-portfolio", "horizon"],
  },
  {
    slug: "horizon",
    term: "Horizon (Days, Monte Carlo)",
    category: "stress",
    definition:
      "The horizon is the forward-looking time period — in trading days — over which Monte Carlo simulations project portfolio values. A 1-year (252-day) horizon with 10,000 simulations generates 10,000 possible 1-year portfolio outcomes. Shorter horizons produce narrower distributions; longer horizons produce wider, more uncertain distributions. The horizon is user-selectable on EconoSift's Risk page.",
    related: ["monte-carlo-risk", "monte-carlo-portfolio", "simulation-count"],
  },
  {
    slug: "worst-case",
    term: "Worst Case (Monte Carlo)",
    category: "stress",
    definition:
      "The worst-case outcome from a Monte Carlo simulation is the minimum portfolio value (or maximum loss) across all simulated paths. For example, if the worst case among 10,000 simulations is a −45% return, this represents the most extreme 0.01% tail outcome in the simulation. The worst case is sensitive to the number of simulations — more simulations reveal more extreme tails.",
    related: ["monte-carlo-risk", "monte-carlo-portfolio", "var", "cvar"],
  },
  {
    slug: "distribution-monte-carlo",
    term: "Monte Carlo Distribution",
    category: "stress",
    definition:
      "The Monte Carlo distribution is the histogram of all simulated portfolio outcomes — typically displayed as a bell-shaped (or skewed) curve. It provides a full picture of risk beyond single-point estimates like VaR. The shape reveals asymmetry (skew) and tail thickness (kurtosis). EconoSift plots the distribution on the Portfolio and Risk pages, allowing investors to visualise the range of possible outcomes rather than relying on a single expected value.",
    related: ["monte-carlo-risk", "monte-carlo-portfolio", "var", "realized-skewness"],
  },

  // ════════════════════════════════════════════════════════════════
  // 26. Misc / Infrastructure
  // ════════════════════════════════════════════════════════════════
  {
    slug: "ytd",
    term: "YTD (Year-to-Date)",
    category: "misc",
    definition:
      "Year-to-Date (YTD) refers to the period from January 1st of the current year to the present date. It is the most common period for measuring investment performance in a calendar year. YTD returns are reported by all funds, benchmarks, and indices. Note that YTD is not the same as '1-year return,' which uses a rolling 12-month window — YTD resets every January 1.",
    related: ["1d-1w-1m-periods", "annualised-return", "total-return"],
  },
  {
    slug: "1d-1w-1m-periods",
    term: "Return Periods (1D / 1W / 1M / 3M / 6M / 1Y / 2Y / 5Y)",
    category: "misc",
    definition:
      "Return periods define the lookback window for calculating performance. 1D = daily return, 1W = weekly (5 trading days), 1M = monthly (~21 days), 3M = quarterly, 6M = semi-annual, 1Y = annual (252 days), 2Y and 5Y for longer-term analysis. Each period reveals different aspects of performance — shorter periods capture momentum and news reactions; longer periods capture structural trends and compounding effects. EconoSift offers multiple period selectors across its pages.",
    related: ["ytd", "annualised-return", "rolling-metrics"],
  },
  {
    slug: "sparkline",
    term: "Sparkline",
    category: "misc",
    definition:
      "A sparkline is a small, word-sized inline chart — typically a simplified line chart without axes or labels — that shows the general shape of price movement over time. EconoSift uses sparklines in the Screener results tables and Watchlist to give an at-a-glance sense of recent price action without the visual weight of a full chart. They are data-rich but design-minimal, following Edward Tufte's 'data-ink ratio' philosophy.",
    related: ["normalised-price", "screener", "price-chart"],
  },
  {
    slug: "cached-data",
    term: "Cached Data",
    category: "misc",
    definition:
      "Cached data in EconoSift refers to responses stored in a two-tier system — memory (fast, ephemeral) and SQLite WAL-mode database (persistent, survives restarts) — with a 60-minute TTL. When a request is made, the cache is checked first; if valid cached data exists, it is returned instantly without making an external API call. If expired or absent, the data is fetched fresh and cached. This dramatically reduces external API calls and improves response times.",
    related: ["sqlite", "stale-cache", "hybrid-cache"],
  },
  {
    slug: "compute-tiers",
    term: "Compute Tiers (🟢 🟡 🔴)",
    category: "misc",
    definition:
      "EconoSift classifies computations into three tiers by cost: 🟢 Green (auto-compute on page load — e.g., price charts, basic ratios, KPIs); 🟡 Yellow (triggered by a 'Calculate' button — e.g., GARCH, cointegration, Black-Litterman); 🔴 Red (heavy computation triggered by 'Run Analysis' — e.g., Monte Carlo options pricing, full-universe momentum deciles). This tiered system ensures fast page loads while still providing access to compute-intensive analyses on demand.",
    related: ["garch", "cointegration", "monte-carlo-risk", "black-litterman"],
  },
  {
    slug: "stale-cache",
    term: "Stale Cache",
    category: "misc",
    definition:
      "A stale cache entry is cached data older than the TTL (60 minutes) but still present — it may be served immediately while a background refresh is triggered. If cache is older than 24 hours, it is considered severely stale and triggers a synchronous refresh. The staleness concept allows EconoSift to balance data freshness with responsiveness: slightly stale data served instantly is often better than waiting for a fresh fetch.",
    related: ["cached-data", "sqlite", "hybrid-cache"],
  },
  {
    slug: "sqlite",
    term: "SQLite (WAL Mode)",
    category: "misc",
    definition:
      "SQLite is the embedded database engine used by EconoSift for persistent caching, job scheduling metadata, and daily price/quote/macro storage. WAL (Write-Ahead Logging) mode enables concurrent reads while a write is in progress, dramatically improving performance for read-heavy workloads. SQLite was chosen because it is serverless, requires zero configuration, stores the entire database in a single file, and is more than capable of handling EconoSift's data volumes.",
    related: ["cached-data", "hybrid-cache", "stale-cache"],
  },
  {
    slug: "fred",
    term: "FRED (Federal Reserve Economic Data)",
    category: "misc",
    definition:
      "FRED is the Federal Reserve Bank of St. Louis's online database of over 800,000 economic time series — the primary source for US macroeconomic data at EconoSift. It provides CPI, GDP, NFP, industrial production, interest rates, yield curve data, and thousands more series via a free API (API key required). FRED data is considered authoritative and is updated in near real-time as government agencies release reports.",
    related: ["fred-calendar", "world-bank", "yfinance"],
  },
  {
    slug: "finnhub",
    term: "Finnhub",
    category: "misc",
    definition:
      "Finnhub is a third-party financial data API providing real-time stock quotes, company news, earnings calendars, economic events, insider transactions, SEC filings, and analyst estimates. EconoSift uses Finnhub to supplement yfinance and FRED data for calendar events, news feeds, and institutional ownership data. A free-tier API key supports limited requests; the EconoSift user's FINNHUB_API_KEY is configured in the environment.",
    related: ["fred", "yfinance", "finnhub-calendar", "calendar"],
  },
  {
    slug: "world-bank",
    term: "World Bank API",
    category: "misc",
    definition:
      "The World Bank API provides free access to global development indicators covering ~200 countries from 1960 to present — GDP, inflation, population, education, health, infrastructure, and hundreds more. It is the primary data source for EconoSift's Atlas page, Country Risk panel, and Econometric Lab. Data is accessed via pandas-datareader and does not require an API key. The World Bank's indicator coverage varies by country and year — gaps are common for smaller/less-developed nations.",
    related: ["fred", "atlas", "country-risk", "econ-lab"],
  },
  {
    slug: "yfinance",
    term: "yfinance",
    category: "misc",
    definition:
      "yfinance is the Python library that provides EconoSift with free access to Yahoo Finance data — historical prices, fundamentals, analyst estimates, options chains, and more. It works by querying Yahoo's publicly available API endpoints. While freely available, it is subject to rate limiting (EconoSift handles this with 401 retry logic and caching) and occasional schema changes. yfinance is reliable enough for a self-hosted analytics platform but should not be used for real-time trading.",
    related: ["fred", "finnhub", "cached-data", "pandas-datareader"],
  },
  {
    slug: "pandas-datareader",
    term: "pandas-datareader",
    category: "misc",
    definition:
      "pandas-datareader is a Python library that provides a unified interface for reading data from various internet sources — FRED, World Bank, OECD, and others — directly into pandas DataFrames. EconoSift uses it extensively in macro services to fetch FRED series and World Bank indicators. It abstracts away the differences between source APIs, providing a consistent .read() interface.",
    related: ["fred", "world-bank", "yfinance", "oecd"],
  },
  {
    slug: "oecd",
    term: "OECD Data",
    category: "misc",
    definition:
      "The OECD (Organisation for Economic Co-operation and Development) publishes economic data for its 38 member countries — GDP, inflation, employment, trade, and more. EconoSift uses OECD central bank policy rate series (via FRED's OECD-sourced data) for G10 carry calculations and CB policy tracking. OECD data is generally high quality with consistent methodology across countries, making it ideal for cross-country comparisons.",
    related: ["fred", "world-bank", "g10-currencies", "central-bank"],
  },
  {
    slug: "ken-french",
    term: "Ken French Data Library",
    category: "misc",
    definition:
      "The Ken French Data Library, maintained by Dartmouth professor Kenneth French, is the authoritative source for Fama-French factor returns — Mkt-RF, SMB, HML, RMW, CMA, and the risk-free rate — updated daily. The data is freely available as CSV files. EconoSift downloads these files to compute Fama-French 3-factor and 5-factor attribution for portfolios and individual stocks. The library also provides industry portfolio returns and momentum factor data.",
    related: ["fama-french", "smb", "hml", "rmw", "cma"],
  },
];

// ── Helper Functions ──

/** Returns all terms, optionally filtered by category. */
export function getAllTerms(category?: string): WikiTerm[] {
  if (category && category !== "all") {
    return TERMS.filter((t) => t.category === category);
  }
  return TERMS;
}

/** Case-insensitive search across term name, definition, and category label. */
export function searchTerms(query: string, category?: string): WikiTerm[] {
  const q = query.toLowerCase().trim();
  if (!q) return getAllTerms(category);

  const base = category && category !== "all"
    ? TERMS.filter((t) => t.category === category)
    : TERMS;

  return base.filter(
    (t) =>
      t.term.toLowerCase().includes(q) ||
      t.definition.toLowerCase().includes(q) ||
      (CATEGORIES.find((c) => c.key === t.category)?.label.toLowerCase() || "").includes(q),
  );
}

/** Returns all terms in a given category. */
export function getTermsByCategory(category: string): WikiTerm[] {
  return TERMS.filter((t) => t.category === category);
}

/** Returns a single term by its URL slug, or undefined. */
export function getTermBySlug(slug: string): WikiTerm | undefined {
  return TERMS.find((t) => t.slug === slug);
}

/** Returns all categories with their term counts. */
export function getCategoriesWithCounts(): (WikiCategory & { count: number })[] {
  return CATEGORIES.map((cat) => ({
    ...cat,
    count: TERMS.filter((t) => t.category === cat.key).length,
  }));
}
