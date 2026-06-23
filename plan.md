# ╔══════════════════════════════════════════════════════════════════════╗
# ║             AXIOM FINANCE — COMPLETE STRATEGIC MASTERPLAN            ║
# ║                           plan.md  v3.0                              ║
# ╠══════════════════════════════════════════════════════════════════════╣
# ║  Generated : 2026-06-23                                              ║
# ║  Executor  : Claude Code (autonomous, no manual coding)              ║
# ║  Stack     : Python FastAPI (backend) + Next.js (frontend)           ║
# ║  Data APIs : yfinance · FRED · Eurostat · World Bank · ECB ·         ║
# ║              OECD · IMF WEO · Finnhub (free tier) ·                  ║
# ║              FinanceDatabase (open source) · Alpha Vantage (free)    ║
# ║  Cost      : $0 — zero paid APIs required                            ║
# ╠══════════════════════════════════════════════════════════════════════╣
# ║  Research basis:                                                      ║
# ║    · Live internal evaluation of Axiom Finance (all tabs)            ║
# ║    · Live competitor recon: Koyfin · TradingView · Trading Economics ║
# ║      MacroMicro · Finviz · GuruFocus · SimplyWallSt · StockAnalysis  ║
# ╠══════════════════════════════════════════════════════════════════════╣
# ║  PHASE MAP                                                            ║
# ║   PHASE 0  — Critical Bug Fixes              (Do first)              ║
# ║   PHASE 1  — Valuation Engine Overhaul       (Full multi-model)      ║
# ║   PHASE 2  — Market Breadth & Global Indices (Dashboard)             ║
# ║   PHASE 3  — S&P 500 Treemap                 (Market visualisation)  ║
# ║   PHASE 4  — Economic Calendar               (Macro + Earnings)      ║
# ║   PHASE 5  — Screener Overhaul               (Signals + view tabs)   ║
# ║   PHASE 6  — Rolling Quantitative Metrics    (Risk tab enhancement)  ║
# ║   PHASE 7  — Options & Implied Volatility    (New tab)               ║
# ║   PHASE 8  — Macro Expansion                 (FX + Commodities)      ║
# ║   PHASE 9  — Snowflake Composite Score       (Multi-axis rating)     ║
# ║   PHASE 10 — Sector Performance Charts       (Groups view)           ║
# ╚══════════════════════════════════════════════════════════════════════╝


═══════════════════════════════════════════════════════════════════════
PHASE 0 — CRITICAL BUG FIXES
Must be done first — these are existing features that are broken or
empty and block user trust in the platform.
═══════════════════════════════════════════════════════════════════════

──────────────────────────────────────────────────────────────────────
0.1  FIX: Valuation Tab — DCF output panel is blank
──────────────────────────────────────────────────────────────────────
PROBLEM:
  The Valuation tab has four sliders (Risk-Free Rate, Market Premium,
  FCF Growth, Terminal Growth) but the output area is completely blank.
  The DCF calculation is either not implemented or not wired to the UI.

WHAT TO BUILD:
  The backend must perform a proper two-stage DCF calculation using the
  slider values as inputs. It must fetch TTM Free Cash Flow and shares
  outstanding from yfinance, compute a 10-year FCF projection, calculate
  a terminal value using the Gordon Growth perpetuity formula, discount
  everything back to present value, and divide by shares outstanding to
  produce an intrinsic value per share.

  Additionally produce:
  - A 3-column scenario table (Bear / Base / Bull) by varying FCF growth
    rate ±3 percentage points from the base case
  - A 7×7 sensitivity heatmap with FCF Growth on one axis (2% to 14%)
    and WACC on the other axis (5% to 12%), showing intrinsic value at
    each combination — colour-coded from deep red (overvalued) to deep
    green (undervalued) relative to current price

OUTPUT UI:
  - KPI row: Intrinsic Value | Current Price | Upside/Downside % | WACC
  - Scenario table: Bear / Base / Bull with IV and % vs current price
  - Sensitivity heatmap grid with the current base-case cell highlighted

DATA SOURCE:
  - yfinance: Ticker.cashflow ("Free Cash Flow" row, or fallback:
    Operating Cash Flow + Capital Expenditure), Ticker.info for
    sharesOutstanding, currentPrice, and beta


──────────────────────────────────────────────────────────────────────
0.2  FIX: Macro Tab — FX Rates panel shows no data
──────────────────────────────────────────────────────────────────────
PROBLEM:
  The Macro page has an "FX Rates" panel with a header but the chart
  area is empty — no rates, no sparklines, nothing renders.

WHAT TO BUILD:
  Fetch daily OHLCV for at least 15 major currency pairs via yfinance.
  Pairs to include:
    EURUSD, GBPUSD, USDJPY, USDCNY, AUDUSD, USDCHF, USDCAD, USDBRL,
    USDMXN, USDKRW, USDINR, USDSGD, USDNOK, USDSEK, USDPLN

  For each pair compute: current rate, 1D change %, 1W change %,
  1M change %, 1Y change %, and a 30-day sparkline array.

  Add a base currency switcher (USD / EUR / GBP) that recomputes all
  rates as crosses (e.g. switching to EUR base shows EURGBP, EURJPY etc.)

OUTPUT UI:
  - Responsive grid of currency cards (flag + pair name + rate + 1D%
    badge coloured green/red + mini sparkline)
  - Pill switcher: [USD] [EUR] [GBP] to change the base currency

DATA SOURCE:
  - yfinance: yf.download() with Yahoo Finance FX tickers
    (format: "EURUSD=X", "USDJPY=X" etc.)


──────────────────────────────────────────────────────────────────────
0.3  FIX: Macro Tab — Regime Classifier shows "Detecting..."
──────────────────────────────────────────────────────────────────────
PROBLEM:
  The Macro Regime detector spinner runs indefinitely. The backend
  classification logic is either not implemented or not returning data.

WHAT TO BUILD:
  Implement the classic 2×2 Goldilocks matrix using real macro data:

  - Fetch US Real GDP (FRED series GDPC1) and compute YoY growth
  - Fetch US CPI (FRED series CPIAUCSL) and compute YoY inflation
  - Compute the 3-month rolling direction (trend) of each
  - Map to regime:
      GDP rising  + Inflation falling → "Goldilocks"  (green)
      GDP rising  + Inflation rising  → "Reflation"   (yellow)
      GDP falling + Inflation rising  → "Stagflation" (orange)
      GDP falling + Inflation falling → "Recession"   (dark red)

  Also compute for:
  - Eurozone: GDP from Eurostat series "namq_10_gdp" (geo=EA, item=B1GQ),
    inflation from Eurostat series "prc_hicp_manr" (geo=EA, coicop=CP00)
  - Japan: GDP and CPI from OECD MEI dataset via OECD.Stat API

  Return a full historical time series of (gdp_delta, cpi_delta, regime)
  going back to the year 2000 so the frontend can animate a scrubber.

OUTPUT UI:
  - 4-quadrant scatter plot: x-axis = inflation momentum,
    y-axis = growth momentum; coloured quadrant backgrounds
  - Animated pulsing dot showing current position
  - Region tabs: [US] [Eurozone] [Japan]
  - Time scrubber to replay history from 2000 to present
  - Large regime label badge with colour below the chart
  - KPI cards: current GDP YoY%, current CPI YoY%, regime name

DATA SOURCES:
  - FRED API (free, requires free API key): series GDPC1, CPIAUCSL
  - Eurostat Python package (pip install eurostat): series namq_10_gdp,
    prc_hicp_manr
  - OECD.Stat API (free, no key): MEI dataset for Japan


═══════════════════════════════════════════════════════════════════════
PHASE 1 — VALUATION ENGINE: FULL MULTI-MODEL OVERHAUL
Completely redesign the Valuation tab from a single DCF panel into a
professional multi-model dashboard that shows 8 valuation methods,
aggregates them into a single Axiom Fair Value, and delivers a
GuruFocus-style verdict label.
═══════════════════════════════════════════════════════════════════════

