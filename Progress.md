# Axiom Finance — Progress & Continuation Plan

> Saved: 2026-06-29 | Plan mode session

## Current State

- 9/22 IDEA_LIST items complete (Phases 0–27)
- 13 remaining: 7 P1, 4 P2 (all P0 done)
- This plan covers the next 5 P1 items

---

## Feature 1: Global Bond Yields → /yield (#18, P1, Medium)

**Goal**: Expand /yield beyond US Treasuries to 20+ country 10Y yields with spread matrix and real yields.

### Backend
- **source_bis.py**: Add new BIS ZIP for government bond yields (`get_bond_yields_bulk()` function, follow `get_credit_gaps_bulk` pattern). Covers EM (CN/IN/BR/MX).
- **yield_curve_service.py**: 
  - Expand `_FOREIGN` dict: add ~12 FRED `IRLTLT01` OECD series (KR, CH, SE, NO, NL, NZ, etc.)
  - Add CPI deflation for real yields (BIS CPI + FRED CPI)
  - Compute yield spread matrix (each country vs US, vs DE, vs JP)
  - Extend `get_yield_curves()` response with `global_yields` key
  - Add new FRED series IDs to `_ALL_SERIES`
- **Router**: No changes — existing `GET /api/yield/curves` expands automatically

### Frontend
- **types.ts**: Add `GlobalYieldCountry { iso2, name, yield10y, realYield, spreadVsUS, spreadVsDE, spreadVsJP, history }` + extend `YieldCurvesData`
- **/yield/page.tsx**: New "Global Yields" tab with country selector, spread matrix table, real yield bar chart, time-series chart

### Verification
```
tsc --noEmit → docker compose build backend frontend → docker compose up -d → clear cache → Invoke-RestMethod http://localhost/api/yield/curves → browser /yield
```

---

## Feature 2: Labor Market Deep Dive → /macro?tab=labor (#7, P1, Medium)

**Goal**: Cross-country labor indicators with traffic-light signals.

### Backend
- **labor_service.py** (NEW): Pattern from `fiscal_service.py`. 
  - 5 WB codes: `SL.TLF.CACT.ZS` (LFPR), `SL.UEM.1524.ZS` (youth unemp), `SL.EMP.TOTL.SP.ZS` (emp/pop), `SL.EMP.VULN.ZS` (vulnerable emp), `SL.GDP.PCAP.EM.KD` (GDP/worker)
  - 2 FRED series for US: `AHETPI` (wages), `OPHNFB` (productivity) — reuse from `/macro/employment`
  - Traffic-light thresholds: LFPR >65 green, youth unemp >20 red, vulnerable >30 red
- **config.py**: Add 5 WB codes to `INDICATOR_MAP`
- **atlas_service.py**: Add 5 codes to `_WB_CODES`
- **macro.py**: Add `GET /api/macro/labor` calling `get_labor_data()`

### Frontend
- **types.ts**: Add `LaborData`, `LaborCountry`, `LaborCountryKpis`
- **api.ts**: Add `api.macroLabor()`
- **LaborTab.tsx** (NEW): KPI cards + bar charts (LFPR, youth unemp, emp/pop, vulnerable emp) + US wage chart
- **MacroTabShell.tsx**: Add "Labor" to TABS + dynamic import + switch case

### Verification
```
tsc --noEmit → build → deploy → clear cache → Invoke-RestMethod http://localhost/api/macro/labor → browser /macro?tab=labor
```

---

## Feature 3: Energy Transition & Climate → /macro?tab=energy (#8, P1, Medium)

**Goal**: CO₂ emissions, renewable share, fossil fuel dependency across countries.

### Backend
- **energy_service.py** (NEW): Pattern from `fiscal_service.py`.
  - 6 WB codes: `EN.ATM.CO2E.PC`, `EG.FEC.RNEW.ZS`, `EG.IMP.CONS.ZS`, `NY.GDP.PETR.RT.ZS`, `NY.GDP.NGAS.RT.ZS`, `NY.GDP.COAL.RT.ZS`
  - Traffic-light: CO₂ >10 red, renewable >30 green, energy imports >50 red, fossil rents >10 red
- **config.py**: Add 6 WB codes
- **atlas_service.py**: Add 6 codes
- **macro.py**: Add `GET /api/macro/energy`

### Frontend
- **types.ts**: Add `EnergyData`, `EnergyCountry`, `EnergyCountryKpis`
- **api.ts**: Add `api.macroEnergy()`
- **EnergyTab.tsx** (NEW): KPI cards + bar charts (CO₂, renewable share, energy imports, fossil rents)
- **MacroTabShell.tsx**: Add "Energy & Climate" tab

### Verification
```
tsc --noEmit → build → deploy → clear cache → Invoke-RestMethod http://localhost/api/macro/energy → browser /macro?tab=energy
```

---

## Feature 4: Currency Crisis Early Warning → /stability (#12, P1, Medium)

**Goal**: KLR (1998) signal extraction model. Traffic-light per country. New standalone page.

### Backend
- **currency_crisis_service.py** (NEW):
  - 5 indicators: reserves decline (existing `FI.RES.TOTL.CD`), current account (existing `BN.CAB.XOKA.GD.ZS`), real FX overvaluation (BIS effective FX + Frankfurter), inflation (existing `FP.CPI.TOTL.ZG`), short-term debt (NEW `DT.DOD.DSTC.ZS`)
  - KLR methodology: percentile rank per indicator → flag if top quartile → composite = weighted sum → green (0-1 flags) / yellow (2-3) / red (4-5)
