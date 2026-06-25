# FIF Phase 18 — Macro-Financial Intelligence

## Purpose

Phase 18 is a long-term, economist-grade expansion of Axiom Finance that turns the platform from a financial analytics suite into a macro-financial intelligence system.

This phase is designed for:
- hedge fund research teams needing cross-asset risk signals, policy regime views, and credit/sovereign risk analytics;
- government economists tracking policy rate regimes, inflation expectations, and balance sheet / sovereign stress;
- portfolio managers who want a unified macro/credit/FX/commodity signal layer to augment existing markets, risk, and portfolio pages.

## Why it is missing today

The current app already has deep coverage of equities, options, risk metrics, technicals, sector analytics, and a rich macro atlas. What is still missing for a professional macro-financial user is:

- a unified policy and credit-risk layer that sits alongside the existing macro and markets pages;
- sovereign, yield-curve, inflation-expectation, and credit-spread analytics that are standard in government and hedge fund briefing decks;
- a scenario and regime engine that converts macro data into actionable stress signals rather than only descriptive dashboards;
- consistent data provenance, freshness, and fallback handling for high-value macro and credit series.

## Phase 18 Objectives

1. Build a Global Policy & Sovereign Risk hub.
2. Add cross-asset macro stress signals and term-structure analytics.
3. Provide a Macro Scenario & Econometric Lab for policy/risk analysis.
4. Deliver the data infrastructure and agent workflow for sustained long-term growth.

## Missing data / features to add

This phase should close the gap between descriptive macro dashboards and a professional macro-financial intelligence suite. The emphasis is on signals that are useful for economic policy analysis, sovereign/credit risk, and cross-asset allocation strategies.

### What other suites miss (and we can add)

- A consolidated policy path view that compares current central bank rates to market-implied curves and neutral-rate estimates.
- Sovereign financing stress signals that combine fiscal metrics, reserves, external debt, and market spread behavior.
- A liquidity/funding gauge built from central bank balance sheets, money aggregates, and funding spreads.
- Cross-asset macro regime alerts instead of stand-alone indicators: the same regime logic should drive equities, rates, credit, FX, and commodity signal overlays.
- Scenario analysis with historical episode templates plus a custom shock engine that directly links into portfolio/risk analytics.
- Transparent data provenance and freshness metadata for every macro and credit feed.

### 1. Global Policy & Central Bank Tracker

- Policy rate history and current rate for major central banks: Fed, ECB, BOE, BoJ, BoC, RBA, SNB, Norges, SARB, PBOC (where available).
- Balance-sheet/QE metrics and broad liquidity aggregates (currency base, total assets, reserves).
- Policy meeting calendar with decision dates, next meeting countdown, and simple probability signals derived from OIS or futures curves.
- Policy surprise index: compare realized rate actions to expectations from market-implied path or consensus rate forecasts.
- Policy divergence score: rank central bank easing/tightening cycles across major economies.
- Funding-cost differential panel for FX carry: short-rate differentials, basis spreads, and currency-specific carry signals.

### 2. Sovereign & Credit Risk Dashboard

- Sovereign risk panel for selected countries combining:
  - debt/GDP, fiscal balance, external balance, reserves, inflation, unemployment, and credit ratings where available.
  - market proxies: sovereign bond spread vs US Treasury, IG/HY corporate spread, CDS proxies from free sources or country debt yields.
- Composite sovereign risk score with traffic-light thresholds.
- Global credit pulse:
  - IG/HY OAS, high-yield share of issuance, TED spread, SOFR/OIS, commercial paper rates.
  - credit spread momentum and convexity signals.
- EM-specific risk watch:
  - reserve adequacy, external debt service, currency depreciation pressure, and carry-adjusted funding index.
- Top/bottom country movers in sovereign risk and cross-country macro stress.

### 3. Yield Curves, Inflation Expectations & Real Rates

