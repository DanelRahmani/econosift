# Axiom Finance — Feature Idea List

> Last cleaned: 2026-06-30 — Phase 40 shipped (Navigation Reshuffle). All P3 items + nav reshuffle complete.
> Remaining: 0 ideas. IDEA_LIST is fully delivered.

---

## 2. Data Source Quick Reference

| Source | Package | Coverage | Currently Mapped | Untapped Potential |
|--------|---------|----------|------------------|-------------------|
| World Bank | `wbgapi` | ~200 countries, ~1,400 indicators | 19 indicators | 1,380+ indicators |
| FRED | `fredapi` | US-focused, 800K+ series | ~40 series | Massive untapped US data |
| IMF WEO | `imfp` | ~190 countries, forecasts | 6 indicators | Additional WEO indicators |
| BIS | httpx + ZIP | 50+ countries, 6 datasets | CPI, policy, FX, credit gaps, property prices, effective FX | Banking stats |
| ECB | `ecbdata` | Eurozone only | Inflation, policy rate | ECB SDW has hundreds of series |
| Frankfurter | httpx | 30+ currencies | Spot + history FX | — |
| DB.nomics | `dbnomics` | OECD + BIS | 4 indicators | Full OECD database |
| yfinance | `yfinance` | US + international stocks | Price/OHLC only | Full financial statements, dividends, info |
| Finnhub | httpx | US + some global | Calendar, news, earnings | Short interest, M&A, corporate actions |
| EDGAR | `edgartools` | US-listed companies | 13F, Form 4 per ticker | Aggregate insider analysis |
| CFTC | httpx + ZIP | US futures | COT reports | Disaggregated COT, supplemental reports |
| Local | JSON + Parquet | Damodaran ERP, sector multiples, CB meetings, bulk cache | 4 local files | Expand static datasets |

---

## 3. 🧠 Ideas
