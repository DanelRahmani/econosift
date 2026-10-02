# Phase 59 status — 2026-10-02 (stopped at 91 % of the 5-hour usage window)

Committed on `DEV`. Fixes are unit-tested; the full local backend suite passes, and the technicals tests
(pandas_ta) passed in the container. **The phase gate has NOT run**: no spec-verifier, no Docker rebuild,
no container pytest, no live checks, no Playwright. ACTIVE_ISSUES / CHANGELOG are not updated yet.

## Done (code + known-value tests)

| ID | Fix | Test |
|---|---|---|
| P3-29 | 26 forward Senkou A/B bars from pandas_ta's span frame (`_forward_senkou`), joined without gap/overlap | `test_technicals_p59.py::test_ichimoku_emits_26_forward_senkou_bars` (+2) |
| P3-30 | Chikou at t = close at t+26 (extra `shift(-1)`) | `test_chikou_at_t_is_the_close_26_bars_later` |
| P3-32 | Daily pivot from the last completed NY session (`_last_session_complete`, `_now_ny`). Weekly/monthly holiday edge **documented, not fixed**: no trading-calendar dependency | `test_daily_pivot_uses_the_last_completed_session`, `..._converts_other_timezones_to_new_york` |
| P3-18 | Fibonacci from intraday High/Low, direction by which extreme came later; new `fibDirection`, `fibSwing` | `test_fib_downswing_when_the_low_comes_after_the_high` (+3) |
| P3-20 | Net debt = debt − (cash + short-term investments), no double count | `test_ratios_p59.py::test_net_debt_prefers_cash_plus_sti_line` (+2) |
| P3-21 | ROE labelled FY (`basis.roe`); ROIC NOPAT uses the WACC's tax rate (`discount_rates.tax_rate_for`) | `test_roe_is_labelled_fiscal_year`, `test_fundamentals_p59.py::test_roic_tax_rate_matches_the_wacc_tax_rate` |
| P3-22 | `debtToEquity` info fallback ÷ 100 | `test_debt_to_equity_info_fallback_is_percent` |
| P3-23 | EPS-surprise fallback in percent | `test_misc_p59.py::test_surprise_fallback_is_percent` |
| P3-24 | Fama-French `asOf` = last aligned data date (None on error paths) | `test_ff_asof_is_last_factor_date` |
| P3-25 | Relabelled: `universe` "S&P 500 sample (44 large caps)", `universeCount` (500 per-ticker `.info` calls too slow) | `test_short_interest_universe_labelled_honestly` |
| P3-33 | Piotroski: banks drop current ratio / gross margin / asset turnover, with `reasons`, on **both** Markets (`fundamentals.py`) and `/corporate` (`corporate_health_service.py`) | `test_bank_drops_three_criteria_and_max_score_is_six`, `test_piotroski_bank_drops_current_ratio_gross_margin_turnover` |

## Remaining (next session)

1. **P3-19 (not fixed yet).** 52-week range uses closes in `technicals_service.py:326-327` (and the
   field description ~line 501) and `treemap_service.py:171-177` (+ provenance ~222); Yahoo / breadth /
   movers use intraday. Switch both to `High.tail(252).max()` / `Low.tail(252).min()` (close fallback),
   test first. `screener_service.py:477-482` has the same difference (other page).
2. **P3-26 (only partly fixed).** `metrics` now labels `basis.fcfMargin`. Root cause still open:
   `yfinance_service.py:376-381` fills `info["freeCashflow"]` from the annual statement, and
   `dcf_engine.py:225-232, 320-327` labels it TTM. Add a marker (e.g. `info["_fcfBasis"] = "FY<year>"`) and use it
   for `fcfBasis`. Confirm live that JPM takes that path.
3. **Frontend.** Check that the Ichimoku chart handles 26 future rows (only senkouA/B set; x-axis domain).
   Add `fibDirection` / `fibSwing` and ratios `basis` to `types.ts`, and optionally show the direction,
   the ROE basis and the short-interest `universe` label. Then `tsc`.
4. **Gate 1–7** from the plan (spec-verifier on the phase diff, rebuild, container pytest, cache clear +
   live checks AAPL technicals / JPM Piotroski (both pages) / TSM+NVO ratios, Playwright, docs, push).
