# First-run setup wizard — plan (draft, 2026-10-01)

## Why
A fresh install opens on an empty cache: every page fans out to FRED, World Bank, BIS,
Yahoo and CFTC at once and the first visit takes minutes. The wizard turns that dead time
into setup time: while the user picks preferences and enters keys, the backend warms
everything that needs no key. It also collects the preferences the app currently hard-codes
(Markets opens on `AAPL,MSFT`, prices only in the listing currency, discount rate always
the per-country CAPM).

The wizard does not remove the need for the Phase 51 concurrency fixes: a cold backend
must stay responsive while it warms, and caches expire again after 60 minutes or a
restart.

## Flow

Route `/setup`, a five-step stepper. The keyless warm starts the moment the page opens.

| Step | Asks | Notes |
|---|---|---|
| 0 Welcome | — | `POST /api/setup/warm` starts the **keyless warm** (below); a progress strip stays visible on every step |
| 1 Currency | Display currency (USD, EUR, GBP, JPY, KRW, CHF, CAD, AUD, …). "Also show the stock's own currency" toggle (default on) | Live preview: `005930.KS ₩71,000 · ≈ $51.20` and `AAPL $230.10 · ≈ €212.40` |
| 2 Valuation | Discount rate: **Automatic** (today's per-country CAPM / WACC, default) or **Fixed** (user enters e.g. 9.0 %). Each stock's DCF stays overridable | Shows the automatic rate for the US and the user's home market so the choice is informed |
| 3 Markets | Default tickers (chips + search, up to 6), default period, benchmark | On "Next", these tickers are added to the warm queue at once |
| 4 Data sources | FRED, Finnhub, Gemini keys (all optional, inline validation, sign-up links, what each unlocks). **SEC EDGAR identity**: name + contact email | Saving a key takes effect immediately (no restart) and queues the keyed warm (FRED macro set) |
| 5 Done | Summary + warm progress | "Open dashboard"; everything editable later in Admin → Preferences |

### Keyless warm (runs during the wizard)
Index constituents (S&P 500, Nasdaq 100, Dow) and screener universe; World Bank / IMF / BIS
bulk datasets; Atlas timelines; country risk; ECB FX rates (Frankfurter); Yahoo quotes and
1-year prices for the index ETFs and the chosen default tickers; Fama-French factors;
sovereign, stability and yield pages that do not depend on FRED. It reuses
`prefetch_service` with a keyless task list. It runs at modest concurrency so the wizard's
own requests (key validation, ticker search) stay fast.

### SEC EDGAR
`data.sec.gov` and EDGAR full-text need **no API key**, but SEC's fair-access policy
requires every request to declare a `User-Agent` of the form
`Company/Person Name contact@domain.com`, and caps traffic at 10 requests/second.
`edgartools` sends it via `set_identity()`. The backend already reads
`settings.json → edgar_identity`; the gap is a UI field. Validation: format check
(name + email), then one test request (`https://data.sec.gov/submissions/CIK0000320193.json`)
with that User-Agent. It is never pre-filled.

## Design decisions

- **Preferences live in the backend** (`DATA_DIR/settings.json`, same file as keys), not
  localStorage: the warm needs to know the default tickers, the desktop and Docker builds
  both have a `DATA_DIR`, and preferences survive a browser change.
- **Keys reload at runtime.** Today `config.FRED_API_KEY` etc. are read once at import, so
  Admin says "restart required". Replace them with a `config.key("fred")` accessor that
  reads the current settings; migrate the ~20 import sites. Admin and the wizard write
  `settings.json` (Docker keeps reading `.env` first, unchanged).
- **Currency conversion happens in the frontend** with one cached rates map
  (`fx_service.fx_rates`, ECB reference rates via Frankfurter, Yahoo FX pair as fallback
  for currencies the ECB does not publish, e.g. TWD). A `<Money value currency>`
  component renders local + converted. Backend responses stay unchanged. Converted figures
  are marked "≈" and their Source panel names the rate and its date.
  Only money amounts convert (price, market cap, EV, fair values, targets, 52-week
  range, dividend per share, portfolio values), never ratios or percentages.
- **Fixed discount rate** feeds the DCF/DDM default only. The 8-model engine's
  CAPM-based models keep CAPM, and the panel states which rate was used and why.
- **First-run detection:** `GET /api/setup/status → {completed}`. The app layout redirects
  to `/setup` when not completed (never from `/admin` or `/setup`).
  `ECONOSIFT_SKIP_SETUP=1` marks setup complete so CI and the Playwright suite are
  never redirected.

## Work breakdown (proposed phases)

| Phase | Scope | Gate |
|---|---|---|
| A | `config` runtime accessor + migrate key reads; `settings.json` writer; Admin: EDGAR identity field + validation; `GET/PUT /api/setup/preferences`, `GET /api/setup/status` | pytest: key hot-reload, prefs round-trip, EDGAR identity validation (format + mocked SEC call) |
| B | `/setup` wizard UI (5 steps), layout redirect, keyless warm task list + `POST /api/setup/warm` + progress | Playwright: fresh data dir → redirected → completes wizard → lands on dashboard; CI path skips |
| C | `<Money>` + FX rates hook; apply to Quote cards, Valuation KPIs, DCF, Analyst targets, Portfolio | Known-value test: KRW→USD conversion with a fixed rate; tsc |
| D | Discount-rate preference wired into DCF/DDM defaults + provenance note | pytest: fixed vs automatic rate path |
| E | Admin → Preferences (edit everything, "Re-run setup") + "Finish setup" banner for existing installs | Playwright smoke |
| F | Optional chart conversion with daily historical FX | Known-value test against ECB reference rates |

## Owner decisions (2026-10-01)
- **Existing installs:** not forced. They get a dismissible "Finish setup" banner; fresh
  installs get the wizard.
- **Dual currency:** headline money figures as above, plus an **optional chart toggle**
  that converts price history with each day's historical FX rate (ECB reference series;
  Yahoo FX pair fallback). Off by default.
- **Discount rate:** automatic per-country CAPM/WACC by default, with an optional fixed
  override used as the DCF/DDM default; per-stock override stays.
- **Stale data:** yes to stale-while-revalidate. Serve the last good value instantly
  (bounded age, e.g. 24 h), refresh in the background, show a small "refreshing" badge;
  the Source panel already shows the fetch time. Shipped as its own phase before the
  wizard, because it fixes slow loads after any idle hour, not only on first run.