- **config.py**: Add 1 WB code
- **atlas_service.py**: Add 1 code
- **stability.py** (NEW router): `GET /api/stability/currency-crisis`. Register in `main.py`.

### Frontend
- **types.ts**: Add `CurrencyCrisisData`, `CurrencyCrisisCountry`
- **api.ts**: Add `api.stabilityCurrencyCrisis()`
- **CurrencyCrisisPanel.tsx** (NEW): Traffic-light country cards, factor breakdown, composite score chart
- **/stability/page.tsx** (NEW): Page shell (will get tabs in Feature 5)
- **Navbar.tsx**: Add "Stability" to `moreTabs`
- **MobileNav.tsx**: Add Stability link

### Verification
```
tsc --noEmit → build → deploy → clear cache → Invoke-RestMethod http://localhost/api/stability/currency-crisis → browser /stability
```

---

## Feature 5: Banking & Financial Stability → extends /stability (#4, P1, Large)

**Goal**: NPL ratios, capital adequacy, bank Z-scores, BIS credit gaps. Composite banking EWS. Adds tab to /stability.

### Backend
- **banking_stability_service.py** (NEW):
  - 4 WB codes: `FB.AST.NPER.ZS` (NPL), `FB.BNK.CAPA.ZS` (capital/assets), `GFDD.SI.01` (Z-score), `FS.AST.DOMO.GD.ZS` (domestic credit)
  - BIS credit gaps via `source_bis.get_credit_gaps_bulk()` (dedicated call, no dependency on /macro/credit-gaps)
  - Composite EWS: NPL + capital + Z-score + credit growth + credit gap → traffic-light
- **config.py**: Add 4 WB codes
- **atlas_service.py**: Add 4 codes
- **stability.py**: Add `GET /api/stability/banking`

### Frontend
- **types.ts**: Add `BankingStabilityData`, `BankingStabilityCountry`
- **api.ts**: Add `api.stabilityBanking()`
- **BankingStabilityPanel.tsx** (NEW): NPL bar chart, capital adequacy, Z-scores, domestic credit, BIS credit gap heatmap
- **/stability/page.tsx**: Add tab structure: "Currency Crisis" | "Banking Stability"

### Verification
```
tsc --noEmit → build → deploy → clear cache → Invoke-RestMethod http://localhost/api/stability/banking → browser /stability?tab=banking
```

---

## Cross-Cutting: All New WB Codes

| Feature | Codes |
|---------|-------|
| Labor (5) | `SL.TLF.CACT.ZS`, `SL.UEM.1524.ZS`, `SL.EMP.TOTL.SP.ZS`, `SL.EMP.VULN.ZS`, `SL.GDP.PCAP.EM.KD` |
| Energy (6) | `EN.ATM.CO2E.PC`, `EG.FEC.RNEW.ZS`, `EG.IMP.CONS.ZS`, `NY.GDP.PETR.RT.ZS`, `NY.GDP.NGAS.RT.ZS`, `NY.GDP.COAL.RT.ZS` |
| Currency Crisis (1) | `DT.DOD.DSTC.ZS` |
| Banking (4) | `FB.AST.NPER.ZS`, `FB.BNK.CAPA.ZS`, `GFDD.SI.01`, `FS.AST.DOMO.GD.ZS` |

**Total: 16 new WB codes** — add to both `config.py` INDICATOR_MAP and `atlas_service.py` _WB_CODES.

---

## Key Patterns (Reference)

- **Service template**: `fiscal_service.py` — `@async_cached`, `atlas_service._wb_timeline()`, `_signal()` helper, `_to_timeseries()`
- **Tab component template**: `FiscalTab.tsx` — `useEffect` + `api.*()` + KPI cards grid + `Card` with bar charts
- **MacroTabShell**: Add to `TABS` array → `dynamic()` import → `switch` case
- **Standalone page**: `/trade` pattern — own router, page component, nav link
- **Types template**: `FiscalData`/`FiscalCountry`/`FiscalCountryKpis`
- **API template**: `api.macroFiscal()` → `get<FiscalData>('/macro/fiscal')`

---

## Verification Gate (Every Feature)

```powershell
# 1. TypeScript
cd frontend && npx tsc --noEmit

# 2. Build & Deploy
docker compose build backend && docker compose up -d backend
docker compose build frontend && docker compose up -d frontend

# 3. Clear persistent cache
docker exec axiomfinance-backend-1 python -c "from backend.database import SessionLocal; from backend.db_models import CacheEntry; db=SessionLocal(); db.query(CacheEntry).delete(); db.commit(); db.close(); print('cleared')"

# 4. Verify endpoint
Invoke-RestMethod -Uri http://localhost/api/... 

# 5. Browser check

# 6. Mark DONE in IDEA_LIST.md
```

---

## Working Agreements (from CLAUDE.md)

- NEVER fabricate data; on source failure, log + serve cached
- @async_cached persists to SQLite — clear stale cache after code fixes
- World Bank _wb_timeline returns {iso3: {year_int: value}} format
- Nginx proxy_read_timeout is 180s — don't lower it
- yfinance safety: always .get() with fallbacks
- After any backend change: build + deploy backend before frontend
- Commit + push after each feature