- Multi-country yield curve builder with selectable countries and benchmark maturities.
- Real yield curves and breakeven inflation curves for economies with TIPS or inflation-linked bond markets.
- Term premium and curve inversion signals with a dedicated alert badge.
- Inflation expectations panel using breakevens, survey data, and market-based proxies when available.
- Policy-real rate gap chart: policy rate minus core inflation or a neutral rate proxy.

### 4. Macro Regime & Policy Signals

- Macro regime classifier built around growth, inflation, policy rate momentum, and yield-spread dynamics.
- Policy regime dashboard showing phases like “tightening”, “easing”, “neutral”, “stagflation”, “disinflation”.
- Regime-aware overlays on Atlas and Macro pages for countries and regions.
- Macro-risk allocation signals: regime-adjusted risk weights for equities, bonds, credit, FX, and commodities.
- Cross-asset signal heatmap aligned to the regime state.

### 5. Scenario & Stress Lab

- Scenario builder anchored in historical episodes:
  - 1980s volcker, 1998 LTCM, 2008 GFC, 2020 COVID, 2022 inflation shock, 2023 regional bank stress.
- Custom shock builder for rates, inflation, growth, credit spreads, FX, and commodity prices.
- Portfolio stress module using the existing portfolio and risk engines to estimate impact on weights, returns, and drawdowns.
- Scenario comparison dashboard with shock maps, regime transition probabilities, and risk-factor attribution.
- “What if” policy path scenarios for central bank rates and curve shifts.

### 6. Econometric & Policy Analytics Lab

- OLS regression lab for macro series with detrending, lag selection, and diagnostics.
- Policy rule calculators: Taylor rule, neutral rate estimate, real-rate gap, and output-gap proxy.
- Leading/coincident indicator composites for growth and inflation.
- Simple survey vs market expectation comparison panels using available inflation and rate-expectations data.
- Regression-based regime predictors for recession, inflation surprise, and rate-hike cycles.

### 7. Funding, Liquidity & Sentiment Signals

- Liquidity gauge built from central bank balance sheets, monetary aggregates, and funding spread metrics.
- Global funding stress panel using TED spread, SOFR/OIS, and commercial paper rates.
- FX funding carry watch: short-rate differentials, basis moves, and FX volatility regimes.
- Macro/credit sentiment panel that tracks news headlines, central bank commentary, and market risk-off themes.
- Commodity risk signals for oil, copper, and agriculture tied to macro and inflation regimes.

### 8. Data Source Feasibility & Rate Limit Considerations

- Data sources are chosen from the APIs listed in `API_suggestions.md`, with priority on free, structured endpoints and no scraping.
- Primary macro/credit sources: FRED, IMF/WEO, World Bank, ECB SDMX, BoE CSV, BoC Valet, BoJ CSV, RBA tables, SNB API, HKMA API, MAS/data.gov.sg, DB.Nomics.
- Market sources: yfinance (equities/FX/futures), Alpha Vantage, IEX Cloud free tier, plus existing Ken French/EDGAR/FINNHUB connections.
- Cache external sources aggressively: daily/weekly snapshots for macro, 60-min caches for market-sensitive credit metrics, and on-demand refresh only for slow sources.
- Use aggregated APIs where possible (e.g. DB.Nomics or SDMX endpoints) to reduce request volume and avoid per-ticker fan-out.
- When data is missing, expose explicit fallback notes and keep UI behavior graceful.

## Phase 18 Implementation Order

This section is written for Claude Code to dispatch agents cleanly, with tasks that can often run simultaneously when non-conflicting. Use the strongest model available for design and the cheaper Haiku model for test generation and validation. A headless browser skill should be used for UI/self-testing.

### 1. Discovery & API contract phase