──────────────────────────────────────────────────────────────────────
1.0  Country-Aware Discount Rate Selector
──────────────────────────────────────────────────────────────────────
WHAT TO BUILD:
  A selector at the very top of the Valuation tab that auto-detects the
  stock's listing country from its Yahoo Finance exchange code, then
  pre-populates:
  - Risk-Free Rate (live 10Y government bond yield from FRED)
  - Equity Risk Premium (from Damodaran's Jan 2026 country ERP table)
  - Beta (from yfinance, 3-year, clamped between 0.5 and 3.0)
  - Cost of Equity (= RFR + Beta × ERP, computed automatically)

  The user can override any value manually. A "Reset to preset" button
  restores the auto-detected values. These shared rates feed ALL 8
  valuation models below.

COUNTRY PRESETS TO INCLUDE (with live RFR source):
  🇺🇸 United States   — FRED series: DGS10            (daily)
  🇩🇪 Germany         — FRED series: IRLTLT01DEM156N  (monthly)
  🇬🇧 United Kingdom  — FRED series: IRLTLT01GBM156N  (monthly)
  🇯🇵 Japan           — FRED series: IRLTLT01JPM156N  (monthly)
  🇫🇷 France          — FRED series: IRLTLT01FRM156N  (monthly)
  🇨🇦 Canada          — FRED series: IRLTLT01CAM156N  (monthly)
  🇦🇺 Australia       — FRED series: IRLTLT01AUM156N  (monthly)
  🇳🇱 Netherlands     — FRED series: IRLTLT01NLM156N  (monthly)
  🇨🇭 Switzerland     — FRED series: IRLTLT01CHM156N  (monthly)
  🇸🇪 Sweden          — FRED series: IRLTLT01SEM156N  (monthly)
  🇪🇸 Spain           — FRED series: IRLTLT01ESM156N  (monthly)
  🇮🇹 Italy           — FRED series: IRLTLT01ITM156N  (monthly)
  🇰🇷 South Korea     — FRED series: IRLTLT01KRM156N  (monthly)
  🇮🇳 India           — yfinance ticker: IN10YT=RR
  🇧🇷 Brazil          — yfinance ticker: BR10YT=RR
  🇨🇳 China           — yfinance ticker: CN10YT=RR
  🇲🇽 Mexico          — yfinance ticker: MX10YT=RR
  🇸🇬 Singapore       — yfinance ticker: SG10YT=RR
  🇳🇿 New Zealand     — yfinance ticker: NZ10YT=RR
  🇿🇦 South Africa    — yfinance ticker: ZA10YT=RR
  🇵🇱 Poland          — yfinance ticker: PL10YT=RR

DAMODARAN ERP VALUES (from pages.stern.nyu.edu/~adamodar, Jan 2026):
  Store these in a static JSON file: backend/data/damodaran_erp_2026.json
  Update this file each January when Damodaran publishes new figures.
  Key values (Total ERP = Base ERP 4.23% + Country Risk Premium):
    US:  4.23% (CRP: 0.00%, rating: Aaa)
    DE:  4.87% (CRP: 0.64%, rating: Aaa)
    GB:  4.87% (CRP: 0.64%, rating: Aa3)
    JP:  5.53% (CRP: 1.30%, rating: A1)
    FR:  4.87% (CRP: 0.64%, rating: Aa2)
    CA:  4.23% (CRP: 0.00%, rating: Aaa)
    AU:  4.87% (CRP: 0.64%, rating: Aaa)
    NL:  4.87% (CRP: 0.64%, rating: Aaa)
    CH:  4.23% (CRP: 0.00%, rating: Aaa)
    SE:  4.87% (CRP: 0.64%, rating: Aaa)
    ES:  5.53% (CRP: 1.30%, rating: Baa1)
    IT:  6.30% (CRP: 2.07%, rating: Baa3)
    KR:  5.53% (CRP: 1.30%, rating: Aa2)
    IN:  7.76% (CRP: 3.53%, rating: Baa3)
    CN:  6.30% (CRP: 2.07%, rating: A1)
    BR: 10.06% (CRP: 5.83%, rating: Ba1)
    MX:  8.89% (CRP: 4.66%, rating: Baa2)
    SG:  4.23% (CRP: 0.00%, rating: Aaa)
    NZ:  4.87% (CRP: 0.64%, rating: Aaa)
    ZA: 11.35% (CRP: 7.12%, rating: Ba2)
    PL:  6.30% (CRP: 2.07%, rating: A2)

AUTO-DETECTION:
  Map Yahoo Finance exchange codes to country codes. Key mappings:
    NYQ/NMS/NGM/PCX → US  |  LSE/IOB → GB  |  XETR/FRA → DE
    TYO/OSA → JP  |  ENX/PAR → FR  |  TSX/CVE → CA  |  ASX → AU
    AMS → NL  |  SWX/VTX → CH
──────────────────────────────────────────────────────────────────────
1.1  VALUATION MODEL 1 — Discounted Cash Flow (Two-Stage DCF)
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  The industry-standard intrinsic value method. Projects a company's
  free cash flows over a 10-year high-growth period, then appends a
  terminal value assuming perpetual stable growth, and discounts
  everything back to present value at WACC.

INPUTS (all user-adjustable via sliders, seeded from Country Selector):
  - TTM Free Cash Flow          (auto-fetched from yfinance)
  - FCF Growth Rate             (slider, default: 5-year avg revenue growth)
  - Terminal Growth Rate        (slider, default: 2.5%)
  - WACC                        (auto-computed from RFR + Beta × ERP)

DATA NEEDED FROM YFINANCE:
  - Ticker.cashflow: "Free Cash Flow" row (fallback: Operating Cash Flow
    minus abs(Capital Expenditure) if FCF row is absent)
  - Ticker.info: sharesOutstanding, currentPrice, beta
  - Ticker.financials: revenue for past 5 years to compute default
    FCF growth rate

FORMULA LOGIC:
  - Year 1–10 FCF projected at high-growth rate
  - Terminal Value = FCF_year10 × (1 + terminal_growth) ÷
                     (WACC − terminal_growth)
  - Intrinsic Value = (PV of all 10 FCFs + PV of Terminal Value)
                       ÷ shares outstanding

OUTPUT DISPLAYED:
  - Intrinsic value per share
  - Upside/downside % vs current price
  - 3-scenario table: Bear (FCF growth −3pp), Base, Bull (FCF growth +3pp)
  - 7×7 sensitivity heatmap: FCF Growth (2%–14%) vs WACC (5%–12%)
    — each cell colour-coded by upside/downside relative to current price
  - Current base-case cell highlighted with a distinct border

APPLICABILITY NOTE (display to user):
  Best for: mature, cash-generative companies (e.g. Apple, LVMH, Shell)
  Not suitable for: pre-revenue companies, banks, insurance firms


──────────────────────────────────────────────────────────────────────
1.2  VALUATION MODEL 2 — Dividend Discount Model (DDM / Gordon Growth)
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  Values a stock as the present value of all future dividend payments.
  Uses the Gordon Growth Model (single-stage) as the primary output,
  with a two-stage DDM as an optional extension for companies in a
  high-growth dividend phase transitioning to stability.

INPUTS:
  - Most recent annual dividend per share    (auto-fetched from yfinance)
  - Dividend growth rate                     (slider, default: 5-year
                                              historical CAGR of dividends)
  - Cost of equity (r)                       (from Country Selector)

DATA NEEDED FROM YFINANCE:
  - Ticker.dividends: historical quarterly/annual dividends to compute
    the 5-year dividend CAGR
  - Ticker.info: dividendRate (current annualised dividend),
    payoutRatio, trailingEps

FORMULA:
  Gordon Growth Model:  P₀ = D₁ ÷ (r − g)
  where D₁ = D₀ × (1 + g)

APPLICABILITY GUARD:
  - Only render this model if the stock has paid dividends in the last
    12 months (dividendRate > 0 in Ticker.info)
  - If the company pays no dividend, show a grey locked card with the
    message: "DDM not applicable — this company pays no dividend.
    Consider the DCF or Residual Income model instead."
  - If cost of equity (r) ≤ dividend growth (g), flag a warning:
    "Growth rate exceeds discount rate — model produces undefined output.
    Reduce the growth assumption."

OUTPUT DISPLAYED:
  - Intrinsic value per share (Gordon Growth)
  - Upside/downside % vs current price
  - Current dividend yield, payout ratio, 5-year dividend CAGR
  - Sensitivity table: rows = dividend growth 1%–6%, cols = cost of
    equity 6%–12%


──────────────────────────────────────────────────────────────────────
1.3  VALUATION MODEL 3 — Benjamin Graham Formula (Growth Stock Value)
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  Graham's original formula for estimating the fair value of a growth
  stock based on earnings and expected growth, adjusted for the current
  interest rate environment. Simple, transparent, widely recognised.

FORMULA (Graham 1962/1973 updated version):
  V* = EPS × (8.5 + 2g) × 4.4 ÷ Y
  where:
    EPS = trailing twelve-month earnings per share
    g   = expected annual EPS growth rate for next 7–10 years (as whole
          number, e.g. 8 for 8%)
    Y   = current yield on AAA corporate bonds (used as the interest
          rate benchmark)
    8.5 = assumed P/E for a zero-growth company (Graham's constant)
    4.4 = AAA bond yield when Graham published (used as base rate)

DATA NEEDED:
  - yfinance Ticker.info: trailingEps, earningsGrowth (or
    earningsQuarterlyGrowth as fallback)
  - FRED series AAA (Moody's Seasoned Aaa Corporate Bond Yield, daily)
    for the Y value — this makes the formula live and rate-responsive

INPUTS (all user-adjustable):
  - EPS (auto-filled from yfinance, editable)
  - Expected growth rate g (slider, default: analyst 5-year EPS CAGR
    from yfinance Ticker.info["earningsGrowth"] × 100)
  - AAA yield Y (auto-filled from FRED series AAA, editable)

OUTPUT DISPLAYED:
  - Graham Number intrinsic value
  - Upside/downside % vs current price
  - Current EPS, current AAA yield, implied fair P/E at that growth rate
  - Sensitivity: rows = EPS growth 3%–20%, cols = AAA yield 3%–7%

APPLICABILITY NOTE:
  Best for: profitable, established companies with positive EPS
  Not suitable for: loss-making companies, banks, REITs


──────────────────────────────────────────────────────────────────────
1.4  VALUATION MODEL 4 — Graham Number (Asset-Based Floor)
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  A simpler Graham formula that produces the maximum price a
  conservative value investor should pay, based purely on earnings and
  book value. Frequently used as a "floor" valuation or safety-of-
  principal check, not a growth valuation.

FORMULA:
  Graham Number = √(22.5 × EPS × BVPS)
  where:
    EPS  = trailing twelve-month earnings per share
    BVPS = book value per share
    22.5 = product of Graham's maximum acceptable P/E (15) ×
           maximum acceptable P/B (1.5)

DATA NEEDED FROM YFINANCE:
  - Ticker.info: trailingEps, bookValue (= BVPS)
  - Ticker.info: currentPrice for comparison

APPLICABILITY GUARD:
  - Requires both EPS > 0 and BVPS > 0 to produce a valid result
  - If either is negative, show grey card: "Graham Number not applicable
    — requires positive earnings and positive book value."

OUTPUT DISPLAYED:
  - Graham Number value
  - Premium/discount vs current price as a %
  - Current P/E and P/B ratios vs Graham's thresholds (15× and 1.5×)
  - Small explainer: what the number represents and its limitations


──────────────────────────────────────────────────────────────────────
1.5  VALUATION MODEL 5 — Peter Lynch Fair Value (PEG-based)
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  Lynch's rule-of-thumb: a fairly valued growth stock should trade at a
  P/E equal to its earnings growth rate (PEG ratio = 1.0). This gives an
  intuitive fair value price tied entirely to growth expectations.

FORMULA:
  Lynch Fair Value = EPS × (EPS Growth Rate × 100)
  Alternatively expressed as: Fair P/E = EPS Growth Rate (%)
  PEG Ratio = (P/E) ÷ (EPS Growth Rate %)
    PEG < 1.0 → potentially undervalued
    PEG = 1.0 → fairly valued
    PEG > 1.0 → potentially overvalued

DATA NEEDED FROM YFINANCE:
  - Ticker.info: trailingEps, earningsGrowth (5-year expected),
    trailingPE, currentPrice
  - Use earningsGrowth as the g input; allow user to override

INPUTS (user-adjustable):
  - EPS (auto-filled)
  - Expected EPS growth rate (slider, default from yfinance)

OUTPUT DISPLAYED:
  - Lynch Fair Value per share
  - Current PEG ratio
  - PEG verdict: Undervalued / Fairly Valued / Overvalued badge
  - Comparison: current P/E vs implied fair P/E at that growth rate
  - Sensitivity: fair value at growth rates from 5% to 30%

APPLICABILITY NOTE:
  Best for: mid-cap growth companies with consistent earnings growth
  Not suitable for: value stocks, loss-making companies, cyclicals,
  companies with very high (>25%) or very low (<5%) growth rates


──────────────────────────────────────────────────────────────────────
1.6  VALUATION MODEL 6 — EV/EBITDA Comparable Company Analysis
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  A relative valuation method (market comps). Values the stock by
  applying the median EV/EBITDA multiple of its sector peers to the
  company's own EBITDA. Unlike intrinsic models, this anchors value to
  what the market currently pays for similar businesses.

WHAT TO BUILD:
  1. Identify the stock's sector using yfinance Ticker.info["sector"]
  2. Fetch the top companies in that sector using yfinance's
     Sector/Industry API (yf.Sector(key).top_companies) or the open-
     source FinanceDatabase library (pip install financedatabase), which
     provides 80,000+ tickers categorised by sector and industry
  3. For each peer, compute EV/EBITDA:
       Enterprise Value = Market Cap + Total Debt − Cash
       EBITDA = Operating Income + D&A
  4. Take the sector median EV/EBITDA multiple (exclude outliers
     beyond 2 standard deviations)
  5. Apply that median to the target company's EBITDA:
       Implied EV = EBITDA × Sector Median EV/EBITDA
       Implied Equity Value = Implied EV − Net Debt
       Implied Price = Implied Equity Value ÷ Shares Outstanding

DATA NEEDED FROM YFINANCE:
  - Ticker.info: marketCap, totalDebt, totalCash, ebitda,
    operatingCashflow, sector
  - For peers: same fields fetched in batch for 20–30 sector peers

SECTOR MEDIAN FALLBACK:
  If live peer calculation fails or returns insufficient peers (<5),
  fall back to a static sector median EV/EBITDA table (store in
  backend/data/sector_multiples.json), updated quarterly:
    Technology:         ~22×
    Healthcare:         ~16×
    Consumer Cyclical:  ~12×
    Financials:         N/A (use P/B instead — see note below)
    Energy:             ~8×
    Industrials:        ~13×
    Consumer Defensive: ~15×
    Communication Svcs: ~10×
    Basic Materials:    ~8×
    Real Estate:        ~20× (EV/EBITDA or use P/FFO)
    Utilities:          ~11×

  Note: For Financials and Insurance, EV/EBITDA is not meaningful.
  Show grey card: "EV/EBITDA not applicable for financial sector stocks.
  Use the P/B or DDM model instead."

OUTPUT DISPLAYED:
  - Implied price per share from comp analysis
  - Upside/downside % vs current price
  - Company's current EV/EBITDA vs sector median (bar comparison)
  - List of top 5–10 peers used with their individual EV/EBITDA ratios
  - Toggle: show sector median or industry median


──────────────────────────────────────────────────────────────────────
1.7  VALUATION MODEL 7 — Residual Income Model (RIM / Edwards-Bell-
     Ohlson Model)
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  Values a stock by starting from current book value (the accounting
  floor) and adding the present value of all future "excess" returns
  above the cost of equity. It is academically rigorous (widely used in
  CFA curriculum) and is particularly powerful for financial companies,
  banks, and asset-heavy firms where DCF is unreliable.

FORMULA:
  Intrinsic Value = Book Value Per Share
                    + PV of Residual Income over forecast horizon
                    + PV of Terminal Residual Income

  Residual Income (year t) = Net Income − (Equity Book Value × Ke)
                           = EPS − (BVPS × Cost of Equity)

  This is equivalent to: ROE excess = (ROE − Ke) × BVPS

IMPLEMENTATION APPROACH:
  Use a simplified 5-year explicit forecast + terminal value:
  1. Start with current BVPS from yfinance Ticker.info["bookValue"]
  2. Project ROE for 5 years (default: current trailing ROE, mean-
     reverting toward sector average by year 5)
  3. Project BVPS each year: BVPS_t = BVPS_(t-1) × (1 + g_book)
     where g_book ≈ ROE × retention ratio (1 − payout ratio)
  4. Compute residual income each year: RI_t = (ROE_t − Ke) × BVPS_(t-1)
  5. Terminal value of RI beyond year 5: RI_5 ÷ (Ke − g_stable)
     if ROE converges to Ke, terminal RI = 0 (clean surplus)
  6. Sum all discounted RI + current BVPS = intrinsic value per share

DATA NEEDED FROM YFINANCE:
  - Ticker.info: bookValue (BVPS), returnOnEquity (trailing ROE),
    payoutRatio, trailingEps
  - Ticker.financials: net income history for ROE trend
  - Cost of equity from Country Selector

APPLICABILITY:
  Works best for: banks, insurance companies, asset managers, REITs,
  capital-intensive industrials, any firm where book value is meaningful
  Not ideal for: asset-light tech companies with intangible-heavy balance
  sheets (often shows very low B
──────────────────────────────────────────────────────────────────────
  (continuing Model 1.7 — Residual Income Model)
──────────────────────────────────────────────────────────────────────

OUTPUT DISPLAYED:
  - Intrinsic value per share (sum of book value + discounted RI stream)
  - Breakdown bar showing how much of intrinsic value comes from current
    book value vs projected excess returns (two stacked segments)
  - Trailing ROE vs Cost of Equity comparison card (positive spread =
    value-creating company, negative = value-destroying)
  - 5-year RI projection table: year | BVPS | ROE | RI | Discounted RI
  - Sensitivity: rows = ROE 5%–25%, cols = Cost of Equity 6%–12%

APPLICABILITY NOTE (display to user):
  Best for: banks, insurers, REITs, capital-intensive industrials, any
  firm where book value is a meaningful anchor
  Limitations: asset-light tech and software companies often have very
  low book values due to intangible assets not recognised on balance
  sheet, causing this model to dramatically understate fair value


──────────────────────────────────────────────────────────────────────
1.8  VALUATION MODEL 8 — Earnings Power Value (EPV)
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  Developed by Professor Bruce Greenwald at Columbia Business School.
  EPV is a conservative, no-growth intrinsic value estimate — it asks:
  "What is this business worth if it never grows again?" It is
  deliberately pessimistic and useful as a downside floor. If the market
  price is below EPV, the stock is cheap even with zero growth priced in.
  If market price > EPV, the market is pricing in growth expectations
  that need to be justified.

FORMULA:
  1. Calculate average EBIT margin over the past 3–5 years
     (smooths out cyclical distortions)
  2. Apply that average margin to the current year's revenue to get
     "normalised EBIT"
  3. Apply the effective tax rate to get NOPAT
     (Net Operating Profit After Tax)
  4. Add back excess D&A (D&A minus maintenance capex) to get
     adjusted earnings — maintenance capex is typically estimated as
     D&A × 0.75 for most sectors as a conservative rule of thumb
  5. EPV = Adjusted Earnings ÷ WACC

  Growth Premium (informational, not used in EPV itself):
    Growth Premium = Current Market Price − EPV
    If Growth Premium > 0: market is pricing in growth
    If Growth Premium < 0: stock is cheap even without growth

DATA NEEDED FROM YFINANCE:
  - Ticker.financials: EBIT, Revenue, Tax Provision, Net Income
    (need 3–5 years of history for margin averaging)
  - Ticker.cashflow: Depreciation & Amortisation, Capital Expenditure
  - Ticker.info: currentPrice, sharesOutstanding
  - WACC from Country Selector (same as DCF model)

OUTPUT DISPLAYED:
  - EPV per share
  - Current market price vs EPV: premium or discount %
  - Growth premium in dollar terms and as a % of market price
  - Breakdown: Normalised Revenue → EBIT Margin → NOPAT → EPV
  - 5-year EBIT margin trend chart to show the normalisation basis
  - Sensitivity: rows = average EBIT margin 5%–25%, cols = WACC 6%–12%

APPLICABILITY NOTE:
  Best for: mature companies in stable industries where current earnings
  power is representative of future earnings power
  Less useful for: high-growth companies (deliberately ignores growth),
  turnaround situations, cyclicals at the bottom of a cycle


──────────────────────────────────────────────────────────────────────
1.9  AXIOM FAIR VALUE — Composite Aggregation & Verdict
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  Aggregates all applicable model outputs into a single "Axiom Fair
  Value" estimate using a confidence-weighted average. Applicable
  models are those that returned a valid, non-error result for the
  given stock. Each model is assigned a base weight that can be
  adjusted based on the company's characteristics.

DEFAULT MODEL WEIGHTS (sum to 1.0 across applicable models):
  DCF (Two-Stage):           30%  — primary intrinsic value anchor
  EV/EBITDA Comps:           20%  — market-grounded relative check
  Residual Income:           15%  — balance sheet anchor
  EPV:                       15%  — downside/no-growth floor
  Graham Formula:            10%  — conservative growth check
  Peter Lynch / PEG:          5%  — growth momentum check
  DDM (Gordon Growth):        5%  — income investor perspective
  Graham Number:              0%  — informational floor only, not in avg

  When a model is inapplicable (e.g. DDM when no dividend, Graham
  Number when EPS < 0), redistribute its weight proportionally across
  remaining applicable models.

COMPOSITE VALUE CALCULATION:
  Axiom Fair Value = Σ (model_intrinsic_value_i × weight_i)
                      across all applicable models

VERDICT CLASSIFICATION (inspired by GuruFocus 6-tier system):
  Price vs Axiom Fair Value:
    Price < Fair Value × 0.70  → "Significantly Undervalued"  (dark green)
    Price < Fair Value × 0.90  → "Modestly Undervalued"       (green)
    Price within ±10% of FV    → "Fairly Valued"               (neutral)
    Price > Fair Value × 1.10  → "Modestly Overvalued"         (orange)
    Price > Fair Value × 1.30  → "Significantly Overvalued"    (red)

OUTPUT UI — top of Valuation tab, above all model cards:
  - Large "Axiom Fair Value: $XXX.XX" display
  - Current price shown alongside
  - Horizontal gauge bar from "Sig. Undervalued" to "Sig. Overvalued"
    with a needle pointing to the current verdict zone
  - Verdict badge (colour-coded label with icon)
  - Upside/downside % to fair value
  - Model weight breakdown shown as a small horizontal stacked bar
    (shows which models contributed and at what weight)
  - "Models used: 6/8" indicator with tooltip listing which were
    excluded and why

BELOW THE COMPOSITE — Model Card Grid (2×4 layout):
  Each of the 8 models rendered as a card showing:
  - Model name and a one-line description
  - Intrinsic value estimate (large, bold)
  - Upside/downside % vs current price (green/red)
  - Applicable/Not Applicable badge
  - "Expand" toggle to reveal the full model detail, inputs, and
    sensitivity analysis for that specific model


──────────────────────────────────────────────────────────────────────
1.10  VALUATION TAB — Full Layout & UX Specification
──────────────────────────────────────────────────────────────────────
TAB STRUCTURE (top to bottom):

  [1] Country Selector Bar
      Full-width bar containing: country flag dropdown, live RFR,
      ERP source label, beta, computed cost of equity, Manual Override
      toggle. Sticky to the top of the tab on scroll.

  [2] Axiom Fair Value Composite Panel
      Large composite value + gauge + verdict badge + model coverage
      indicator. This is the first thing the user sees.

  [3] Model Card Grid (2 columns × 4 rows = 8 cards)
      Each card is compact by default, expandable inline.
      Cards for inapplicable models are rendered greyed-out with an
      explanation — never hidden, always visible.

  [4] Sensitivity & Scenarios (within each expanded model card)
      Heatmaps and scenario tables render inline inside the expanded
      card, not in a separate modal.

  [5] Warning Flags Panel (bottom of tab)
      Automatically generated flags such as:
      - "Negative FCF in most recent year — DCF inputs may be unreliable"
      - "Payout ratio > 100% — dividend may not be sustainable for DDM"
      - "Beta not available — using market beta of 1.0 as fallback"
      - "Book value per share is negative — Graham Number and RIM excluded"
      Shown only when relevant, collapsed by default, expandable.

FILES TO CREATE / MODIFY:
  Backend:
    backend/routes/valuation.py          (main routing for all 8 models)
    backend/services/valuation_engine.py (all model calculation logic)
    backend/services/discount_rates.py   (country selector, live RFR)
    backend/services/peer_fetcher.py     (EV/EBITDA comparable lookup)
    backend/data/damodaran_erp_2026.json (static ERP table)
    backend/data/sector_multiples.json   (static sector median fallback)

  Frontend:
    frontend/app/markets/tabs/Valuation.tsx        (main tab layout)
    frontend/components/valuation/CountrySelector.tsx
    frontend/components/valuation/CompositePanel.tsx
    frontend/components/valuation/ValuationGauge.tsx
    frontend/components/valuation/ModelCard.tsx    (shared card template)
    frontend/components/valuation/SensitivityHeatmap.tsx
    frontend/components/valuation/ScenarioTable.tsx
    frontend/components/valuation/WarningFlags.tsx


═══════════════════════════════════════════════════════════════════════
PHASE 2 — MARKET BREADTH & GLOBAL DASHBOARD
Add a new "Dashboard" landing page (or enhance the Markets homepage)
that gives an at-a-glance picture of global market health — inspired
by Finviz's homepage breadth bars and Trading Economics' live index
tables. This is the first thing a professional sees when opening a
financial terminal.
═══════════════════════════════════════════════════════════════════════

──────────────────────────────────────────────────────────────────────
2.1  Market Breadth Bar — S&P 500 Internal Health Indicators
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  A horizontal bar strip shown at the very top of the Markets page,
  above all tabs. Displays five live breadth indicators that describe
  the internal health of the S&P 500 — i.e. whether the move is broad-
  based or driven by a handful of large caps. Inspired directly by the
  Finviz homepage breadth bars.

INDICATORS TO DISPLAY (all five as segmented progress bars):
  1. Advancing / Declining stocks
     How many of the ~500 S&P 500 constituents gained vs fell today
  2. New 52-Week Highs / New 52-Week Lows
     Stocks within 1% of their 52-week high vs within 1% of their low
  3. Above SMA 50 / Below SMA 50
     Percentage of S&P 500 stocks trading above their 50-day moving avg
  4. Above SMA 200 / Below SMA 200
     Percentage of S&P 500 stocks trading above their 200-day moving avg
  5. McClellan Oscillator (displayed as a single signed number + colour)
     = 19-day EMA of (advances − declines) minus 39-day EMA of same
     Positive = bullish momentum, Negative = bearish momentum

HOW TO GET THE S&P 500 CONSTITUENT LIST (free, no API needed):
  Scrape the Wikipedia page for S&P 500 constituents:
  URL: https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
  Parse the first HTML table to extract all ticker symbols.
  Cache this list and refresh weekly (constituents change infrequently).
  This is a standard, well-documented approach used widely in open-
  source finance projects.

DATA PIPELINE:
  Once the ~500 tickers are known, batch-download the last 252 trading
  days (1 year) of daily closing prices for all of them via yfinance
  using yf.download() in chunks of 100 tickers at a time.
  Cache results in the backend with a daily refresh at market close.
  From this cached dataset compute all five breadth indicators daily.

OUTPUT UI:
  - Five horizontal segmented bars, each split green/red with counts and
    percentages on both sides: e.g. "312 Advancing (62.4%) | 188 Declining"
  - McClellan Oscillator shown as a KPI chip: green if > 0, red if < 0,
    with the numeric value
  - Bars update on each page load (from cache, not live-streaming)
  - Tooltip on hover explains what each indicator means

DATA SOURCES:
  - S&P 500 constituent list: Wikipedia (scraped weekly, cached)
  - Price data: yfinance batch download (cached daily)


──────────────────────────────────────────────────────────────────────
2.2  Global Indices Live Table
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  A table of major global stock indices with live/end-of-day prices,
  daily change, and a 5-day sparkline — similar to the Trading Economics
  homepage index table. Gives instant macro context on any market day.

INDICES TO INCLUDE (grouped by region):

  Americas:
    S&P 500        → ^GSPC     Nasdaq 100    → ^NDX
    Dow Jones 30   → ^DJI      Russell 2000  → ^RUT
    Brazil Bovespa → ^BVSP     Canada TSX    → ^GSPTSE
    Mexico IPC     → ^MXX

  Europe:
    FTSE 100       → ^FTSE     DAX 40        → ^GDAXI
    CAC 40         → ^FCHI     Euro Stoxx 50 → ^STOXX50E
    AEX (NL)       → ^AEX      IBEX 35       → ^IBEX
    Swiss SMI      → ^SSMI     FTSE MIB (IT) → FTSEMIB.MI

  Asia-Pacific:
    Nikkei 225     → ^N225     Hang Seng     → ^HSI
    Shanghai Comp  → 000001.SS ASX 200       → ^AXJO
    SENSEX         → ^BSESN    KOSPI (KR)    → ^KS11
    Straits Times  → ^STI

  All tickers above are available via yfinance at no cost.

DATA TO SHOW PER INDEX:
  - Index name + country flag emoji
  - Current/last price
  - Daily change in points and in %
  - 5-day sparkline (mini line chart)
  - 1-month change % (for momentum context)
  - YTD change %

DATA SOURCE:
  - yfinance: yf.download() with all index tickers, period="3mo",
    interval="1d", grouped by ticker. Compute all metrics from this.
  - Cache results; refresh during market hours every 15 minutes,
    once daily outside market hours.

OUTPUT UI:
  - Tabbed by region: [All] [Americas] [Europe] [Asia-Pacific]
  - Sortable columns: by name, price, 1D%, 1M%, YTD%
  - Colour coding: green rows for positive day, red for negative
  - Sparklines rendered inline using a lightweight chart library
    (recharts or react-sparklines)


──────────────────────────────────────────────────────────────────────
2.3  Fear & Greed Composite Indicator
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  A proprietary composite sentiment index built entirely from free data,
  modelled after CNN's Fear & Greed Index but computed in-house. It
  aggregates 7 market signals into a single score from 0 (Extreme Fear)
  to 100 (Extreme Greed), displayed as a gauge/speedometer. This gives
  users an instant macro sentiment reading that contextualises all other
  analysis on the platform.

  This is one of the most high-impact features to add — it requires no
  paid API and provides a signature, sticky feature that users return to
  daily.

THE 7 COMPONENT SIGNALS (each scored 0–100, then averaged):

  Signal 1 — Stock Price Momentum
    Description: Whether the S&P 500 is trading above or below its
    125-day moving average, and by how much.
    Calculation: Compute the percentage deviation of the S&P 500
    (^GSPC) closing price from its 125-day SMA. Normalise this
    deviation using a rolling 2-year z-score. Map z-score to 0–100
    using a sigmoid or percentile transform.
    Data source: yfinance — ^GSPC daily prices, period="3y"

  Signal 2 — Stock Price Strength (New Highs vs New Lows)
    Description: The ratio of S&P 500 stocks hitting 52-week highs
    versus those hitting 52-week lows. When more stocks are making
    new highs, sentiment is greedy; more new lows signals fear.
    Calculation: Use the breadth data already computed in Phase 2.1.
    Score = (new_highs / (new_highs + new_lows)) × 100
    Data source: S&P 500 constituent prices via yfinance (from the
    same batch cache used in Phase 2.1)

  Signal 3 — Stock Price Breadth (McClellan Volume Summation Index)
    Description: Whether advancing volume is dominating declining
    volume. Persistent positive volume breadth = greed.
    Calculation: For each day compute (advancing stocks − declining
    stocks). Then compute a 19-day EMA and a 39-day EMA of this
    series. The McClellan Oscillator = 19d EMA − 39d EMA.
    The Summation Index = running cumulative sum of the Oscillator.
    Normalise the Summation Index to 0–100 over a 2-year lookback
    window using percentile rank.
    Data source: S&P 500 constituent daily prices from Phase 2.1 cache

  Signal 4 — Put/Call Ratio
    Description: The ratio of put option volume to call option volume
    on the S&P 500. High put/call (>1.0) = fear/hedging; low (<0.7)
    = greed/speculation. Uses the CBOE total put/call ratio.
    Calculation: Fetch CBOE put/call ratio from FRED series:
    CBOE/PUTCALL (if available) or compute as a proxy using the
    aggregate put vs call open interest on SPY from yfinance options
    chain (yf.Ticker("SPY").option_chain(nearest_expiry)).
    Score = 100 − percentile_rank(put_call_ratio, 2yr_lookback) × 100
    (inverted because high put/call = fear = low score)
    Data source: FRED series CBOE/PUTCALL (primary), yfinance SPY
    options chain as fallback

  Signal 5 — Market Volatility (VIX)
    Description: The CBOE Volatility Index. High VIX = fear, low VIX
    = complacency/greed. VIX is the market's 30-day implied volatility
    expectation on S&P 500 options.
    Calculation: Fetch VIX closing price via yfinance ticker ^VIX.
    Score = 100 − percentile_rank(VIX, 2yr_lookback) × 100
    (inverted because high VIX = fear = low score)
    Data source: yfinance — ^VIX daily prices, period="3y"

  Signal 6 — Safe Haven Demand (Stocks vs Bonds)
    Description: Measures the relative weekly return of equities vs
    Treasuries. When investors flee to bonds, it signals fear;
    when they prefer equities, it signals greed.
    Calculation: Compute 20-day rolling return for S&P 500 (^GSPC)
    and for 20-Year Treasury ETF (TLT, which tracks long-duration
    Treasuries and is available free via yfinance).
    Safe Haven Score = normalised spread: stocks_return − bonds_return
    over a 2-year lookback, converted to 0–100 via percentile rank.
    Data source: yfinance — ^GSPC and TLT daily prices

  Signal 7 — Junk Bond Demand (Credit Spread)
    Description: When investors are greedy they accept lower yields on
    high-yield (junk) bonds, compressing spreads. Wide spreads signal
    fear and risk aversion.
    Calculation: Fetch the ICE BofA US High Yield Option-Adjusted Spread
    from FRED series BAMLH0A0HYM2. Lower spread = greed, higher = fear.
    Score = 100 − percentile_rank(HY_spread, 2yr_lookback) × 100
    Data source: FRED series BAMLH0A0HYM2

COMPOSITE SCORE:
  Axiom Fear & Greed = simple average of all 7 signal scores (0–100)
  If any signal fails to compute, exclude it and average the rest.
  Always show which signals contributed and their individual scores.

VERDICT LABELS:
  0–20   → "Extreme Fear"  (dark red)
  21–40  → "Fear"          (red/orange)
  41–59  → "Neutral"       (yellow/grey)
  60–79  → "Greed"         (light green)
  80–100 → "Extreme Greed" (dark green)

OUTPUT UI:
  - Speedometer/gauge dial prominently displayed, needle pointing to
    current score
  - Large score number (e.g. "34") with verdict label below
  - "Yesterday: 31 | Last Week: 28 | Last Month: 45" comparison row
  - 90-day historical line chart of the composite score
  - Expandable panel showing all 7 signals as individual mini-gauges
    or progress bars with their individual scores and a one-line
    explanation of what each is measuring
  - Caching: recompute daily at market close, serve from cache during
    the day

DATA SOURCES SUMMARY:
  - yfinance: ^GSPC, ^VIX, TLT, SPY (options chain), all S&P 500
    constituents (from Phase 2.1 cache)
  - FRED: BAMLH0A0HYM2 (HY credit spread), CBOE/PUTCALL (put/call ratio)

FILES:
  backend/services/fear_greed.py          (signal computation engine)
  backend/routes/dashboard.py             (endpoint: GET /api/dashboard/fear-greed)
  frontend/components/dashboard/FearGreedGauge.tsx
  frontend/components/dashboard/SignalBreakdown.tsx


──────────────────────────────────────────────────────────────────────
2.4  Dashboard Page Layout & Navigation
──────────────────────────────────────────────────────────────────────
WHAT TO BUILD:
  A new top-level page at route /dashboard that serves as the platform
  homepage and morning briefing. It should be the default landing page
  when users open Axiom Finance, replacing or supplementing the current
  Markets default.

PAGE LAYOUT (top to bottom):

  [1] Market Breadth Bar (Phase 2.1)
      Full-width, sticky at top. Always visible.

  [2] Three-Column Header Row
      Left:   Fear & Greed Gauge (Phase 2.3) — compact version
      Centre: Today's date, market session status (Pre-market /
              Open / After-hours / Closed) with time to open/close
      Right:  Macro Regime badge (from Phase 0.3) — US current regime
              with colour and small 2×2 quadrant mini-chart

  [3] Global Indices Table (Phase 2.2)
      Full-width, region-tabbed, sortable

  [4] Two-Column Row
      Left:  US Yield Curve (existing, already works — pull from Macro
             tab into dashboard as a compact embedded chart)
      Right: Top Movers strip — 5 biggest S&P 500 gainers and 5 biggest
             losers for the day, computed from the constituent cache

  [5] Sector Performance Summary (compact version of Phase 10)
      11 sector ETFs (XLF, XLK, XLE etc.) shown as horizontal bars,
      1D change %, colour-coded. Links to the full Sectors tab.

  [6] Upcoming Economic Events (next 3 days, compact)
      A mini calendar strip showing the next 3 high-impact macro events
      (date, flag, event name, consensus). Links to full Calendar page
      (Phase 4).

NAVIGATION:
  Add "Dashboard" as the first item in the top navigation bar, before
  "Markets" and "Macro". This should be the entry point users land on.

FILES:
  frontend/app/dashboard/page.tsx           (new page)
  frontend/components/dashboard/SessionBadge.tsx
  frontend/components/dashboard/TopMovers.tsx
  frontend/components/dashboard/CompactYieldCurve.tsx
  frontend/components/dashboard/CompactSectorBars.tsx
  frontend/components/dashboard/MiniCalendarStrip.tsx


──────────────────────────────────────────────────────────────────────
2.5  Top Movers — Biggest Gainers, Losers & Unusual Volume
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  Surfaces the most notable stocks of the day from across the S&P 500
  universe in categorised lists — similar to Finviz's homepage signal
  lists. Gives traders and investors immediate actionable signals
  without needing to run a screener manually.

CATEGORIES TO COMPUTE:
  Using the S&P 500 constituent daily price cache from Phase 2.1:

  Top 5 Gainers:
    Stocks with highest positive daily return %

  Top 5 Losers:
    Stocks with largest negative daily return %

  Unusual Volume:
    Stocks where today's volume > 2× their 20-day average daily volume
    and sorted by the volume ratio (today_vol / avg_20d_vol)
    Signals: earnings releases, news events, option expiry activity

  52-Week Highs:
    Stocks within 0.5% of their 52-week high — breakout candidates

  52-Week Lows:
    Stocks within 0.5% of their 52-week low — potential reversals or
    continued downtrends depending on context

  Most Volatile Today:
    Stocks with the highest intraday range % = (high − low) / open × 100

DATA SOURCE:
  All from S&P 500 constituent price cache (yfinance batch download,
  refreshed daily). Volume data available in yfinance OHLCV output.
  No additional API calls needed beyond what Phase 2.1 already fetches.

OUTPUT UI ON DASHBOARD:
  Displayed as a tabbed compact table on the dashboard (2.4):
  Tabs: [Gainers] [Losers] [Unusual Volume] [New Highs] [New Lows]
  Each row: ticker | company name | price | 1D% | volume ratio

  Also available as a full-page view by clicking "View All" which routes
  to the Markets → Screener tab with the preset pre-applied (Phase 5).

FILES:
  backend/services/movers.py              (computes all mover categories)
  backend/routes/dashboard.py             (add endpoint: GET /api/dashboard/movers)
  frontend/components/dashboard/TopMovers.tsx


═══════════════════════════════════════════════════════════════════════
PHASE 3 — S&P 500 TREEMAP (MARKET VISUALISATION)
The single most iconic market visualisation in professional finance,
pioneered by Finviz. Sizes each stock by market cap, colours it by
daily performance. Gives an instant visual read on which sectors and
stocks are moving the market.
═══════════════════════════════════════════════════════════════════════

──────────────────────────────────────────────────────────────────────
3.1  Treemap Data Pipeline
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  Builds a hierarchical dataset of all S&P 500 stocks organised by
  sector → industry → stock, with market cap as the size dimension and
  daily/weekly/monthly return as the colour dimension.

DATA NEEDED PER STOCK:
  - Ticker symbol
  - Company name
  - Sector and industry (from yfinance Ticker.info)
  - Market capitalisation (from yfinance Ticker.info["marketCap"])
  - Daily return % (from price cache)
  - Weekly return % (from price cache, 5-day lookback)
  - Monthly return % (from price cache, 22-day lookback)
  - P/E ratio (from Ticker.info["trailingPE"], for tooltip)
  - 52-week high/low proximity (for tooltip)

CONSTITUENT LIST:
  Same Wikipedia-scraped S&P 500 list from Phase 2.1. Enrich it with
  sector and industry data fetched once per week from yfinance and cached.
  The FinanceDatabase library (pip install financedatabase) can also
  provide pre-categorised sector/industry metadata for all tickers,
  avoiding the need for 500 individual yfinance .info calls.

DATA HIERARCHY STRUCTURE:
  The backend should return a nested JSON tree:
  {
    "name": "S&P 500",
    "children": [
      {
        "name": "Technology",
        "children": [
          {
            "name": "Semiconductors",
            "children": [
              { "ticker": "NVDA", "name": "NVIDIA", "market_cap": 3.2e12,
                "return_1d": 2.4, "return_1w": 5.1, "return_1m": 12.3,
                "pe": 45.2 }
            ]
          }
        ]
      }
    ]
  }

INDICES TO SUPPORT:
  Start with S&P 500. Later extend to:
  - Nasdaq 100 (top 100 by market cap from ^NDX holdings)
  - Dow Jones 30 (30 fixed constituents)

DATA SOURCE:
  All from yfinance (constituent prices, market caps, fundamentals).
  FinanceDatabase for sector/industry classification fallback.

──────────────────────────────────────────────────────────────────────
3.2  Treemap Frontend Component
──────────────────────────────────────────────────────────────────────
WHAT TO BUILD:
  An interactive, zoomable treemap rendered in the browser. Rectangles
  are sized by market cap (log scale to prevent mega-caps from totally
  dominating), coloured by return using a diverging red-white-green
  colour scale.

COLOUR SCALE:
  -3% or worse  → deep red    (#dc2626)
  -1.5%         → light red
  0%            → white/neutral (#f8fafc)
  +1.5%         → light green
    (continuing 3.2 — Treemap Frontend Component)

  +3% or better → deep green  (#16a34a)
  Saturation should be smooth and continuous — not binary.
  The colour scale midpoint (white/neutral) anchors at exactly 0%.
  Recommended: use a linear interpolation between the three anchor
  colours (red → white → green) mapping the return range −5% to +5%.
  Beyond ±5%, clamp to the maximum saturation colour.

SIZING:
  Rectangle area must be proportional to market cap. Because S&P 500
  constituents span market caps from ~$3 trillion (AAPL/NVDA) down to
  ~$5 billion, use a square root or logarithmic scale for area so that
  smaller companies remain visible and readable. Linear scale makes
  mega-caps crowd out everything else. Log scale is the correct choice.

RENDERING LIBRARY:
  Use the `d3-hierarchy` treemap layout (from the d3 npm package) for
  the squarified treemap algorithm. React handles the rendering — d3
  only computes the rectangle positions (x, y, width, height) which
  are then passed to SVG rect elements rendered by React. Do not use
  d3 to mutate the DOM directly; keep React in control of the DOM.
  Alternatively, if d3 integration feels heavy, the `recharts` Treemap
  component is a simpler option that accepts hierarchical data directly,
  though it has less layout control than d3's squarify algorithm.

INTERACTIVITY:
  Hover tooltip:
    Show a floating card on hover over any stock rectangle containing:
    - Company name and ticker symbol
    - Current price
    - Daily return % (large, coloured)
    - Market cap (formatted: $3.2T, $450B etc.)
    - P/E ratio (TTM)
    - 52-week range and current proximity (% from high, % from low)
    - Sector and industry labels

  Click behaviour:
    Clicking a stock rectangle navigates to that stock's page on the
    Markets tab (pre-filling the ticker search with that symbol).
    Clicking a sector label zooms into that sector showing only its
    industries and constituent stocks. A "← Back to All Sectors"
    breadcrumb appears when zoomed.

  Drill-down levels:
    Level 1: All sectors (11 coloured sector group labels)
    Level 2: Industries within a sector (click sector to zoom)
    Level 3: Individual stocks within an industry (deepest level)
    Each level shows progressively finer rectangles.

CONTROLS BAR (above the treemap):
  - Period selector pills: [1D] [1W] [1M] [3M] [YTD] [1Y]
    Changes the return metric used for colouring. The 1D view is the
    default and uses today's daily return. Other periods use the
    appropriate lookback from the price cache.

  - Index selector dropdown: [S&P 500] [Nasdaq 100] [Dow 30]
    Switches the universe of stocks shown.

  - Group by: [Sector] [Industry]
    At the "Sector" grouping, sector labels are shown as headers.
    At "Industry" grouping, individual industries are the grouping
    containers without the sector layer.

  - Colour by: [Return %] [Market Cap] [Volume vs Avg]
    "Return %" is the default. "Market Cap" colours by market cap
    size (useful for visualising concentration). "Volume vs Avg"
    colours by today's volume ratio vs 20-day average (highlights
    unusual activity).

  - Legend bar: displayed below the controls showing the colour scale
    from deep red (−5% or worse) through white (0%) to deep green
    (+5% or better) with tick marks.

PERFORMANCE CONSIDERATIONS:
  Rendering 500 SVG rectangles is well within browser capability.
  However, the treemap layout computation should be done once on data
  load (not on every render). Cache the computed layout positions in
  React state. Only recompute the layout when the index or grouping
  changes. Colour updates (e.g. switching from 1D to 1W) should only
  change fill colours, not recompute the layout.

  The data payload from the backend should be pre-sorted by market cap
  descending so the squarify algorithm places the largest stocks in the
  most prominent positions (top-left).

PLACEMENT IN APP:
  Replace the existing Sectors tab heatmap with the Treemap as the
  primary visualisation. The old sector ETF heatmap can be demoted to
  a secondary view accessible via a "Switch to Heatmap" toggle.
  Also embed a compact, non-interactive version (top-level sectors only,
  no drill-down) on the Dashboard page (Phase 2.4) for at-a-glance
  sector rotation context.

FILES:
  backend/routes/treemap.py                   (GET /api/treemap?index=sp500&period=1d)
  backend/services/treemap_builder.py         (hierarchy assembly + enrichment)
  frontend/app/markets/tabs/Sectors.tsx       (replace heatmap with treemap)
  frontend/components/treemap/Treemap.tsx     (main d3/recharts component)
  frontend/components/treemap/TreemapTooltip.tsx
  frontend/components/treemap/TreemapControls.tsx
  frontend/components/treemap/ColourLegend.tsx
  frontend/components/dashboard/CompactTreemap.tsx (dashboard mini version)


═══════════════════════════════════════════════════════════════════════
PHASE 4 — ECONOMIC CALENDAR
A dedicated calendar page aggregating macro data releases, earnings
events, dividend dates, and IPOs into a single unified weekly-grid
interface. Inspired by Trading Economics' calendar (Actual/Previous/
Consensus columns + impact stars) and TradingView's unified calendar
(macro + earnings + dividends + IPOs in one view).
═══════════════════════════════════════════════════════════════════════

──────────────────────────────────────────────────────────────────────
4.1  Macro Economic Releases Calendar
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  Shows all upcoming and recent macroeconomic data releases with the
  Actual, Previous, Consensus, and Forecast values — the same column
  structure used by Trading Economics and Bloomberg. Users can filter
  by country, impact level, and category. This is the most-visited
  page on most macro-focused platforms because traders need it daily.

DATA SOURCES FOR MACRO EVENTS:

  Primary — FRED Release Calendar (free, no key required for dates):
    Endpoint: https://api.stlouisfed.org/fred/releases/dates
    Returns all scheduled FRED data release dates. Covers all major
    US macro series: CPI, PPI, PCE, GDP advance/revised/final,
    NFP (Nonfarm Payrolls), Unemployment Rate, Retail Sales, ISM
    Manufacturing/Services PMI, Industrial Production, Consumer
    Confidence, Building Permits, Housing Starts, Trade Balance,
    JOLTS, and many more.
    This gives accurate release timestamps for all US indicators.

  Secondary — Finnhub Economic Calendar (free tier):
    Endpoint: https://finnhub.io/api/v1/calendar/economic
    Free tier provides upcoming economic events with country,
    event name, impact level, actual, previous, estimate, and unit.
    Covers major events across US, Eurozone, UK, Japan, Canada,
    Australia and more. Rate limit on free tier: 60 calls/minute.
    Use to supplement FRED with international events.

  Tertiary — Static FOMC/ECB/BOJ/BOE Meeting Dates (hardcoded JSON):
    Store central bank meeting dates in backend/data/cb_meetings.json.
    Update this file quarterly when central banks publish their forward
    calendars. Central bank decisions are the single most market-moving
    events and must never be missing from the calendar.
    Include: FOMC (8 meetings/year), ECB Governing Council (8/year),
    Bank of England MPC (8/year), Bank of Japan (8/year),
    Swiss National Bank (4/year), Reserve Bank of Australia (11/year).

  Quaternary — Eurostat Release Calendar:
    Eurostat publishes a release calendar at:
    https://ec.europa.eu/eurostat/web/main/news/release-calendar
    Parse this to get EU/Eurozone GDP, HICP (inflation), unemployment,
    trade balance, and industrial production dates.

FIELDS TO STORE AND DISPLAY PER EVENT:
  - datetime (UTC, converted to user timezone in frontend)
  - country_code and flag emoji
  - event_name (e.g. "US Nonfarm Payrolls")
  - period (e.g. "Jun 2026")
  - impact_level: 1 (low, grey star), 2 (medium, yellow star),
    3 (high, red star) — assign manually for known events or derive
    from FRED's release importance metadata
  - category: GDP | Inflation | Employment | Interest Rate | PMI |
    Trade | Consumer | Housing | Manufacturing | Energy
  - actual (null if not yet released)
  - previous
  - consensus / estimate
  - forecast (IMF/OECD forward projection where available)
  - beat/miss flag: if actual is known, compare to consensus and flag
    green (beat) or red (miss) — applied as colour to the Actual cell

IMPACT LEVEL ASSIGNMENT:
  Maintain a static lookup of high-impact events in
  backend/data/event_impact.json. Examples of impact=3 (high):
  US: NFP, CPI, FOMC Decision, Core PCE, GDP advance estimate,
      Retail Sales, ISM Manufacturing PMI
  EU: ECB Rate Decision, Eurozone CPI Flash, Eurozone GDP
  UK: BOE Rate Decision, UK CPI, UK GDP
  JP: BOJ Decision, Japan CPI, Japan GDP
  For any event not in the lookup, default to impact=1.

──────────────────────────────────────────────────────────────────────
4.2  Earnings Calendar
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  Shows upcoming and recent company earnings releases with EPS estimate,
  revenue estimate, and actual results (once reported). Allows users to
  see at a glance which stocks in their watchlist or the broader index
  are reporting soon.

DATA SOURCE:
  Primary — yfinance:
    yf.Ticker(symbol).calendar returns a dict with "Earnings Date"
    as a key containing the next expected earnings date.
    For a universe-wide calendar, iterate over all S&P 500 tickers
    from the Phase 2.1 constituent list. Batch this with rate-limiting
    and cache results for 24 hours.
    Also provides EPS Estimate, Revenue Estimate from
    yf.Ticker(symbol).earnings_forecasts where available.

  Secondary — Finnhub Earnings Calendar (free tier):
    Endpoint: https://finnhub.io/api/v1/calendar/earnings?from=DATE&to=DATE
    Returns earnings dates with EPS estimate, EPS actual (post-release),
    revenue estimate, revenue actual for the requested date range.
    Free tier allows 1 month of data per call. Use to cross-check
    and supplement yfinance data.

FIELDS PER EARNINGS EVENT:
  - date and time (BMO = Before Market Open, AMC = After Market Close)
  - ticker symbol, company name, sector
  - EPS estimate (consensus)
  - EPS actual (null if not yet reported)
  - Revenue estimate
  - Revenue actual
  - EPS surprise % = (actual − estimate) / abs(estimate) × 100
    (shown in green if beat, red if miss, once actual is available)
  - Market cap (to gauge event significance)

──────────────────────────────────────────────────────────────────────
4.3  Dividend & IPO Calendar
──────────────────────────────────────────────────────────────────────
DIVIDEND CALENDAR DATA:
  yfinance provides ex-dividend dates and dividend amounts via
  yf.Ticker(symbol).dividends (historical) and
  yf.Ticker(symbol).info["exDividendDate"] and ["dividendRate"].
  Batch-compute for the S&P 500 universe. Show upcoming ex-dates within
  the next 30 days, sorted by ex-date.

  Fields: ticker, company, ex-dividend date, dividend amount,
  annualised yield, payout frequency.

IPO CALENDAR DATA:
  Finnhub free tier provides upcoming IPO data:
  Endpoint: https://finnhub.io/api/v1/calendar/ipo?from=DATE&to=DATE
  Fields: symbol, name, date, price range, number of shares,
  market, status (expected/priced/withdrawn).

──────────────────────────────────────────────────────────────────────
4.4  Calendar Page Layout & UX
──────────────────────────────────────────────────────────────────────
ROUTE: /calendar (new top-level page, add to navigation)

TAB ROW (secondary tabs within the calendar page):
  [Economic] [Earnings] [Dividends] [IPO]
  Each tab shows its respective calendar. Default tab: Economic.

VIEW FORMAT — Weekly Grid:
  Display events in a Mon–Sun weekly grid, with today's column
  highlighted with an accent border. Each event is a row within its
  day column. Allow paging forward/backward by week.
  Also provide a "List View" toggle for a simpler chronological list.

FILTER BAR (above the calendar grid):
  For the Economic tab:
    - Impact: [All] [★★★ High] [★★ Medium] [★ Low]
    - Country: multi-select dropdown with flag checkboxes
      (US selected by default, others off)
    - Category: multi-select (GDP, Inflation, Employment etc.)
    - Timezone: selector (default to user's browser timezone)

  For the Earnings tab:
    - Market Cap filter: [All] [Large Cap >$10B] [Mid Cap] [Small Cap]
    - Sector filter: dropdown
    - Time: [BMO only] [AMC only] [All]
    - Index: [S&P 500] [Nasdaq 100] [All]

ACTUAL vs CONSENSUS COLOURING:
  When an event has both actual and consensus values, colour the
  Actual cell: green if actual > consensus (beat), red if below (miss),
  neutral/white if equal or within 0.1% of each other.
  This is the single most important UX feature of a macro calendar
  — it tells the user instantly whether data surprised the market.

COUNTDOWN TIMERS:
  For events within the next 24 hours, show a live countdown timer
  in hours and minutes next to the event row (e.g. "in 3h 42m").
  This is a small but high-value UX detail that builds user habit.

FILES:
  backend/routes/calendar.py               (GET /api/calendar/economic,
                                            /earnings, /dividends, /ipo)
  backend/services/calendar_aggregator.py  (merges all sources)
  backend/data/cb_meetings.json            (static central bank dates)
  backend/data/event_impact.json           (event → impact level lookup)
  frontend/app/calendar/page.tsx           (new calendar page)
  frontend/components/calendar/WeeklyGrid.tsx
  frontend/components/calendar/EventRow.tsx
  frontend/components/calendar/CalendarFilters.tsx
  frontend/components/calendar/CountdownTimer.tsx
  frontend/components/calendar/EarningsRow.tsx


═══════════════════════════════════════════════════════════════════════
PHASE 5 — SCREENER OVERHAUL
Upgrade the existing manual screener from a basic filter builder into
a professional-grade stock discovery tool with pre-built signal presets,
index universe selectors, multiple result view tabs, and a chart
thumbnail mode. Inspired by TradingView's market movers signal pills
and Finviz's multi-view screener table.
═══════════════════════════════════════════════════════════════════════

──────────────────────────────────────────────────────────────────────
5.1  Universe Selector — Move Beyond Manual Ticker Entry
──────────────────────────────────────────────────────────────────────
PROBLEM WITH CURRENT IMPLEMENTATION:
  The existing screener requires users to type tickers manually. This is
  completely unscalable and defeats the purpose of a screener. The user
  should be able to select a pre-defined universe of stocks and then
  filter within it.

UNIVERSES TO SUPPORT:
  S&P 500       (~500 stocks)    — Wikipedia constituent list (Phase 2.1)
  Nasdaq 100    (~100 stocks)    — Store as a static JSON, update monthly.
                                   Source: Wikipedia "Nasdaq-100" article,
                                   same scraping approach as S&P 500.
  Dow Jones 30  (30 stocks)      — Store as a static JSON, rarely changes.
  Russell 2000  (~2000 stocks)   — Use FinanceDatabase library to pull all
                                   US small-cap equities as a proxy. The
                                   actual Russell 2000 list requires a paid
                                   data source; FinanceDatabase's US equity
                                   database filtered by market cap < $2B is
                                   an acceptable free-tier substitute.
  S&P Europe 350 (~350 stocks)   — Use FinanceDatabase filtered by country
                                   = major European nations + exchange =
                                   major European exchanges as a proxy.
  Custom        (user-defined)   — Preserve the existing manual ticker
                                   entry mode as the "Custom" option.

UNIVERSE DATA PIPELINE:
  At startup (and weekly on a cron job), the backend should:
  1. Scrape or load the constituent list for each universe
  2. Batch-fetch fundamental and price data for all constituents from
     yfinance in chunks (100 tickers at a time to respect rate limits)
  3. Compute all screener metrics (see 5.3) and store results in a
     cached data structure (e.g. a Pandas DataFrame serialised to
     Parquet or stored in Redis/SQLite)
  4. Refresh price-based metrics (returns, volume ratios, RSI) daily
     at market close; refresh fundamental metrics (P/E, margins etc.)
     weekly since they change infrequently

DATA SOURCE:
  yfinance Ticker.info for fundamentals (P/E, P/B, EV/EBITDA, margins,
  ROE, market cap, dividend yield, beta, 52-week high/low).
  yfinance Ticker.history for price-based metrics (returns, moving
  averages, volume, RSI computation).
  FinanceDatabase (pip install financedatabase) for universe membership
  and sector/industry classification where yfinance info is missing.


──────────────────────────────────────────────────────────────────────
5.2  Signal Preset Pills — One-Click Discovery
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  A row of clickable pill buttons above the manual filter builder.
  Each pill represents a pre-configured filter combination that
  instantly loads a curated list of stocks. Inspired by TradingView's
  market movers tags (Top Gainers, Biggest Losers, High Beta, 52-Week
  High etc.) and Finviz's Signal dropdown.

  Selecting a preset populates the filter builder with the relevant
  filters AND executes the screen immediately. The user can then
  further refine the results by adding additional manual filters on
  top of the preset.

PRESETS TO IMPLEMENT:

  PRICE ACTION PRESETS:
  ┌─────────────────────────────────────────────────────────────────┐
  │ Top Gainers      │ Stocks with highest positive 1D return %     │
  │ Biggest Losers   │ Stocks with largest negative 1D return %     │
  │ New 52W High     │ Price within 0.5% of 52-week high            │
  │ New 52W Low      │ Price within 0.5% of 52-week low             │
  │ All-Time High    │ Price within 1% of all-time historical high   │
  │ Above SMA 200    │ Price > 200-day moving average (uptrend)      │
  │ Below SMA 200    │ Price < 200-day moving average (downtrend)    │
  │ Golden Cross     │ 50-day SMA crossed above 200-day SMA in last  │
  │                  │ 10 trading days (bullish technical signal)    │
  │ Death Cross      │ 50-day SMA crossed below 200-day SMA in last  │
  │                  │ 10 trading days (bearish technical signal)    │
  └─────────────────────────────────────────────────────────────────┘

  VOLUME & MOMENTUM PRESETS:
  ┌─────────────────────────────────────────────────────────────────┐
  │ Unusual Volume   │ Today's volume > 2× 20-day average volume    │
  │ High Momentum    │ RSI between 50–70 + price > SMA 50 (healthy  │
  │                  │ uptrend, not yet overbought)                  │
  │ Overbought       │ RSI (14-day) > 70                            │
  │ Oversold         │ RSI (14-day) < 30                            │
  │ Most Volatile    │ Highest 20-day annualised volatility          │
  │ High Beta        │ Beta > 1.5 (amplified market moves)          │
  │ Low Volatility   │ Beta < 0.7 + 20-day vol below sector median  │
  └─────────────────────────────────────────────────────────────────┘

  FUNDAMENTAL / VALUE PRESETS:
  ┌─────────────────────────────────────────────────────────────────┐
  │ Undervalued      │ P/E < sector median P/E AND P/B < 3×         │
  │ High Dividend    │ Dividend yield > 3% AND payout ratio < 80%   │
  │ High ROIC        │ Return on Invested Capital > 15%             │
  │ Quality Growth   │ Revenue growth YoY > 10% AND net margin > 10%│
  │ Deep Value       │ P/B < 1.0 AND P/E < 12× (Graham-style)       │
  │ High Earnings    │ EPS growth YoY > 20% (earnings momentum)     │
  │ Growth           │ Revenue growth > 15% YoY (top-line growth)   │
  │ Profitable       │ Net margin > 15% AND ROE > 15%               │
  └─────────────────────────────────────────────────────────────────┘

  SITUATION PRESETS:
  ┌─────────────────────────────────────────────────────────────────┐
  │ Earnings This Wk │ Companies reporting earnings within 7 days    │
  │ Pre-Earnings Dip │ Earnings within 14 days + stock down >5% 1M  │
  │ Post-Earnings    │ Earnings reported within last 5 days         │
  │ Insider Buying   │ Net insider buying in last 30 days (requires  │
  │                  │ SEC Form 4 data — see note below)            │
  └─────────────────────────────────────────────────────────────────┘

  NOTE ON INSIDER DATA:
  SEC Form 4 filings (insider transactions) are public and available
  free from the SEC EDGAR full-text search API at
  https://efts.sec.gov/LATEST/search-index?q=%22form+4%22&dateRange=custom
  or via the EDGAR company search API. This is a free government dataset.
  The "Insider Buying" preset should be deprioritised (implement last)
  as it requires additional data pipeline work, but it is very high-
  value once built.

UI BEHAVIOUR OF PRESET PILLS:
  - Displayed as a scrollable horizontal row of chips/pills
  - Active preset highlighted with filled background
  - Multiple presets cannot be combined (selecting one deselects the
    previous) — but the user can ADD manual filters on top
  - A "Clear Preset" × button removes the preset and resets filters
  - Presets are grouped visually with subtle separators:
    [Price Action] | [Volume & Momentum] | [Fundamentals] | [Situations]


──────────────────────────────────────────────────────────────────────
5.3  Screener Metrics — Full Computed Field List
──────────────────────────────────────────────────────────────────────
These are all the metrics computed for each stock in the universe
cache and available as filter dimensions and result columns.

PRICE & MARKET DATA (from yfinance price history):
  - Current Price
  - Daily Return %
  - Weekly Return % (5-day)
  - Monthly Return % (22-day)
  - 3-Month Return % (66-day)
  - 6-Month Return % (126-day)
  - YTD Return %
  - 1-Year Return % (252-day)
  - 52-Week High and Low (price values)
  - % from 52-Week High = (price − high_52w) / high_52w × 100
  - % from 52-Week Low  = (price − low_52w)  / low_52w  × 100
  - Average Daily Volume (20-day)
  - Today's Volume
  - Relative Volume = today_vol / avg_20d_vol

TECHNICAL INDICATORS (computed from price history):
  - SMA 20, SMA 50, SMA 200 (price vs each moving average, as %)
  - EMA 12, EMA 26
  - RSI 14-day (standard Wilder's RSI formula)
  - MACD Signal: whether MACD line is above or below signal line
  - Bollinger Band %B = (price − lower_band) / (upper_band − lower_band)
  - ATR 14-day (Average True Range, normalised as % of price)
  - Annualised 20-day Volatility (stddev of daily returns × √252)
  - Beta (3-year vs S&P 500, from yfinance Ticker.info)
  - Golden/Death Cross flag (SMA50 vs SMA200 crossover in last 10 days)

FUNDAMENTAL DATA (from yfinance Ticker.info):
  - Market Capitalisation
  - Enterprise Value
  - Trailing P/E
  - Forward P/E
  - P/B Ratio (Price to Book)
  - P/S Ratio (Price to Sales, TTM)
  - EV/EBITDA
  - EV/Revenue
  - PEG Ratio
  - Dividend Yield %
  - Payout Ratio %
  - Gross Margin %
  - Operating Margin %
  - Net Profit Margin %
  - Return on Equity (ROE) %
  - Return on Assets (ROA) %
  - Return on Invested Capital (ROIC) % — computed as:
    NOPAT / (Total Equity + Total Debt − Cash)
  - Revenue Growth YoY %
  - EPS Growth YoY %
  - Earnings Growth (5-year estimate) %
  - Total Debt / Equity ratio
  - Current Ratio (current assets / current liabilities)
  - Quick Ratio
  - Free Cash Flow (TTM, in millions)
  - FCF Yield = FCF / Market Cap × 100
  - Short Float % (shares sold short / float shares)
  - Analyst Recommendation (from yfinance Ticker.info["recommendationKey"]:
    strong_buy, buy, hold, sell, strong_sell)

UNIVERSE METADATA:
  - Sector
  - Industry
  - Country
  - Exchange
  - Index Membership (S&P 500, Nasdaq 100, Dow 30)


──────────────────────────────────────────────────────────────────────
5.4  Manual Filter Builder Enhancement
──────────────────────────────────────────────────────────────────────
WHAT TO IMPROVE OVER CURRENT IMPLEMENTATION:
  The current filter builder (metric / operator / value) is functional
  but needs the following upgrades:

  1. Metric dropdown must expose all fields listed in 5.3 — the current
     implementation likely only exposes a small subset. Group the
     dropdown by category: [Price & Market] [Technical] [Fundamental]
     [Metadata].

  2. Operator options should be context-aware:
     - Numeric fields: > | < | >= | <= | between (range) | =
     - Boolean/flag fields (Golden Cross, MACD Signal): = true | = false
     - String fields (Sector, Industry): = | contains | not =
     - For "between" operator, show two value inputs (min and max)

  3. Sector/Industry filter should use a searchable dropdown populated
     from the universe data, not a free-text field.

  4. Add a "Match All / Match Any" toggle (AND logic vs OR logic between
     filters). Default is AND (all filters must be satisfied).

  5. Show a live result count ("142 stocks match") that updates as the
     user adjusts filters, before they click Apply/Run.

  6. Allow saving named filter combinations as "Saved Screens" stored
     in localStorage (no backend needed). Saved screens should appear
     in a dropdown alongside the preset pills.


──────────────────────────────────────────────────────────────────────
5.5  Result View Tabs
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  Multiple view modes for the screener results table, each showing
  a different set of columns. Inspired by TradingView's market movers
  page which has tabs for Overview, Performance, Technicals, Valuation,
  Dividends, Profitability, Income Statement, Balance Sheet, Cash Flow.

TABS TO IMPLEMENT:

  OVERVIEW (default):
    Ticker | Company | Price | 1D% | Volume | Rel.Vol | Mkt Cap |
    P/E | Sector | Analyst Rating

  PERFORMANCE:
    Ticker | Price | 1D% | 1W% | 1M% | 3M% | 6M% | YTD% | 1Y%

  TECHNICALS:
    Ticker | Price | RSI | SMA50 vs Price% | SMA200 vs Price% |
    Bollinger %B | Relative Volume | 20D Volatility | Beta | MACD Signal

  VALUATION:
    Ticker | Price | P/E (TTM) | P/E (Fwd) | P/B | P/S |
    EV/EBITDA | PEG | FCF Yield | EV/Revenue

  PROFITABILITY:
    Ticker | Gross Margin | Operating Margin | Net Margin |
    ROE | ROA | ROIC | Revenue Growth YoY | EPS Growth YoY

  DIVIDENDS:
    Ticker | Price | Dividend Yield | Annual Dividend | Payout Ratio |
    Ex-Dividend Date | 5Y Dividend Growth | Dividend Frequency
      FINANCIALS:
    Ticker | Revenue (TTM) | Revenue Growth YoY | Gross Profit |
    EBITDA | Net Income | EPS (TTM) | EPS Growth YoY | Free Cash Flow

  BALANCE SHEET:
    Ticker | Total Assets | Total Debt | Total Cash | Net Cash/Debt |
    Debt/Equity | Current Ratio | Quick Ratio | Book Value Per Share

  ALL COLUMNS (power user mode):
    All fields from 5.3 in a horizontally scrollable super-table.
    Columns are reorderable by drag-and-drop. User can pin up to 3
    columns to the left as frozen columns. Column visibility can be
    toggled per-column. Settings persisted in localStorage.

TABLE BEHAVIOUR ACROSS ALL VIEWS:
  - Every column header is clickable to sort ascending/descending
  - Alternating row background for readability
  - Ticker symbol is a hyperlink navigating to that stock's page in
    the Markets tab
  - Positive return values coloured green, negative red, throughout
  - Results count shown above table: "Showing 87 of 500 stocks"
  - Pagination: 50 rows per page with page controls, OR a "Load All"
    button for power users who want to scroll the full list
  - CSV export button: exports all results (all columns, not just the
    active tab's columns) as a flat CSV file


──────────────────────────────────────────────────────────────────────
5.6  Charts View — Thumbnail Gallery Mode
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  An alternative result display mode (alongside the table tabs) that
  shows screener results as a gallery of small price chart thumbnails
  — one per matching stock. Used by Finviz as a key differentiator.
  Allows users to visually scan dozens of charts simultaneously for
  technical pattern recognition.

HOW IT WORKS:
  - Add a "Charts" button alongside the tab row (or as a view toggle:
    [Table | Charts])
  - For each stock in the screener results (up to 50 shown at once),
    render a compact 200×120px sparkline chart showing the last 3
    months of daily closes
  - Overlay the 50-day SMA as a coloured line
  - Label each card: ticker, company name, 1D% change (coloured), price
  - Cards laid out in a responsive CSS grid (4 columns on desktop,
    2 on tablet, 1 on mobile)
  - Clicking any card navigates to that stock's Markets tab page
  - "Load More" button to show the next 50 results

CHART DATA:
  The 3-month daily price history per stock is already available in
  the Phase 2.1 / 5.1 constituent price cache. No additional API calls
  needed — serve directly from the existing data.

PERFORMANCE:
  Use canvas-based sparklines (e.g. the lightweight-charts library or
  react-sparklines) rather than full SVG charts. Canvas renders
  hundreds of small charts far faster than SVG. Each thumbnail should
  render in under 5ms.

FILES FOR PHASE 5:
  backend/routes/screener.py            (enhanced — all metrics, all views)
  backend/services/screener_engine.py   (metric computation, filtering logic)
  backend/services/universe_loader.py   (constituent lists, weekly refresh)
  backend/data/sp500_constituents.json  (cached Wikipedia scrape)
  backend/data/nasdaq100.json           (static, monthly update)
  backend/data/dow30.json               (static, rarely changes)
  frontend/app/markets/tabs/Screener.tsx
  frontend/components/screener/PresetPills.tsx
  frontend/components/screener/UniverseSelector.tsx
  frontend/components/screener/FilterBuilder.tsx
  frontend/components/screener/ResultsTable.tsx
  frontend/components/screener/ResultViewTabs.tsx
  frontend/components/screener/ChartsThumbnailGrid.tsx
  frontend/components/screener/SavedScreens.tsx


═══════════════════════════════════════════════════════════════════════
PHASE 6 — ROLLING QUANTITATIVE METRICS (Risk Tab Enhancement)
The existing Risk tab shows point-in-time statistics (Sharpe, Beta,
Volatility, VaR etc.) which are useful but static. Add time-series
charts of these metrics computed over rolling windows, giving users
insight into how a stock's risk profile has changed over time — a
feature present on institutional platforms like Bloomberg and Koyfin
but rare in free tools.
═══════════════════════════════════════════════════════════════════════

──────────────────────────────────────────────────────────────────────
6.1  Rolling Window Selector
──────────────────────────────────────────────────────────────────────
WHAT TO BUILD:
  A window size selector added to the Risk tab that changes the rolling
  period used for all rolling metrics. Options: [20D] [60D] [120D] [252D]
  Default: 60D (approximately 3 months, the most common professional
  lookback for rolling risk metrics).

  This single control affects all charts in section 6.2 simultaneously.
  Switching between window sizes re-renders all charts instantly from
  the same pre-computed data without additional API calls.


──────────────────────────────────────────────────────────────────────
6.2  Rolling Metric Time-Series Charts
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  For each ticker in the comparison set, compute the selected metric
  over a rolling window across the full 3-year price history, then
  plot the result as a time-series line chart. This shows how risk
  characteristics evolved through different market regimes.

METRICS TO CHART:

  Rolling Sharpe Ratio:
    At each date t, compute the annualised mean and standard deviation
    of daily returns over the preceding [window] days. Divide by √252.
    Subtract the annualised risk-free rate (FRED DGS10 / 252 per day).
    Plot as a line chart per ticker. A horizontal dashed line at 1.0
    marks the "acceptable" threshold. Below 0 means negative risk-
    adjusted returns over that rolling period.
    This is the single most informative rolling risk chart.

  Rolling Volatility (Annualised):
    Standard deviation of daily returns over [window] days × √252.
    Plot per ticker. Spikes reveal periods of elevated uncertainty
    (e.g. earnings, market dislocations). Comparison across tickers
    shows which is structurally more volatile.

  Rolling Beta (vs S&P 500):
    Covariance of ticker daily returns with ^GSPC daily returns over
    [window] days, divided by variance of ^GSPC returns over same
    window. A beta that drifts from 1.5 to 0.8 over time shows the
    stock's market sensitivity is changing — extremely useful for
    portfolio construction.
    Requires fetching ^GSPC price history alongside the tickers
    (already available from Phase 2.1 cache).

  Rolling Sortino Ratio:
    Same as Sharpe but the denominator uses only downside deviation
    (standard deviation of negative daily returns only, × √252).
    More appropriate for asymmetric return distributions. Plot
    alongside Sharpe for comparison.

  Rolling Maximum Drawdown:
    At each date t, the maximum peak-to-trough decline within the
    preceding [window] days. Expressed as a negative percentage.
    Shows periods when the stock suffered its worst sustained losses.
    Plot as a filled area chart (shaded red below zero) rather than
    a line for visual impact.

  Rolling Correlation Matrix (Heatmap Over Time):
    For multi-ticker comparisons, compute the pairwise correlation
    between every pair of selected tickers over the rolling window.
    Rather than a static correlation heatmap (which already exists on
    the Risk tab), add a line chart showing one specific pair's rolling
    correlation over time. If 2 tickers are selected, show that one
    pair. If 3+ are selected, show a dropdown to pick which pair.
    Correlation that drifts toward 1.0 means diversification benefit
    is diminishing — critically important for portfolio managers.

  Rolling Value at Risk (Historical VaR):
    At each date t, take the return distribution of the preceding
    [window] days and read off the 5th percentile return (95% VaR)
    and the 1st percentile return (99% VaR). Expressed as a
    percentage loss. Plot as two lines (95% and 99% confidence).
    Spikes in VaR indicate periods when the tail risk was elevated.

DATA SOURCE FOR ALL ROLLING METRICS:
  yfinance: 3-year daily OHLCV history for all selected tickers plus
  ^GSPC (benchmark). Fetch once per session and cache in the backend.
  The rolling computations are straightforward pandas rolling window
  operations performed server-side.
  FRED: DGS10 (daily 10Y yield) for risk-free rate in Sharpe/Sortino.


──────────────────────────────────────────────────────────────────────
6.3  Rolling Metrics Layout on Risk Tab
──────────────────────────────────────────────────────────────────────
WHAT TO BUILD:
  Add a new expandable "Rolling Metrics" section at the bottom of the
  existing Risk tab, below the current point-in-time statistics and
  correlation heatmap.

  The section has two sub-views toggled by a button:
  [Overlay View] and [Grid View]

  Overlay View (default):
    A single chart area where multiple rolling metrics for multiple
    tickers are overlaid. Use a metric selector dropdown to choose
    which metric to display (Sharpe / Volatility / Beta / Sortino /
    Max Drawdown / VaR). All selected tickers shown as differently
    coloured lines on the same axes. A legend identifies each ticker.
    Best for direct comparison between 2–4 stocks.

  Grid View:
    A 2×3 grid of small charts, one per metric type, each showing
    all selected tickers. Best for seeing the full risk picture of one
    stock at a glance. Clicking any small chart expands it to full width.

  Time range selector for all charts: [1Y] [2Y] [3Y]
  This controls how far back the rolling history is displayed.

FILES:
  backend/routes/risk.py                (add rolling metrics endpoint)
  backend/services/rolling_engine.py    (all rolling computations)
  frontend/app/markets/tabs/Risk.tsx    (add rolling section)
  frontend/components/risk/RollingCharts.tsx
  frontend/components/risk/RollingWindowSelector.tsx
  frontend/components/risk/MetricSelector.tsx


═══════════════════════════════════════════════════════════════════════
PHASE 7 — OPTIONS & IMPLIED VOLATILITY MODULE (New Tab)
Add a dedicated "Options" tab to the Markets page, providing implied
volatility analysis, options chain data, and key derivatives metrics.
All data sourced from yfinance's options chain at zero cost.
This is a genuine differentiator — no other free platform provides
a clean, integrated options analytics view.
═══════════════════════════════════════════════════════════════════════

──────────────────────────────────────────────────────────────────────
7.1  Options Chain Table
──────────────────────────────────────────────────────────────────────
WHAT TO BUILD:
  A classic side-by-side options chain table: calls on the left,
  puts on the right, strikes in the centre column. The current
  stock price is highlighted in the strike column (at-the-money).

DATA SOURCE:
  yfinance Ticker.options returns a list of all available expiry dates.
  yfinance Ticker.option_chain(expiry) returns two DataFrames:
  calls and puts, each containing:
    contractSymbol, strike, lastPrice, bid, ask, change, percentChange,
    volume, openInterest, impliedVolatility, inTheMoney,
    contractSize, currency

EXPIRY SELECTOR:
  A dropdown listing all available expiry dates for the ticker.
  Default: the nearest expiry (front month).
  Also show the number of days to expiry (DTE) alongside each date.

CHAIN TABLE COLUMNS:
  Calls side:  IV% | OI | Volume | Bid | Ask | Last | Strike | ITM
  Centre:      Strike Price (highlighted yellow if ATM ±2 strikes)
  Puts side:   ITM | Last | Bid | Ask | Volume | OI | IV%

  "ITM" column: a boolean indicator showing whether the option is
  in-the-money (calls: strike < current price; puts: strike > current
  price). ITM rows shaded with a subtle background tint.

  The implied volatility column should display as a percentage with
  2 decimal places (e.g. "34.21%"). Note that yfinance returns IV as
  a decimal (e.g. 0.3421) — divide by 1 if already a decimal, or
  multiply by 100 for display.

FILTER:
  A "Show OTM only" toggle that hides deep in-the-money strikes,
  keeping the table focused on the most liquid/relevant strikes.


──────────────────────────────────────────────────────────────────────
7.2  Implied Volatility Term Structure (IV Curve)
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  Plots the at-the-money implied volatility against days-to-expiry
  across all available expiry dates. This "vol term structure" or
  "vol curve" reveals the market's expectation of future volatility
  at different horizons.

  A normal (upward-sloping) term structure shows higher IV at longer
  expirations. An inverted (downward-sloping) structure — where near-
  term IV exceeds longer-term IV — signals acute near-term fear (e.g.
  around earnings or macro events). This is a key signal for options
  traders and risk managers.

HOW TO COMPUTE:
  For each available expiry date:
  1. Fetch the full option chain (calls + puts) via yfinance
  2. Find the current stock price
  3. Identify the ATM strike: the strike closest to the current price
  4. Take the average of the call IV and put IV at that ATM strike
     (put-call parity means they should be close; averaging reduces noise)
  5. Record (DTE, ATM_IV) as one data point
  6. Repeat for all expiries to build the full term structure

OUTPUT:
  Line chart: x-axis = DTE (days to expiry), y-axis = ATM IV%
  Annotation markers on the x-axis for known upcoming events:
  - Earnings date (fetched from yfinance Ticker.calendar)
  - Next FOMC meeting date (from Phase 4 central bank calendar)
  These markers explain jumps or kinks in the term structure curve.


──────────────────────────────────────────────────────────────────────
7.3  Implied Volatility Smile / Skew
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  Plots IV against strike price (or moneyness) for a single expiry.
  The "smile" or "smirk" shape reveals how the market prices tail risk.
  Equity options typically show a downside skew (put IV > call IV at
  equivalent distance from ATM) because investors pay a premium to
  hedge downside. A steeper skew signals elevated fear of a crash.

HOW TO COMPUTE:
  For the selected expiry (from the expiry dropdown in 7.1):
  1. For each strike, use the call IV if the strike > current price
     (OTM calls), and the put IV if the strike < current price
     (OTM puts). For ATM strikes use both and average.
  2. Convert strikes to moneyness: moneyness = strike / current_price
     So ATM = 1.0, OTM calls > 1.0, OTM puts < 1.0.
     This normalisation makes the skew chart comparable across
     different stock price levels and across different tickers.
  3. Plot IV (y-axis) vs moneyness (x-axis) as a smooth curve.
     A perfectly flat line would mean all strikes have the same IV —
     which never happens in practice. The real shape reveals market
     structure: the left tail (moneyness < 0.90) shows put skew
     (crash insurance premium), the right tail shows call skew
     (lottery/upside speculation premium).

OUTPUT:
  Line chart: x-axis = moneyness (0.70 to 1.30), y-axis = IV%
  Expiry selector synced with the chain table expiry selector (7.1)
  so changing expiry updates both the chain and the smile simultaneously.
  A vertical dashed line at x=1.0 marks the ATM point.
  Annotate the chart with the put/call skew metric:
  Skew = IV(0.90 moneyness put) − IV(1.10 moneyness call)
  This single number captures the asymmetry. Display prominently as
  a KPI card alongside the chart: high positive skew = fear-driven,
  low or negative = greed-driven/speculative market.


──────────────────────────────────────────────────────────────────────
7.4  Key Options Analytics KPI Cards
──────────────────────────────────────────────────────────────────────
WHAT TO BUILD:
  A row of KPI cards at the top of the Options tab providing a quick
  summary of the most important options-derived insights, before the
  user dives into the detailed charts and chain.

CARDS TO INCLUDE:

  Implied Volatility (30-Day ATM):
    The ATM IV interpolated to exactly 30 days to expiry, regardless
    of which expiries are available. This is the standard "the IV"
    figure referenced by options traders. Compute by linear
    interpolation between the two expiries bracketing 30 DTE.
    Label: "IV30" or "30D ATM IV"

  IV Rank (IVR):
    Where the current IV30 stands within its own 1-year range.
    IVR = (current_IV − min_IV_52w) / (max_IV_52w − min_IV_52w) × 100
    A score of 0% means IV is at a 52-week low (historically cheap options),
    100% means IV is at a 52-week high (historically expensive options).
    Compute by fetching historical IV from the options chain snapshots —
    since yfinance does not provide historical IV directly, approximate
    it using the VIX-relative approach: fetch ^VIX history and compute
    the stock's beta-adjusted VIX as a proxy for historical IV, then
    compute IVR against that series.
    Display as a progress bar from 0 to 100 with colour zones:
    0–25 (green/cheap), 25–75 (neutral), 75–100 (red/expensive).

  IV Percentile (IVP):
    The percentage of days in the past 252 trading days where IV was
    LOWER than today's IV. Unlike IVR (which only uses min/max),
    IVP uses the full distribution. A more robust measure.
    Same approximation approach as IVR (beta-adjusted VIX history).

  Put/Call Ratio (Open Interest-based):
    Total open interest of all puts / total open interest of all calls
    across all expiries and all strikes for this ticker.
    > 1.0 = more put OI than call OI = bearish/hedging sentiment
    < 0.7 = more call OI than put OI = bullish/speculative sentiment
    Computed from the aggregated option_chain data across all expiries
    fetched from yfinance.

  Max Pain:
    The strike price at which the total dollar value of expiring options
    (both calls and puts) is minimised for the option buyers — or
    equivalently, maximised for the option writers (market makers).
    Theory holds that underlying prices tend to gravitate toward max pain
    at expiration due to market maker hedging activity.
    Computation for the nearest expiry: for each strike, calculate the
    total loss to option holders if price expired at that strike. The
    strike with minimum total buyer loss is max pain.
    Display as: "Max Pain: $XXX.XX (current price: $XXX.XX)"

  Implied Move (Earnings):
    For tickers with an earnings date in the options chain, compute the
    expected move implied by the options market:
    Implied Move % ≈ (ATM Call Price + ATM Put Price) / Current Stock Price
    This is the straddle price as a percentage of spot. It represents
    the options market's estimate of the magnitude of the earnings move
    (in either direction). Extremely useful for event traders.
    Only display this card when an earnings date is within 60 days.


──────────────────────────────────────────────────────────────────────
7.5  Options Tab Layout
──────────────────────────────────────────────────────────────────────
ROUTE: New tab "Options" added to the Markets page tab bar, between
"Ratios" and "Portfolio" (or as the last tab before Screener).

PAGE LAYOUT (top to bottom):

  [1] KPI Cards Row (7.4)
      IV30 | IVR | IVP | Put/Call Ratio | Max Pain | Implied Move
      Laid out as a 6-card horizontal row. On mobile: 2×3 grid.

  [2] Two-Column Chart Row
      Left:  IV Term Structure chart (7.2) — expiry selector above it
      Right: IV Smile / Skew chart (7.3) — synced expiry selector

  [3] Options Chain Table (7.1)
      Full width. Expiry selector at the top of this section.
      "Show OTM only" toggle on the right of the expiry selector.

  [4] Open Interest by Strike (Bar Chart)
      Horizontal bar chart showing open interest for each strike:
      calls OI as green bars extending right, puts OI as red bars
      extending left, strike prices on the y-axis. This "OI profile"
      chart visually shows where market participants are concentrated
      and where the max pain strike lies (annotated with a dashed line).
      Data: aggregate OI across all expiries for each strike, or filter
      to the nearest expiry (toggle). Sourced from yfinance chain data.

NOTE ON DATA FRESHNESS:
  yfinance options data is delayed ~15 minutes for most tickers.
  This is acceptable for the analytics use case (not for live trading).
  Clearly label all options data with "Data delayed ~15min" in the
  tab header.

FILES:
  backend/routes/options.py               (GET /api/options?t=AAPL)
  backend/services/options_analytics.py  (IV term structure, smile, max
                                          pain, IV rank, implied move)
  frontend/app/markets/tabs/Options.tsx
  frontend/components/options/OptionsChain.tsx
  frontend/components/options/IVTermStructure.tsx
  frontend/components/options/IVSmile.tsx
  frontend/components/options/OIProfile.tsx
  frontend/components/options/OptionsKPICards.tsx


═══════════════════════════════════════════════════════════════════════
PHASE 8 — MACRO EXPANSION (Commodities, Global Indicators, Leading
           Indicators)
Expand the existing Macro tab beyond US/Germany/Japan into a full
global macro dashboard covering commodities, energy, metals, global
economic cycle indicators, and central bank policy tracking.
═══════════════════════════════════════════════════════════════════════

──────────────────────────────────────────────────────────────────────
8.1  Commodities Dashboard
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  A dedicated commodities section on the Macro tab (or as a standalone
  sub-tab) showing live prices, charts, and macro context for the most
  important global commodities. Commodities are fundamental macro
  indicators — oil prices drive inflation, gold signals risk aversion,
  copper is called "Dr. Copper" for its GDP-predictive properties.

ALL COMMODITIES AVAILABLE FREE VIA YFINANCE (continuous futures):

  Energy:
    WTI Crude Oil      → CL=F    Brent Crude       → BZ=F
    Natural Gas        → NG=F    Gasoline (RBOB)   → RB=F
    Heating Oil        → HO=F

  Metals (Precious):
    Gold               → GC=F    Silver            → SI=F
    Platinum           → PL=F    Palladium         → PA=F

  Metals (Industrial):
    Copper             → HG=F    Aluminium         → ALI=F

  Agriculture:
    Corn               → ZC=F    Wheat             → ZW=F
    Soybeans           → ZS=F    Coffee            → KC=F
    Cocoa              → CC=F    Sugar             → SB=F
    Cotton             → CT=F    Lean Hogs         → HE=F
    Live Cattle        → LE=F    Orange Juice      → OJ=F

  Other:
    Lumber             → LBS=F   Oat               → ZO=F

DATA TO DISPLAY PER COMMODITY:
  - Current price (with appropriate unit: $/barrel, $/oz, $/bushel etc.)
  - Daily change $ and %
  - Weekly and monthly change %
  - YTD change %
  - 1-year chart (daily closes)
  - A brief macro context tooltip explaining why this commodity matters
    (e.g. "Copper is a leading indicator for global industrial activity
    and often leads GDP by 3–6 months")

SPECIAL MACRO RELATIONSHIPS TO VISUALISE:
  Dr. Copper vs Global GDP:
    Overlay HG=F (copper price) with World Bank global GDP growth on the
    same dual-axis chart. Source: World Bank API indicator NY.GDP.MKTP.KD.ZG.
    This is one of the most powerful macro visualisations and very rare
    in free tools.

  Gold/Oil Ratio:
    Compute GC=F / CL=F. A rising ratio signals flight to safety and
    oil weakness (recessionary). Plot as a time series with recession
    shading using FRED series USREC (US recession indicator, binary).

  Commodity Price Index (Axiom Composite):
    Compute an equal-weighted composite of a basket of key commodities
    (CL=F, GC=F, HG=F, ZC=F, ZW=F) normalised to 100 at a base date.
    Plot as a single "Axiom Commodity Index" line alongside CPI inflation
    to show the lead-lag relationship.

DATA SOURCE:
  All commodity prices: yfinance (continuous futures tickers above).
  World Bank global GDP: World Bank Indicators API, free, no key required.
  Endpoint: https://api.worldbank.org/v2/country/WLD/indicator/
            NY.GDP.MKTP.KD.ZG?format=json&per_page=30
  FRED USREC: Recession indicator series for shading charts.


──────────────────────────────────────────────────────────────────────
8.2  Global Macro Indicators Expansion
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  Expand the existing multi-country GDP/CPI/Unemployment comparison
  beyond the current US/Germany/Japan to include more countries and
  more indicator types. Add IMF forward projections alongside historical
  actuals to show where the global economy is heading.

ADDITIONAL COUNTRIES TO ADD:
  Current coverage appears to be US, Germany, Japan. Expand to:
  United Kingdom, France, Canada, Australia, China, India, Brazil,
  South Korea, Netherlands, Spain, Italy (all G20 + Eurozone core).

ADDITIONAL INDICATORS TO ADD BEYOND GDP/CPI/UNEMPLOYMENT:

  Current Account Balance (% of GDP):
    Measures a country's trade position. Persistent deficits signal
    external vulnerability. Source: World Bank indicator BN.CAB.XOKA.GD.ZS
    or OECD.Stat "Balance of Payments" dataset.

  Government Debt (% of GDP):
    Source: IMF WEO database (free, downloadable as Excel/CSV twice/year).
    Direct URL for the latest WEO data:
    https://www.imf.org/en/Publications/WEO/weo-database/2026/April
    The IMF WEO covers 190+ countries with 5-year forward projections for
    GDP growth, inflation, unemployment, current account, and government
    debt. Parse the Excel file and cache the data locally. Update twice
    per year when IMF publishes (April and October).

  PMI (Purchasing Managers' Index):
    The single most timely leading indicator for economic activity.
    Published monthly. Values > 50 = expansion, < 50 = contraction.
    Covers Manufacturing PMI and Services PMI separately.
    Free source: Some PMI data is available via FRED:
      US Manufacturing PMI: FRED series MANEMP (ISM proxy) or
      search FRED for "PMI" to find ISM manufacturing/services series.
    For non-US PMIs (Eurozone, UK, Japan, China Caixin): these are
    proprietary S&P Global data and not available free. However, the
    headline flash PMI readings are press-released publicly each month
    and can be stored manually in the event_impact.json (Phase 4) as
    they are released. Display the last 12 months of historical
    readings from the manually maintained dataset.

  Yield Curve Spread (2Y10Y):
    Already partially implemented. Ensure the following spreads are
    computed and charted for each country:
    - 2Y10Y spread (most-watched recession predictor)
    - 3M10Y spread (Estrella-Mishkin model's preferred recession indicator)
    Source: FRED for US (T10Y2Y, T10Y3M series directly available).
    For Germany: compute from FRED IRLTLT01DEM156N (10Y Bund) minus
    the ECB's 2-year Bund yield (ECB Data Portal series IRS.M.DE.L.L40.CI.
    0000.EUR.N.Z, which provides Eurozone sovereign yields by maturity).

  Central Bank Policy Rate Tracker:
    A time-series chart showing the official policy rates for the major
    central banks over the past 5 years, all on one chart:
    - US Federal Funds Rate: FRED series FEDFUNDS
    - ECB Deposit Facility Rate: FRED series ECBDFR or ECB Data Portal
    - Bank of England Bank Rate: FRED series BOERUKM
    - Bank of Japan Policy Rate: FRED series IRSTCB01JPM156N
    - Reserve Bank of Australia: FRED series IRSTCB01AUM156N
    - Swiss National Bank: FRED series IRSTCB01CHM156N
    This chart is one of the most important macro charts a professional
    can look at — it shows the global rate cycle simultaneously.

OECD Composite Leading Indicator (CLI):
  The OECD publishes a monthly CLI for all major economies. A CLI above
  100 and rising = expansion; below 100 and falling = slowdown.
  Free endpoint via the OECD.Stat API (no key required):
  https://stats.oecd.org/SDMX-JSON/data/MEI_CLI/LOLITOAA.AUS+AUT+
  BEL+CAN+CHL+
    (continuing 8.2 — OECD Composite Leading Indicator)

  The full OECD.Stat API endpoint for CLI data (no API key required):
  https://stats.oecd.org/SDMX-JSON/data/MEI_CLI/LOLITOAA.AUS+AUT+
  BEL+CAN+CHL+COL+CZE+DNK+EST+FIN+FRA+DEU+GRC+HUN+ISL+IRL+ISR+ITA+
  JPN+KOR+LVA+LTU+LUX+MEX+NLD+NZL+NOR+POL+PRT+SVK+SVN+ESP+SWE+CHE+
  TUR+GBR+USA+EA19+G-7+OECD/M?startTime=2010-01&endTime=2026-06

  This returns monthly CLI values for all OECD member countries plus
  aggregates (Euro Area, G7, OECD Total) in SDMX-JSON format.
  The response must be parsed: navigate to
  response["dataSets"][0]["series"] then map the dimension positions
  back to country names and timestamps.

  Key countries to display: US, DE, FR, GB, JP, CN, KR, AU, CA, IT, ES
  Display as: a multi-line chart with each country as a distinct colour,
  with a horizontal reference line at 100 (the expansion/contraction
  boundary). A country whose CLI crosses below 100 from above is a
  leading signal of economic slowdown — annotate these crossovers.
  Add a country selector (multi-select checkboxes) so the user can
  isolate specific countries rather than showing all simultaneously.


──────────────────────────────────────────────────────────────────────
8.3  Macro Tab Redesign — Sub-Tab Navigation
──────────────────────────────────────────────────────────────────────
PROBLEM:
  The current Macro tab is a single long scrolling page. As more
  sections are added in Phase 8, it will become unmanageable. It needs
  to be reorganised into sub-tabs.

PROPOSED SUB-TAB STRUCTURE:
  [Overview]  [Rates & Yields]  [Inflation]  [Growth & Employment]
  [Commodities]  [FX]  [Leading Indicators]

  Overview (default):
    A curated "macro at a glance" view showing the most important single
    chart or KPI from each sub-tab. This is the macro equivalent of the
    Dashboard (Phase 2.4) — a fast morning briefing of the global
    macro environment. Include:
    - Regime Clock (Phase 0.3) — compact version
    - Global interest rate tracker (central bank policy rates)
    - Top 3 commodity movers today
    - OECD CLI for G7 aggregate
    - Yield curve spread (US 2Y10Y) with inversion flag
    - FX: DXY (US Dollar Index) and EUR/USD chart

  Rates & Yields:
    - Central bank policy rate tracker (all major CBs, 5-year history)
    - US yield curve (existing, already works well)
    - Yield curve spreads: 2Y10Y and 3M10Y for US, Germany, UK, Japan
    - Breakeven inflation rates: FRED series T5YIE (5-year), T10YIE (10-year)
      These are market-implied inflation expectations from TIPS spreads.
      One of the most important forward-looking macro indicators.
    - Real yields: FRED series DFII10 (10-Year TIPS yield)
      Real yield = nominal yield minus breakeven inflation. Rising real
      yields are historically bearish for equities and gold.

  Inflation:
    - Multi-country CPI (YoY%) comparison — existing, expand countries
    - CPI component breakdown for US: FRED provides sub-series for
      Core CPI (CPILFESL), Shelter CPI (CUSR0000SAH1),
      Food CPI (CPIUFDSL), Energy CPI (CPIENGSL)
      Show as a stacked bar or grouped bar chart to illustrate which
      components are driving headline inflation.
    - PPI (Producer Price Index) vs CPI: FRED series PPIACO
      PPI leads CPI by 2–6 months. Plotting both shows whether
      pipeline inflation pressure is building or easing.
    - Inflation Heatmap (existing) — keep and expand to more countries
    - Breakeven inflation rates (5Y and 10Y, moved from Rates tab)

  Growth & Employment:
    - Multi-country GDP (existing, expand countries and add IMF forecasts)
    - PMI multi-country chart (from Phase 8.2)
    - Unemployment rate comparison (existing, expand countries)
    - JOLTS Job Openings (US): FRED series JTSJOL — leading employment
      indicator, peaks before unemployment rises
    - Initial Jobless Claims (US): FRED series ICSA — weekly leading
      indicator, very timely
    - Consumer Confidence: US Conference Board (FRED series CSCICP03USM665S),
      EU Consumer Confidence (Eurostat series ei_bsco_m)
    - Industrial Production Index: FRED series INDPRO (US),
      Eurostat series sts_inpr_m (EU industrial production by country)

  Commodities:
    Full commodities dashboard from Phase 8.1. All commodity prices,
    the Dr. Copper chart, Gold/Oil ratio, and the Axiom Commodity Index.

  FX:
    Full FX rates panel from Phase 0.2 (bug fix, elevated to its own
    sub-tab). Add:
    - US Dollar Index (DXY): yfinance ticker DX-Y.NYB or ^DXY
      The DXY is a trade-weighted index of USD vs a basket of 6
      currencies. It is the most important macro FX indicator. Plot
      as a 2-year chart with annotations for FOMC decisions.
    - Currency Heatmap: a grid where rows = base currencies and
      columns = quote currencies, cells showing the 1D change % of
      each cross. Highlights at a glance which currency is strengthening
      or weakening across the board.
    - Emerging Market FX: USDMXN, USDBRL, USDINR, USDKRW, USDCNY —
      already in the FX rates grid but emphasise these as a group with
      an "EM FX" sub-section. EM currency weakness is often an early
      signal of global risk-off conditions.

  Leading Indicators:
    - OECD CLI multi-country chart (Phase 8.2)
    - US Conference Board Leading Economic Index components: FRED
      provides many of the 10 sub-components individually (yield curve,
      building permits PERMIT, jobless claims ICSA, S&P 500 performance,
      ISM new orders, consumer expectations).
    - Yield curve inversion tracker: a historical chart showing the
      US 2Y10Y spread going back to 1980 with recession periods shaded
      using FRED series USREC. Visually demonstrates the yield curve's
      track record as a recession predictor.
    - Global Recession Probability: compute a simplified logit-based
      recession probability model using the Estrella-Mishkin (1998)
      methodology, which takes only the 3M10Y yield spread as input.
      FRED provides the pre-computed version as series RECPROUSM156N
      (probability of US recession 12 months ahead). Plot as a
      percentage line chart with a 50% threshold line.

FILES FOR PHASE 8:
  backend/routes/macro.py               (expand existing with new endpoints)
  backend/services/commodities.py       (commodity price fetching + ratios)
  backend/services/global_macro.py      (World Bank, IMF WEO, OECD CLI)
  backend/services/rates_inflation.py   (breakeven, real yields, PPI, TIPS)
  backend/data/imf_weo_cache.json       (IMF WEO data, refreshed 2x/year)
  backend/data/cb_meetings.json         (already created in Phase 4)
  frontend/app/macro/page.tsx           (add sub-tab navigation)
  frontend/app/macro/tabs/Overview.tsx
  frontend/app/macro/tabs/RatesYields.tsx
  frontend/app/macro/tabs/Inflation.tsx
  frontend/app/macro/tabs/GrowthEmployment.tsx
  frontend/app/macro/tabs/Commodities.tsx
  frontend/app/macro/tabs/FX.tsx
  frontend/app/macro/tabs/LeadingIndicators.tsx
  frontend/components/macro/CentralBankRateChart.tsx
  frontend/components/macro/BreakevenInflationChart.tsx
  frontend/components/macro/CurrencyHeatmap.tsx
  frontend/components/macro/DXYChart.tsx
  frontend/components/macro/OECDCliChart.tsx
  frontend/components/macro/RecessionProbabilityChart.tsx
  frontend/components/macro/CommodityCard.tsx
  frontend/components/macro/CPIComponentBreakdown.tsx


═══════════════════════════════════════════════════════════════════════
PHASE 9 — SNOWFLAKE COMPOSITE SCORE
A proprietary multi-axis rating system that scores each stock across
5 fundamental dimensions, displayed as a pentagon radar chart. Directly
inspired by SimplyWallSt's Snowflake score — which is their most
recognisable and sticky UI element — built here entirely from free data.
═══════════════════════════════════════════════════════════════════════

──────────────────────────────────────────────────────────────────────
9.1  The Five Axes
──────────────────────────────────────────────────────────────────────
Each axis scored 0–10 based on a composite of sub-metrics. The score
for each axis is a weighted average of its sub-metric z-scores,
normalised against the stock's sector peers. This means a score of 7
means the stock ranks better than ~84% of its sector on that dimension
(approximately 1 standard deviation above mean), not an absolute value.

AXIS 1 — VALUE (0–10)
  Measures how cheaply the stock is priced relative to fundamentals.
  Higher score = more attractively valued.
  Sub-metrics (sourced from yfinance Ticker.info):
  - P/E vs sector median: score higher if P/E < sector median
  - P/B ratio: score higher if P/B < 3.0 (sector-adjusted)
  - EV/EBITDA vs sector median: score higher if below median
  - FCF Yield: score higher if FCF/Market Cap is higher
  - PEG ratio: score higher if PEG < 1.0
  - Price vs 52-week high: score higher if further below 52W high
    (contrarian value signal)
  Weighting: P/E (30%), EV/EBITDA (25%), FCF Yield (20%),
             P/B (15%), PEG (10%)

AXIS 2 — FUTURE GROWTH (0–10)
  Measures forward-looking growth expectations and potential.
  Higher score = stronger expected growth.
  Sub-metrics:
  - EPS growth estimate (5-year): yfinance Ticker.info["earningsGrowth"]
  - Revenue growth (TTM YoY): Ticker.financials Revenue comparison
  - Analyst forward EPS revisions: whether forward EPS estimates have
    been revised up (positive) or down (negative) — use Ticker.info
    ["earningsQuarterlyGrowth"] as a proxy for earnings momentum
  - PEG ratio (growth-adjusted): lower PEG at high growth = value
  - R&D spending as % of revenue (proxy for innovation investment):
    Ticker.financials "Research Development" / Revenue
  Weighting: EPS growth estimate (35%), Revenue growth (30%),
             Earnings momentum (20%), R&D intensity (15%)

AXIS 3 — PAST PERFORMANCE (0–10)
  Measures how well the company has historically delivered returns.
  Higher score = stronger historical track record.
  Sub-metrics:
  - 3-year revenue CAGR: compound annual growth in revenue over 3 years
    from Ticker.financials
  - 3-year EPS CAGR: compound annual growth in EPS over 3 years
  - Return on Equity (ROE) average over 3 years: Ticker.info["returnOnEquity"]
    for current year; use Ticker.financials Net Income / Equity for prior years
  - Return on Assets (ROA): Ticker.info["returnOnAssets"]
  - Gross margin trend: is gross margin stable or improving over 3 years
  - 1-year stock price performance vs sector ETF performance
    (price alpha relative to sector): from Phase 2.1 price cache
  Weighting: 3Y Revenue CAGR (25%), ROE (25%), 3Y EPS CAGR (20%),
             Gross Margin trend (15%), Price vs Sector (15%)

AXIS 4 — FINANCIAL HEALTH (0–10)
  Measures balance sheet strength and financial stability.
  Higher score = stronger financial position, lower bankruptcy risk.
  Sub-metrics:
  - Altman Z-Score: already computed in the existing Ratios tab.
    Score of 10 if Z > 3.0 (safe zone), scale down linearly to 0
    if Z < 1.8 (distress zone).
  - Debt/Equity ratio: lower = better (sector-adjusted)
  - Current Ratio: higher = better (above 1.5 is healthy)
  - Interest Coverage Ratio: EBIT / Interest Expense from
    Ticker.financials. Higher = better. < 1.5 is a red flag.
  - Free Cash Flow Positive: binary — FCF > 0 gets a boost
  - Cash vs Total Debt: net cash position (Ticker.info["totalCash"]
    minus Ticker.info["totalDebt"]). Positive net cash scores higher.
  Weighting: Altman Z-Score (30%), Interest Coverage (25%),
             Current Ratio (20%), Net Cash Position (15%),
             Debt/Equity (10%)

AXIS 5 — DIVIDEND (0–10)
  Measures dividend attractiveness and sustainability.
  Higher score = more attractive and sustainable income.
  Note: Non-dividend-paying stocks score 0 on this axis by design —
  the axis is transparent about what it measures. This axis should be
  weighted lower or excluded in the composite for growth stocks.
  Sub-metrics (only apply if dividendRate > 0):
  - Dividend Yield vs sector median: higher yield vs peers scores better
  - Payout Ratio: lower is more sustainable. Score falls sharply above 80%
  - 5-year Dividend Growth CAGR: from Ticker.dividends history
  - Dividend consistency: number of consecutive years with no cut or
    suspension from historical Ticker.dividends series
  - FCF Coverage Ratio: FCF / (Dividends Paid) — how well FCF covers
    the dividend. > 1.5× is safe, < 1.0× is dangerous.
  Weighting: Yield vs Peers (25%), Payout Ratio (25%), Growth (25%),
             Consistency (15%), FCF Coverage (10%)
  If dividendRate = 0, all sub-metrics score 0 and this axis = 0/10.


──────────────────────────────────────────────────────────────────────
9.2  Sector Normalisation
──────────────────────────────────────────────────────────────────────
WHY IT MATTERS:
  Scoring a utility company's growth on an absolute scale would always
  rank it near 0 because utilities inherently grow slowly. Instead,
  each sub-metric score is computed relative to the stock's own sector
  peers,so a utility can score 8/10 on Future Growth by being an exceptional
  grower within the utilities sector, even if its absolute growth rate
  (3–5% annually) would score near zero on a technology-calibrated
  absolute scale. This makes the Snowflake score meaningful and fair
  across all sectors.

HOW TO IMPLEMENT SECTOR NORMALISATION:
  For each sub-metric within each axis:
  1. Compute the raw metric value for the target stock (e.g. P/E = 22×)
  2. Collect the same metric for all stocks in the same sector from the
     Phase 5 universe cache (e.g. all Technology sector stocks' P/E ratios)
  3. Compute the percentile rank of the target stock's value within that
     distribution. For metrics where lower = better (P/E, Debt/Equity),
     invert the percentile: percentile_score = 100 − raw_percentile.
     For metrics where higher = better (ROE, FCF Yield), use raw percentile.
  4. Map the 0–100 percentile to a 0–10 score (divide by 10).
  5. Weight and sum the sub-metric scores to produce the axis score.

  This requires the screener universe cache (Phase 5.1) to be available
  when computing Snowflake scores, since it provides the sector peer
  distributions. The two systems are therefore tightly linked — Phase 5
  must be complete before Phase 9 can work correctly.

  For stocks in thin sectors (fewer than 10 peers in the dataset), fall
  back to industry-level normalisation. If industry also has fewer than
  10 peers, fall back to market-wide normalisation with a warning label:
  "Score based on market-wide comparison (insufficient sector peers)."


──────────────────────────────────────────────────────────────────────
9.3  Snowflake Radar Chart Component
──────────────────────────────────────────────────────────────────────
WHAT TO BUILD:
  A filled pentagon radar chart with 5 axes (Value, Growth, Past
  Performance, Health, Dividend), each scaled 0–10. The filled area
  shows the stock's profile. For multi-ticker comparisons, overlay
  multiple semi-transparent filled shapes in different colours.

VISUAL DESIGN:
  - Pentagon shape (5 equal axes at 72° intervals)
  - Concentric grid rings at 2, 4, 6, 8, 10
  - Each axis labelled at its tip with the axis name and score:
    e.g. "VALUE\n6.2"
  - The filled polygon coloured with the Axiom Finance brand colour
    at 60% opacity so the grid is visible through it
  - For comparison mode (2 tickers): two differently coloured polygons
    overlaid with 50% opacity each
  - Axis score numbers displayed at each vertex of the polygon
  - A thin stroke outline on the polygon edge for crispness

RENDERING LIBRARY:
  Use recharts RadarChart component — it handles the pentagon layout,
  grid, and multiple data series natively and requires minimal custom
  SVG work. It accepts data in the form:
  [{ axis: "Value", score: 6.2 }, { axis: "Growth", score: 8.1 }, ...]

PLACEMENT IN THE APP:
  Primary placement: Overview tab of the Markets page (a new "Snapshot"
  section alongside the price chart for the first selected ticker).
  Secondary placement: a compact version in each screener result row
  when in "Charts" view mode (Phase 5.6) — rendered as a tiny 60×60px
  radar thumbnail.
  Also shown in the Valuation tab alongside the Axiom Fair Value
  composite (Phase 1.9) to give context beyond pure price-based valuation.

INTERACTIVITY:
  Hovering over any axis on the radar chart shows a tooltip explaining
  what that axis measures and listing the top 3 sub-metrics contributing
  to that score (with their individual values). This makes the score
  transparent and educational — users learn what each axis means by
  exploring it, rather than needing to read documentation.
  Clicking an axis navigates to the relevant tab (e.g. clicking
  "Health" navigates to the Ratios tab; clicking "Value" navigates
  to the Valuation tab).


──────────────────────────────────────────────────────────────────────
9.4  Snowflake Score on the Overview Tab
──────────────────────────────────────────────────────────────────────
WHAT TO BUILD:
  Add a "Snapshot" section to the Markets Overview tab positioned to
  the right of the main price chart. This section contains:

  1. Snowflake radar chart (Phase 9.3)
  2. A row of 5 score badges below the radar:
     [Value 6.2] [Growth 8.1] [Past 7.4] [Health 5.8] [Dividend 0.0]
     Each badge coloured: 0–3 red, 4–6 yellow, 7–8 light green, 9–10 green
  3. A one-line automated verdict generated from the scores:
     Examples:
     - "Strong growth profile with solid financial health, but
        expensive on valuation metrics relative to sector peers."
     - "Deep value play with robust dividend history, but growth
        expectations are below sector average."
     - "Exceptional past performance and strong health, dividend not
        applicable (no dividend paid)."
     This verdict is generated by a simple rules-based template system
     on the backend — not AI. The template selects a sentence fragment
     based on which axes are highest and lowest.

  4. A "Rewards & Risks" section showing:
     Top 3 positives (from highest-scoring sub-metrics across all axes)
     Top 3 risks (from lowest-scoring sub-metrics across all axes)
     Each presented as a bullet point with a green ✓ or red ⚠ icon.
     Example positives:
       ✓ P/E ratio (22×) is below the Technology sector median (28×)
       ✓ ROE of 38% is in the top quartile of the sector
       ✓ 5-year dividend CAGR of 9.2% shows consistent income growth
     Example risks:
       ⚠ Payout ratio of 89% is above the sustainable 80% threshold
       ⚠ Debt/Equity of 2.1× is above the sector median of 0.9×
       ⚠ EPS growth estimate (3%) is below the sector median (8%)

FILES FOR PHASE 9:
  backend/services/snowflake_engine.py      (all 5 axis computations,
                                            sector normalisation, verdict
                                            template generation)
  backend/routes/overview.py               (add snowflake endpoint)
  frontend/components/snowflake/SnowflakeRadar.tsx
  frontend/components/snowflake/ScoreBadges.tsx
  frontend/components/snowflake/VerdictText.tsx
  frontend/components/snowflake/RewardsRisks.tsx
  frontend/app/markets/tabs/Overview.tsx   (add Snapshot section)


═══════════════════════════════════════════════════════════════════════
PHASE 10 — SECTOR PERFORMANCE CHARTS
Replace or enhance the existing Sectors tab heatmap with a richer,
multi-period sector performance view. Directly inspired by Finviz's
Groups page, which shows 1D, 1W, and 1M performance simultaneously as
horizontal bar charts — a much more information-dense view than a
heatmap for reading the actual magnitude of moves.
═══════════════════════════════════════════════════════════════════════

──────────────────────────────────────────────────────────────────────
10.1  Sector Performance Bar Charts
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  Displays all 11 GICS sectors as horizontal bar charts with sector
  names on the y-axis and return % on the x-axis. Multiple time periods
  are stacked vertically on the same page (1D, 1W, 1M, 3M, YTD, 1Y)
  so the user can see sector rotation patterns across timeframes
  simultaneously without switching tabs or clicking through filters.

DATA SOURCE:
  The 11 SPDR sector ETFs are the standard instruments used to track
  sector performance, all available free via yfinance:
  XLF  Financial           XLK  Technology
  XLE  Energy              XLV  Healthcare
  XLI  Industrials         XLY  Consumer Discretionary
  XLP  Consumer Staples    XLB  Basic Materials
  XLRE Real Estate         XLC  Communication Services
  XLU  Utilities

  Fetch 2 years of daily history for all 11 tickers simultaneously
  using a single yf.download() call. Compute returns for each time
  period (1D, 1W, 1M, 3M, YTD, 1Y) from this dataset. Cache the
  result and refresh daily.

  Additionally compute the same for S&P 500 benchmark (^GSPC) and
  show it as a reference line on each bar chart (a vertical dashed
  line at the S&P 500 return for that period) so users can instantly
  see which sectors are outperforming and underperforming the index.

CHART LAYOUT (Finviz Groups "Performance Chart" mode):
  Six stacked horizontal bar charts on the page, one per time period:
  1D Performance | 1W Performance | 1M Performance
  3M Performance | YTD Performance | 1Y Performance

  Each chart:
  - Y-axis: sector names sorted by return (best at top, worst at bottom)
    The sorting is independent per chart — 1D leaders may not be 1Y
    leaders. This makes it easy to spot momentum vs mean reversion.
  - X-axis: return % (symmetric around 0, with dynamic scale)
  - Bars: green for positive, red for negative. The bars extend left
    or right from the 0% centre line.
  - Dashed vertical reference line at the S&P 500 return for that period
  - Value labels at the end of each bar showing the exact % return
  - ETF ticker shown in parentheses after sector name for transparency


──────────────────────────────────────────────────────────────────────
10.2  Sector Fundamentals Table
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  A tabular view (inspired by Finviz Groups "Overview" and "Valuation"
  modes) showing fundamental aggregates per sector. Gives context for
  whether sector performance is justified by fundamentals or is pure
  momentum/sentiment.

TABS WITHIN THE SECTOR TABLE:
  [Overview] [Valuation] [Performance] [Volatility]

  Overview:
    Sector | # Stocks | Mkt Cap ($T) | Avg P/E | Avg Div Yield |
    1D Chg% | 1W Chg% | 1M Chg%

  Valuation:
    Sector | Avg P/E | Avg P/B | Avg EV/EBITDA | Avg P/S |
    Avg FCF Yield | Median Div Yield

  Performance:
    Sector | 1D% | 1W% | 1M% | 3M% | YTD% | 1Y% | vs S&P 500 (1Y)

  Volatility:
    Sector | Avg Beta | 20D Volatility (annualised) | Max Drawdown (1Y) |
    Sharpe Ratio (1Y, using sector ETF return vs DGS10 risk-free rate)

DATA SOURCE:
  - Sector ETF prices for all performance and volatility metrics
    (yfinance, same dataset as 10.1)
  - Sector fundamental aggregates: compute by taking the median (not
    mean — median is more robust to outliers) of each metric across all
    stocks in the Phase 5 universe cache belonging to that sector.
  - Market cap by sector: sum of all constituent market caps from
    yfinance Ticker.info["marketCap"] per sector.


──────────────────────────────────────────────────────────────────────
10.3  Industry Drill-Down
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  When a user clicks on any sector in the performance bar chart or
  fundamentals table, the view drills down to show the same charts and
  table at the industry level within that sector.

  For example, clicking "Technology" shows:
  - Semiconductors, Software — Application, Software — Infrastructure,
    Hardware, IT Services, Electronic Components etc.

  Each industry is represented by the top-3 stocks by market cap in
  that industry (their average return approximates the industry return).
  This is a clean and fully free approach since it uses only yfinance
  constituent data from Phase 5's FinanceDatabase sector classification.

  A breadcrumb at the top of the page shows the drill-down path:
  [All Sectors] → [Technology] → [Semiconductors]
  Back navigation returns to the previous level.

  At the deepest level (individual stocks within an industry), the
  view switches to showing the screener results table (Phase 5.5)
  filtered to that specific industry — a seamless handoff between
  the two features.


──────────────────────────────────────────────────────────────────────
10.4  Sector Rotation Clock (Visual)
──────────────────────────────────────────────────────────────────────
WHAT IT DOES:
  A visual representation of where we are in the economic cycle based
  on which sectors are leading and lagging. The sector rotation model
  (from Sam Stovall's work at CFRA) maps sectors to phases of the
  economic cycle:

  Early Cycle (recovery begins):     Financials, Consumer Discretionary
  Mid Cycle (expansion):             Technology, Industrials, Materials
  Late Cycle (slowing growth):       Energy, Consumer Staples, Healthcare
  Recession:                         Utilities, Consumer Staples, Healthcare

IMPLEMENTATION:
  Represent as a circular clock diagram with 4 quadrants (Early / Mid /
  Late / Recession). Each sector's ETF is placed in its canonical
  quadrant. A colour and size indication on each sector label shows
  its recent relative performance vs the S&P 500 (green = outperforming
  = suggests that phase is active; grey = underperforming).

  The "implied phase" is computed by checking which group of sectors
  is most broadly outperforming over the past 3 months. This gives a
  data-driven (though approximate) reading of where the market is pricing
  the cycle. Overlay this with the Regime Clock from Phase 0.3 (GDP/CPI
  quadrant) for cross-validation.

  This is a visual/informational feature rather than a predictive model —
  label it clearly as "Sector Rotation Model (Sam Stovall framework)"
  with a tooltip explaining the methodology and its limitations.

DATA SOURCE:
  Sector ETF 3-month returns vs S&P 500 benchmark (from existing data).
  No additional data required.

FILES FOR PHASE 10:
  backend/routes/sectors.py               (expand existing sector endpoint)
  backend/services/sector_analytics.py   (performance aggregation, industry
                                          drill-down, rotation clock signal)
  frontend/app/markets/tabs/Sectors.tsx  (full redesign of existing tab)
  frontend/components/sectors/SectorBarChart.tsx
  frontend/components/sectors/SectorFundamentalsTable.tsx
  frontend/components/sectors/IndustryDrillDown.tsx
  frontend/components/sectors/SectorRotationClock.tsx


═══════════════════════════════════════════════════════════════════════
APPENDIX A — COMPLETE DATA SOURCE REFERENCE
All data sources used across all phases. Every source is free.
No paid APIs required anywhere in this plan.
═══════════════════════════════════════════════════════════════════════

──────────────────────────────────────────────────────────────────────
A.1  yfinance (Python library)
──────────────────────────────────────────────────────────────────────
Install: pip install yfinance
Cost: Free. Open source. No API key required.
Rate limits: Unofficial — enforce a 0.5s delay between individual
  Ticker() calls; use yf.download() for batch requests (much faster
  and more respectful of Yahoo Finance servers).
Documentation: https://ranaroussi.github.io/yfinance/

Used for:
  - Equities: OHLCV price history (all intervals from 1m to 3mo)
    yf.download(tickers, period, interval)
  - Fundamentals: P/E, P/B, EV/EBITDA, margins, ROE, ROA, beta,
    shares outstanding, market cap, book value, debt, cash
    yf.Ticker(t).info
  - Financial statements: Income Statement, Balance Sheet, Cash Flow
    yf.Ticker(t).financials / .balance_sheet / .cashflow
    Available annual and quarterly, TTM approximated from latest quarter
  - Dividends history: yf.Ticker(t).dividends (pandas Series)
  - Options chains: yf.Ticker(t).options (list of expiry dates)
    yf.Ticker(t).option_chain(expiry).calls / .puts
    Fields: strike, lastPrice, bid, ask, volume, openInterest,
    impliedVolatility, inTheMoney
  - Earnings calendar: yf.Ticker(t).calendar (next earnings date,
    EPS estimate, revenue estimate)
  - Sector data: yf.Sector(key).top_companies, .industries
  - Forex pairs: yf.download("EURUSD=X") — all Yahoo Finance FX tickers
    in format BASE+QUOTE+"=X"
  - Commodities (continuous futures): CL=F, GC=F, SI=F, HG=F, ZC=F etc.
  - Stock indices: ^GSPC, ^NDX, ^DJI, ^FTSE, ^GDAXI, ^N225, ^HSI etc.
  - VIX: ^VIX
  - US Dollar Index: DX-Y.NYB or ^DXY
  - Bond ETFs: TLT (20Y Treasuries), IEF (7-10Y), SHY (1-3Y),
    HYG (High Yield), LQD (Investment Grade)
  - 10Y government bond yields (yfinance fallback for non-FRED countries):
    IN10YT=RR, BR10YT=RR, CN10YT=RR, MX10YT=RR, SG10YT=RR etc.

Key data quality notes:
  - Ticker.info can occasionally return None for some fields — always
    implement safe .get() calls with sensible fallback defaults
  - Historical options data is NOT available via yfinance — only current
    snapshot. This limits IV Rank to the proxy approach described in 7.4.
  - Financial statement data may have a 1–2 quarter lag. Always display
    the "as of" date sourced from the data.
  - Batch downloads via yf.download() are significantly faster and more
    reliable than looping individual Ticker() calls. Always prefer batch.


──────────────────────────────────────────────────────────────────────
A.2  FRED — Federal Reserve Economic Data
──────────────────────────────────────────────────────────────────────
Provider: Federal Reserve Bank of St. Louis
Install: pip install fredapi
Cost: Free. Requires a free API key from fred.stlouisfed.org/docs/api/api_key.html
Documentation: https://fred.stlouisfed.org/docs/api/fred/

Key series used throughout the plan:

  INTEREST RATES & YIELDS:
    DGS10          10-Year Treasury Constant Maturity Rate (daily)
    DGS2           2-Year Treasury Constant Maturity Rate (daily)
    DGS5           5-Year Treasury Constant Maturity Rate (daily)
    DGS30          30-Year Treasury Constant Maturity Rate (daily)
    DGS1MO         1-Month Treasury Rate (daily)
    DGS3MO         3-Month Treasury Rate (daily)
    DGS6MO         6-Month Treasury Rate (daily)
    DGS1           1-Year Treasury Rate (daily)
    DGS7           7-Year Treasury Rate (daily)
    DGS20          20-Year Treasury Rate (daily)
    T10Y2Y         10-Year minus 2-Year Treasury Spread (daily, pre-computed)
    T10Y3M         10-Year minus 3-Month Treasury Spread (daily, pre-computed)
    FEDFUNDS       Federal Funds Effective Rate (monthly)
    DFEDTARU       Federal Funds Target Rate Upper Bound (daily)
    DFII10         10-Year TIPS Yield — Real Yield (daily)
    T10YIE         10-Year Breakeven Inflation Rate (daily)
    T5YIE          5-Year Breakeven Inflation Rate (daily)
    AAA            Moody's Seasoned Aaa Corporate Bond Yield (daily)
    BAA            Moody's Seasoned Baa Corporate Bond Yield (daily)
    BAMLH0A0HYM2   ICE BofA US High Yield OAS — Credit Spread (daily)
    BAMLEM4BRRHLCRPIOAS  EM Corporate Bond Spread (daily)

  INTERNATIONAL 10-YEAR GOVERNMENT BOND YIELDS (monthly):
    IRLTLT01DEM156N  Germany (Bund)
    IRLTLT01GBM156N  United Kingdom (Gilt)
    IRLTLT01JPM156N  Japan (JGB)
    IRLTLT01FRM156N  France (OAT)
    IRLTLT01CAM156N  Canada
    IRLTLT01AUM156N  Australia
    IRLTLT01NLM156N  Netherlands
    IRLTLT01ESM156N  Spain
    IRLTLT01ITM156N  Italy
    IRLTLT01KRM156N  South Korea
    IRLTLT01CHM156N  Switzerland
    IRLTLT01SEM156N  Sweden
    IRLTLT01USM156N  United States (monthly, use DGS10 daily instead)

  INTERNATIONAL CENTRAL BANK POLICY RATES:
    ECBDFR         ECB Deposit Facility Rate
    BOERUKM        Bank of England Bank Rate (monthly)
    IRSTCB01JPM156N  Bank of Japan Policy Rate (monthly)
    IRSTCB01AUM156N  Reserve Bank of Australia Cash Rate
    IRSTCB01CHM156N  Swiss National Bank Policy Rate

  INFLATION:
    CPIAUCSL       US CPI All Items (monthly, seasonally adjusted)
    CPILFESL       US Core CPI (ex food & energy, monthly)
    CPIUFDSL       US Food CPI (monthly)
    CPIENGSL       US Energy CPI (monthly)
    CUSR0000SAH1   US Shelter CPI (monthly)
    PCEPI          PCE Price Index (monthly)
    PCEPILFE       Core PCE (Fed's preferred inflation measure, monthly)
    PPIACO         Producer Price Index All Commodities (monthly)

  GDP & GROWTH:
    GDPC1          US Real GDP (quarterly, seasonally adjusted)
    GDPPOT         US Potential GDP (quarterly)
    A191RL1Q225SBEA  US Real GDP Growth Rate QoQ (quarterly)

  LABOUR MARKET:
    UNRATE         US Unemployment Rate (monthly)
    ICSA           Initial Jobless Claims (weekly — very timely)
    CCSA           Continued Jobless Claims (weekly)
    JTSJOL         JOLTS Job Openings (monthly)
    PAYEMS         Total Nonfarm Payrolls (monthly)
    LNS11300000    Labour Force Participation Rate (monthly)
    AHETPI         Average Hourly Earnings (monthly)

  MONEY SUPPLY & FINANCIAL CONDITIONS:
    M2SL           M2 Money Supply (monthly)
    M2V            M2 Velocity of Money (quarterly)
    WALCL          Federal Reserve Total Assets — Balance Sheet (weekly)

  CONSUMER & BUSINESS:
    UMCSENT        University of Michigan Consumer Sentiment (monthly)
    CSCICP03USM665S  OECD Consumer Confidence US (monthly, via FRED)
    RSAFS          Retail Sales (monthly)
    RRSFS          Real Retail Sales (monthly)
    INDPRO         Industrial Production Index (monthly)
    MCUMFN         Capacity Utilisation (monthly)
    PERMIT         Building Permits (monthly)
    HOUST          Housing Starts (monthly)

  MARKET / SENTIMENT:
    CBOE/PUTCALL   CBOE Equity Put/Call Ratio (if available via FRED)
    VIXCLS         CBOE VIX Closing Price (daily — same as ^VIX yfinance)
    USREC          US Recession Indicator (binary, monthly: 0 or 1)
    RECPROUSM156N  US Recession Probability 12-months ahead (monthly)
    SP500          S&P 500 monthly closing price (monthly — use ^GSPC
                   from yfinance for daily resolution)

API usage: fred.get_series("SERIES_ID") returns a pandas Series.
  fred.get_series("SERIES_ID", observation_start="2020-01-01") for
  date-filtered requests. All FRED data is public domain.


──────────────────────────────────────────────────────────────────────
A.3  Eurostat (European Statistical Office)
──────────────────────────────────────────────────────────────────────
Install: pip install eurostat
Cost: Free. No API key required.
Documentation: https://ec.europa.eu/eurostat/web/api-statistics

Key datasets used:
  namq_10_gdp      National Accounts GDP by expenditure, quarterly
                   Filter: geo=EA (Euro Area), DE, FR, IT, ES, NL etc.
                   na_item=B1GQ (GDP at market prices)
                   unit=CLV_PCH_PRE (chain-linked volume, % change)

  prc_hicp_manr    HICP (Harmonised CPI) annual rate of change, monthly
                   Filter: geo=EA, DE, FR etc.; coicop=CP00 (all items)

  une_rt_m         Unemployment rate, monthly
                   Filter: geo=EA, DE, FR etc.; sex=T (total); age=TOTAL

  sts_inpr_m       Industrial production index, monthly
                   Filter: geo=EU27_2020; nace_r2=B-D (mining + manufacturing)

  ei_bsco_m        Consumer confidence indicator, monthly
                   Filter: geo=EA, EU27_2020

  bop_eu6_q        Balance of Payments current account, quarterly
                   Filter: geo=EA; bop_item=CA

Usage pattern: eurostat.get_data_df("dataset_id") returns a pandas
  DataFrame. Filter columns by the geo, time period, and indicator
  codes needed. The eurostat Python library handles all SDMX parsing.


──────────────────────────────────────────────────────────────────────
A.4  World Bank Open Data API
──────────────────────────────────────────────────────────────────────
Install: pip install wbdata   (or use direct HTTP requests)
Cost: Free. No API key required.
Base URL: https://api.worldbank.org/v2/
Documentation: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392

Key indicators used:
  NY.GDP.MKTP.KD.ZG   GDP growth (annual %, constant prices)
  NY.GDP.PCAP.KD.ZG   GDP per capita growth (annual %)
  FP.CPI.TOTL.ZG      CPI inflation (annual %)
  SL.UEM.TOTL.ZS      Unemployment rate (% of labour force)
  BN.CAB.XOKA.GD.ZS   Current account balance (% of GDP)
  GC.DOD.TOTL.GD.ZS   Central government debt (% of GDP)
  NE.EXP.GNFS.ZS      Exports (% of GDP)
  NE.IMP.GNFS.ZS      Imports (% of GDP)
  NY.GDP.MKTP.CD      GDP (current US$) — for market-cap-to-GDP ratio

Country codes: Use ISO 3166-1 alpha-3 (USA, DEU, GBR, JPN, CHN,
  IND, BRA, KOR, AUS, CAN, FRA, ITA, ESP, NLD etc.)
World aggregate: "WLD"
Use wbdata.get_dataframe({indicator_id: "label"}, country=[list])
  to fetch a multi-country DataFrame directly.
Note: World Bank data is annual with a 1–2 year lag. Use for long-term
  historical context and trend analysis, not real-time monitoring.


──────────────────────────────────────────────────────────────────────
A.5  ECB Data Portal (European Central Bank)
──────────────────────────────────────────────────────────────────────
Cost: Free. No API key required.
Base URL: https://data-api.ecb.europa.eu/service/data/{flow}/{key}
Documentation: https://data.ecb.europa.eu/help/api/data

Key series used:
  ECB deposit facility rate:
    Flow: FM, Key: M.U2.EUR.4F.KR.DFR.LEV
    Returns monthly ECB deposit facility rate

  Euro Area sovereign bond yields by maturity:
    Flow: IRS, Key: M.{country}.L.L40.CI.0000.EUR.N.Z
    Replace {country} with DE, FR, IT, ES, NL etc.
    Returns government bond yields at various maturities needed for
    non-US yield curve construction

  ECB balance sheet (total assets):
    Flow: BSI, Key: M.U2.N.A.A20T.A.1.U2.2240.Z01.E

  Euro Area M3 money supply:
    Flow: BSI, Key: M.U2.Y.V.M30.X.1.U2.2300.Z01.E

The API returns data in SDMX-JSON format. Navigate:
  response["dataSets"][0]["series"]["0:0:0:..."]["observations"]
  to extract time series values. The dimension keys are mapped via
  response["structure"]["dimensions"]["series"] to get timestamps
  and series metadata.


──────────────────────────────────────────────────────────────────────
A.6  OECD.Stat API
──────────────────────────────────────────────────────────────────────
Cost: Free. No API key required.
Base URL: https://stats.oecd.org/SDMX-JSON/data/
Documentation: https://data.oecd.org/api/sdmx-json-documentation/

Key datasets used:
  MEI_CLI — Composite Leading Indicators:
    Sample endpoint for key countries:
    https://stats.oecd.org/SDMX-JSON/data/MEI_CLI/
    LOLITOAA.USA+GBR+DEU+FRA+JPN+KOR+AUS+CAN+ITA+ESP+
    NLD+CHN+IND+BRA+EA19+G-7+OECD/M?
    startTime=2010-01&endTime=2026-06&contentType=csv
    Use contentType=csv for simpler parsing than SDMX-JSON.
    The CSV format returns rows of (country, indicator, date, value).

  MEI — Main Economic Indicators:
    https://stats.oecd.org/SDMX-JSON/data/MEI/
    Used for: Japan GDP, Japan CPI, Japan industrial production,
    and other countries where FRED coverage is monthly-lagged.
    Key series codes:
      IRSTCB01.{CC}.ST.M  — Central bank policy rate, monthly
      IRLTLT01.{CC}.ST.M  — 10-year government bond yield, monthly
      PRINTO01.{CC}.ST.M  — Industrial production index, monthly
      NAEXKP01.{CC}.ST.Q  — GDP volume index, quarterly
      CPALTT01.{CC}.ST.M  — CPI, total, monthly

  Replace {CC} with OECD country code (USA, GBR, DEU, FRA, JPN etc.)

  Response parsing: request with contentType=csv for simplest parsing.
  If using SDMX-JSON, the structure is:
    response["dataSets"][0]["series"] contains all series keyed by
    dimension position strings. Map these positions to actual values
    using response["structure"]["dimensions"]["series"][i]["values"].


──────────────────────────────────────────────────────────────────────
A.7  IMF World Economic Outlook (WEO) Database
──────────────────────────────────────────────────────────────────────
Cost: Free. No API key required.
Update frequency: Twice per year — April and October releases.
Download URL pattern:
  https://www.imf.org/en/Publications/WEO/weo-database/{year}/{month}
  e.g. https://www.imf.org/en/Publications/WEO/weo-database/2026/April

The WEO database is distributed as a tab-delimited .xls or .xlsx file.
Download it programmatically using requests, then parse with pandas.
Cache locally in backend/data/imf_weo_cache.xlsx and refresh twice per
year via a cron job or manual trigger. Do not re-download on every
request — this is a large file (~5MB).

Key WEO series codes (column "WEO Subject Code" in the file):
  NGDP_RPCH      Real GDP growth (annual %, IMF projection)
  PCPIPCH        CPI inflation (end of period, annual %)
  LUR            Unemployment rate (% of labour force)
  BCA_NGDPD      Current account balance (% of GDP)
  GGXWDG_NGDP   General government gross debt (% of GDP)
  NID_NGDP       Total investment (% of GDP)
  NGSD_NGDP      Gross national savings (% of GDP)

Coverage: 190+ countries. Data from 1980 through 5-year forward
  projections (so currently 2026 data includes projections to 2031).
  This forward projection capability is the key differentiator vs other
  sources — it lets Axiom Finance show IMF forecasts alongside
  historical actuals on GDP and inflation charts.

Integration: Parse the WEO Excel into a pandas DataFrame at startup,
  filter for desired countries and series codes, store in memory or
  SQLite. Merge with World Bank/FRED historical actuals for a combined
  history + forecast chart.


──────────────────────────────────────────────────────────────────────
A.8  Finnhub (Free Tier)
──────────────────────────────────────────────────────────────────────
Install: pip install finnhub-python
Cost: Free tier — 60 API calls/minute, no credit card required.
  Requires a free API key from finnhub.io
Documentation: https://finnhub.io/docs/api

Used for (free tier only — no paid features used):
  Earnings Calendar:
    GET /calendar/earnings?from=YYYY-MM-DD&to=YYYY-MM-DD
    Returns: symbol, date, epsEstimate, epsActual, revenueEstimate,
    revenueActual, quarter. Free tier: 1 month of data per request.
    Use to supplement yfinance earnings dates with consensus estimates
    and actual results.

  IPO Calendar:
    GET /calendar/ipo?from=YYYY-MM-DD&to=YYYY-MM-DD
    Returns: symbol, name, date, priceRange, shares, market, status.
    The only free source of IPO calendar data in this stack.

  Economic Calendar:
    GET /calendar/economic
    Returns upcoming economic events with country, event name, impact,
    actual, previous, estimate. Covers major events internationally.
    Use to supplement FRED release dates with international events and
    consensus estimates.

  Company Basic Financials (limited):
    GET /stock/metric?symbol=AAPL&metric=all
    Returns many fundamental metrics in a single call. Use as a cross-
    check for yfinance fundamental data.

Rate limit management: Implement a token bucket or simple time.sleep()
  delay between calls. Cache all Finnhub responses with a TTL of 24
  hours to minimise API consumption. Never call Finnhub on every page
  load — always serve from cache.


──────────────────────────────────────────────────────────────────────
A.9  FinanceDatabase (Open Source Library)
──────────────────────────────────────────────────────────────────────
Install: pip install financedatabase
Cost: Free. Open source. No API key. No rate limits.
GitHub: https://github.com/JerBouma/FinanceDatabase
Documentation: https://www.jeroenbouma.com/projects/financedatabase

Contents: A static database of 180,000+ financial instruments including
  80,000+ equities, 15,000+ ETFs, 30,000+ mutual funds, categorised by:
  country, sector, industry, exchange, market cap classification.

Used for:
  Universe construction: Get all US equities in a given sector/industry:
    fd.select_equities(country="United States", sector="Technology")
    Returns a DataFrame of tickers, names, sectors, industries, exchanges.
    This is the cleanest free way to build screener universes without
    manually maintaining ticker lists.

  Sector/industry classification: When yfinance Ticker.info returns
    None for "sector" or "industry" (which happens occasionally),
    look up the ticker in FinanceDatabase as a fallback.

  Russell 2000 proxy: Filter US equities by market cap < $2B as an
    approximation. Not identical to the official Russell 2000 (which
    is reconstituted annually) but acceptable for screening purposes.

  European universe: Filter by country = major European nations
    (Germany, France, UK, Netherlands, Spain, Italy, Sweden, Switzerland)
    and exchange = major European exchanges to build an EU screener
    universe without a paid data subscription.

Note: FinanceDatabase provides ticker lists and metadata only — it does
  not provide price data or fundamentals. All actual financial data must
  still be fetched via yfinance using the tickers it provides.


──────────────────────────────────────────────────────────────────────
A.10  Wikipedia (S&P 500 Constituent Scraping)
──────────────────────────────────────────────────────────────────────
URL: https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
Cost: Free. No API key. Scrape with requests + pandas.read_html().

The first HTML table on this page contains all current S&P 500
  constituents with: ticker symbol, company name, GICS sector,
  GICS sub-industry, headquarters location, date added to index,
  CIK (SEC filing identifier), and founded date.

pandas.read_html(url)[0] returns this table directly as a DataFrame.
  Extract the "Symbol" column for all tickers and the "GICS Sector"
  column for sector classification.

Caching: Refresh weekly. Store as backend/data/sp500_constituents.json.
  S&P 500 membership changes infrequently (a few additions/removals
  per quarter). A weekly refresh is more than sufficient.

Same approach applies for:
  Nasdaq 100: https://en.wikipedia.org/wiki/Nasdaq-100
  Dow Jones 30: https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average


──────────────────────────────────────────────────────────────────────
A.11  Damodaran Data (NYU Stern — Static Annual Files)
──────────────────────────────────────────────────────────────────────
URL: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datacurrent.html
Cost: Free. No API key. Files are public Excel/CSV downloads.
Update frequency: Annually (January each year).

Files used:
  Country Risk Premiums (January 2026):
    URL: https://pages.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xlsx
    Contains: Country, Moody's rating, Default Spread, Country Risk
    Premium (CRP), Total Equity Risk Premium (ERP), Corporate Tax Rate.
    Download once per year, store as backend/data/damodaran_erp_2026.json.
    Used by Phase 1.0 (Country Selector) across all valuation models.

  Industry EV/EBITDA Multiples (January 2026):
    URL: https://pages.stern.nyu.edu/~adamodar/pc/datasets/vebitda.xlsx
    Contains sector/industry median EV/EBITDA, EV/EBIT, EV/Sales,
    EV/Capital multiples for US and global industry groupings.
    Use as fallback static sector multiples for Phase 1.6 (EV/EBITDA
    Comparable Company Analysis) when live peer computation fails.
    Store as backend/data/damodaran_multiples_2026.json.

  Implied ERP for S&P 500 (monthly updates):
    URL: https://pages.stern.nyu.edu/~adamodar/pc/implprem/ERPbymonth.xlsx
    Contains the monthly implied ERP for the US market derived from the
    S&P 500 level and earnings. Use to validate and contextualise the
    static ERP assumption in the valuation models.

Download these files once per year via a Python script that fetches
  the URLs, parses with pandas, and writes the relevant fields to JSON.


──────────────────────────────────────────────────────────────────────
A.12  SEC EDGAR (Insider Transactions — Phase 5 Insider Preset)
──────────────────────────────────────────────────────────────────────
URL: https://efts.sec.gov/LATEST/search-index?q=%22form+4%22
  or  https://data.sec.gov/submissions/ (company filing history)
  or  https://efts.sec.gov/LATEST/search-index?q=&dateRange=custom&
      startdt=2026-06-01&enddt=2026-06-23&forms=4
Cost: Free. No API key required. Public government data.
Documentation: https://www.sec.gov/developer

Form 4 filings disclose insider (officer, director, 10%+ shareholder)
  purchases and sales of company stock within 2 business days of the
  transaction. Filed electronically and publicly accessible.

For the "Insider Buying" screener preset (Phase 5.2):
  Endpoint: https://efts.sec.gov/LATEST/search-index?forms=4&
    dateRange=custom&startdt={30_days_ago}&enddt={today}
  Parse the returned filing list to identify:
  - Companies where insiders net-bought (more purchases than sales by
    dollar value) in the past 30 days
  - Filter for Form 4 transaction type "P" (purchase) vs "S" (sale)
  - Map CIK numbers to ticker symbols using the SEC company tickers JSON:
    https://www.sec.gov/files/company_tickers.json (free, no key)

This is a complex data pipeline — implement as a lower priority
  (Phase 5's last preset) and cache results with a 24-hour TTL.


═══════════════════════════════════════════════════════════════════════
APPENDIX B — BACKEND CACHING STRATEGY
═══════════════════════════════════════════════════════════════════════

Performance and API rate limit management depend entirely on a
well-designed caching layer. The following TTLs should be applied:

  REAL-TIME (refresh every 15 minutes during market hours, once daily
  outside market hours):
    - Global index prices (Phase 2.2)
    - FX rates (Phase 0.2)
    - Commodity prices (Phase 8.1)
    - S&P 500 constituent daily prices (Phase 2.1)
    - VIX (Phase 2.3)

  DAILY (refresh once per day, at 11pm UTC after all markets close):
    - Screener universe metrics for all tickers (Phase 5.1)
    - Fear & Greed composite score (Phase 2.3)
    - Market breadth statistics (Phase 2.1)
    - Top movers, unusual volume lists (Phase 2.5)
    - Options chain data per ticker (Phase 7)
    - Sector ETF performance (Phase 10)
    - Rolling risk metrics per ticker (Phase 6)
    - Snowflake scores for all universe tickers (Phase 9)

  WEEKLY (refresh every Sunday night):
    - S&P 500 constituent list (Wikipedia scrape, Phase 2.1)
    - Nasdaq 100 and Dow 30 lists (Phase 5.1)
    - Sector/industry classification per ticker (Phase 5.3)
    - Damodaran static multiples (check for annual update, Phase 1.6)
    - Earnings calendar for next 4 weeks (Phase 4.2)
    - IPO calendar (Phase 4.3)

  MONTHLY:
    - IMF WEO data check (update only in April and October, Phase A.7)
    - OECD CLI data (published monthly, Phase 8.2)
    - Eurostat macro series (published monthly, Phase 8.3)
    - World Bank annual data (check for new annual release, Phase A.4)
    - FRED monthly series: CPI, PCE, Unemployment, GDP, PMI etc.

  ANNUALLY (January):
    - Damodaran ERP and industry multiples files (Phase 1.0, A.11)
    - IMF WEO full refresh (April and October, Phase A.7)

CACHING IMPLEMENTATION:
  Use a simple in-process cache (Python functools.lru_cache with TTL
  wrapper, or cachetools library) for development. For production,
  upgrade to Redis for shared caching across multiple workers.
  All cache keys should include the relevant parameters (ticker, period,
  country code etc.) so different parameterisations are cached separately.
  Implement a /api/admin/cache/clear endpoint to manually invalidate
  stale cache entries during development and debugging.


═══════════════════════════════════════════════════════════════════════
APPENDIX C — FILE & FOLDER STRUCTURE
Complete listing of all new and modified files across all 10 phases.
═══════════════
