# Axiom Finance Alpha 0.1

A locally-hosted, Dockerised, multi-asset financial analytics dashboard.

## Pillars

- **Markets** — search any stock ticker (US, EU, Asia); price charts, CAPM/DCF
  valuation, financial ratios, and portfolio risk metrics (VaR, CVaR, Sharpe,
  Sortino, Beta). Data via [yfinance](https://github.com/ranaroussi/yfinance).
- **Macro** — compare macroeconomic indicators across countries: GDP growth, CPI
  inflation, unemployment, policy rates, debt/GDP, current account, FX. Pulled
  from a 7-source pipeline with a priority waterfall (FRED, World Bank, ECB, IMF,
  DB.nomics, pandas-datareader, Frankfurter).

## Tech stack

- **Backend** — Python 3.12, FastAPI, uvicorn
- **Frontend** — Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts
- **Infra** — Docker Compose (backend, frontend, nginx)

## Quick start

```bash
cp .env.example .env   # optional: add a free FRED_API_KEY
docker compose up -d    # then open http://localhost
docker compose logs -f  # tail logs
docker compose down     # stop
```

No paid API keys are required. `FRED_API_KEY` is optional and free; without it
the macro pipeline falls back to pandas-datareader / World Bank / IMF.

## API

The backend is served under `/api` (proxied by nginx). Key endpoints:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/market/prices` | Normalised price history + benchmarks |
| `GET /api/market/risk` | VaR, CVaR, Sharpe, Sortino, Beta |
| `GET /api/valuation/capm-dcf` | CAPM expected return + DCF target |
| `GET /api/ratios/{ticker}` | Liquidity, leverage, efficiency, profitability, Z-score |
| `GET /api/macro/data` | Cross-country indicator series |
| `GET /api/macro/fx` | Live FX rates |

## Layout

```
backend/   FastAPI app (routers, services, 7 macro sources)
frontend/  Next.js dashboard (Markets + Macro)
nginx/     Reverse proxy (port 80)
```