- Task 1.1: Research agent
  - Inventory approved free data sources from `API_suggestions.md` that match Phase 18 needs.
  - Confirm which central bank, sovereign, credit, and funding series are available via FRED, IMF, WB, ECB SDMX, DB.Nomics, BoE, BoC, BoJ, RBA, SNB, HKMA, MAS, and other free endpoints.
  - Produce a contract document listing new endpoint names, request parameters, expected payload shapes, and cache semantics.
  - Output: `phase18_api_contract.md` and a new section in `FIF_Phase18.md` with final API contracts.

- Task 1.2: Data agent
  - Validate data availability and rate limits for each proposed source.
  - Identify which sources require daily/weekly snapshots vs on-demand refresh.
  - Define fallback cascades for missing macro/credit series.
  - Output: `phase18_data_inventory.md` with source mappings, update frequency, and rate-limit strategy.

### 2. Backend scaffolding

- Task 2.1: Backend agent
  - Create the skeleton services and routers for `policy`, `sovereign`, `yield_curve`, `credit`, `scenario`, and `econometrics`.
  - Add new endpoints to `main.py` and wire them into `frontend/lib/api.ts` as stubs.
  - Implement lightweight cache wrappers in `cache.py` for new source categories.
  - Output: backend API contracts, stubbed service methods, `api.ts` endpoint definitions.

- Task 2.2: Data agent (parallel with 2.1)
  - Build extraction helpers for the highest-priority sources first (FRED, World Bank, ECB, BoC Valet, BoE CSV).
  - Implement normalization functions that produce consistent decimals, dates, and metadata.
  - Output: reusable fetchers in `backend/backend/services/` with cache-friendly designs.

### 3. Core analytics implementation

- Task 3.1: Backend agent
  - Implement central bank policy rate and balance-sheet metrics.
  - Implement sovereign risk score and credit pulse analytics.
  - Implement yield curve builder and breakeven/real rate analytics.
  - Implement scenario templates and portfolio stress calculations.
  - Implement econometric lab utilities and policy rule calculators.
  - Output: working endpoints returning sanitized JSON with source metadata.

- Task 3.2: Research agent (parallel)
  - Validate formulas and thresholds for regime classifier, sovereign risk score, policy surprise, and term-premium flags.
  - Produce test cases and expected output behavior for each analytics module.
  - Output: `phase18_regime_rules.md` and score thresholds.

### 4. Frontend page & widget development

- Task 4.1: Frontend agent
  - Build the new `/policy`, `/sovereign`, `/yield`, and `/scenario` pages with placeholder layouts.
  - Add widgets for trending policy, sovereign risk, credit pulse, and term-spread alerts.
  - Enhance `/macro` with regime overlays, inflation expectation widgets, and data freshness indicators.
  - Output: React page scaffolds, components, and new nav links.

- Task 4.2: Backend + Frontend integration
  - Connect UI components to the new API routes.
  - Ensure shared TypeScript types are updated in `frontend/lib/types.ts`.
  - Verify loading states, fallback notes, and error handling for slow data sources.

### 5. Self-testing & headless verification

- Task 5.1: Testing agent (Haiku)
  - Generate a lightweight regression test suite for the new endpoints and pages.
  - Use cheap model reasoning to identify high-value test cases: endpoint health, cache behavior, fallback messages, and page render checks.
  - Output: backend tests under `backend/tests/` and frontend endpoint smoke tests if applicable.

- Task 5.2: Headless browser skill
  - Use a browser skill or Playwright to navigate to `/policy`, `/sovereign`, `/yield`, and `/scenario`.
  - Verify the pages render, load data, and display the expected basic widgets.
  - Confirm a new page loads with HTTP 200 and the UI shows a data freshness badge or fallback note.

### 6. Final validation & documentation

- Task 6.1: Research/Review agent
  - Validate that the implemented phase matches the economist-grade use case.
  - Confirm that all new features are consistent with approved data sources and do not require scraping.
  - Output: updated `FIF_Phase18.md` summary and a short implementation retrospective.

- Task 6.2: Documentation agent
  - Update `README.md` or `CLAUDE.md` if the new macro-financial workspace needs a brief mention.
  - Ensure `API_suggestions.md` is referenced in the phase plan.

## Agent delegation and concurrency

- Research and Data agents can run in parallel during discovery and validation.
- Backend and Data agents may overlap on ingest/normalization while service scaffolding is created; they should coordinate on API contract definitions.
- Frontend can begin once endpoint contracts are defined and stubbed; full data binding awaits backend implementation but page scaffolds can be developed in parallel.
- Testing can begin as soon as stable endpoints exist, and should use the Haiku model for lightweight validation plus headless browser automation for UI checks.

## Phase 18 Deliverables

### Backend components

- `services/policy_service.py`
  - central bank rates, balance sheets, policy calendars, surprise index.
- `services/sovereign_risk.py`
  - debt metrics, current account, reserves, CDS/spreads, risk classification.
- `services/yield_curve.py`
  - multi-country yield curve builder, inflation breakevens, real yields.
- `services/credit_market.py`
  - IG/HY spreads, TED/SOFR-OIS, credit impulse signals.
- `services/scenario_lab.py`
  - historical scenario definitions, custom shock engine, portfolio impact.
- `services/econometric_lab.py`
  - regression engine, policy rules, indicator composites.
- `services/sentiment_service.py` (optional)
  - news sentiment and central bank headline watch.
- New routers: `policy.py`, `sovereign.py`, `yield_curve.py`, `credit.py`, `scenario.py`, `econometrics.py`.
- Cache management via `cache.py` for all new external sources.

### Frontend components

- New page: `/policy`
  - policy tracker, meeting calendar, rate path, central bank balance sheets.
- New page: `/sovereign`
  - country risk panels, sovereign risk ranking, CDS/spread views.
- New page: `/yield`
  - yield curves, breakeven curves, term premium, inversion alerts.
- New page: `/scenario`
  - scenario builder, historical episodes, portfolio stress views.
- Enhanced `/macro` page:
  - policy/regime overlays, inflation expectation widgets, survey vs market signals.
- Dashboard widgets:
  - credit market pulse, spread momentum, term spread alert.
- `components/macro/` additions for risk badges, regime scorecards, and data freshness indicators.

### Agent workflow

- Research agent:
  - define data sources, policy rate mappings, and scenario definitions.
  - validate economic theory behind the regime classifier and stress scenarios.
- Data agent:
  - build ingestion and normalization for FRED, IMF, WB, ECB, BIS, and market-derived credit series.
  - ensure fallback logic and cache timing for slow sources.
- Backend agent:
  - implement services, routers, and derived analytics.
  - integrate with existing `main.py` and `cache.py` patterns.
- Frontend agent:
  - build pages, charts, and summary panels for the new macro-financial features.
  - wire the new API endpoints into `frontend/lib/api.ts` and shared types.
- Testing agent:
  - generate lightweight tests with Haiku.
  - execute UI verification through a headless browser.

## Success criteria

- A new Macro-Financial Intelligence workspace is available from the app nav.
- Central bank policy tracker, sovereign risk panels, yield curve analytics, and scenario lab all load without errors.
- New backend endpoints have cached external sources and clear data provenance.
- The phase supports both long-term research workflows and real-time policy/risk monitoring.

## Questions to resolve before implementation

1. Which additional external macro/credit sources are approved for this repo beyond FRED, Finnhub, IMF, and World Bank?
2. Should sovereign CDS be included only where free data exists, or should this phase defer CDS until an external paid feed is approved?
3. Do we want the stress lab to support direct portfolio re-weighting suggestions, or keep it as descriptive scenario analysis only?
4. Is there appetite for a simple `policy risk` score that blends rate path, inflation surprise, and fiscal impulse into one composite?

## Long-term strategic fit

Phase 18 should become the foundational macro-financial layer for Axiom Finance, bridging the existing market/risk pages with the planned research lab in Phases 14–16. It is the phase that makes the platform useful not only for equity and option analysis, but for sovereign/credit policy-risk decisions as well.
