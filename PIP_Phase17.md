# PIP Phase 17: Performance & Persistence Layer — RESTRUCTURED FOR AGENT EXECUTION

**Status**: Post-Phase 16  
**Goal**: Add persistent local database + background jobs to eliminate API rate limits and cold-start delays. Refactor caching for stale-while-revalidate.  
**Effort**: 5–6 weeks parallel (Backend 17.A–D, Frontend 17.E–G, Integration 17.H, optional Data 17.I)

## Quick Reference: Subphase Execution Order

```
Parallel Start:
├─ Phase 17.A: Database Foundation (Backend Opus) → 2–3h
├─ Phase 17.E: Frontend React Query Setup (Frontend Sonnet) → 1–2h
│
Phase 17.B: Job Infrastructure (Backend Opus) → 2–3h [waits for 17.A]
Phase 17.C: Cache Layer Upgrade (Backend Opus) → 1–2h [waits for 17.A]
Phase 17.F: Markets Page Refactor (Frontend Sonnet) → 2–3h [waits for 17.D + 17.E]
│
Phase 17.D: API Optimization Layer (Backend Opus) → 2–3h [waits for 17.C]
Phase 17.G: Progressive Tab Loading (Frontend Sonnet) → 1–2h [waits for 17.F]
│
Phase 17.H: Integration & Testing (DevOps Haiku) → 2–3h [waits for 17.D + 17.G]
│
Phase 17.I: Data Backfill (Optional, any Agent) → 4–6h [waits for 17.A + 17.B, can run async]
```

**Critical Path**: 17.A → (17.B || 17.C) → 17.D → 17.H (12–15 hours total)

---

## Part 1: Database Layer

### 1.1 Schema (PostgreSQL)

Create in `backend/backend/database.py`:

```sql
-- Daily OHLCV for all constituents + watchlist
CREATE TABLE daily_prices (
    symbol TEXT NOT NULL, date DATE NOT NULL,
    open FLOAT, high FLOAT, low FLOAT, close FLOAT, adj_close FLOAT, volume BIGINT,
    PRIMARY KEY (symbol, date), INDEX idx_date (date DESC)
);

-- Quote snapshots (updated daily ~17:30 UTC)
CREATE TABLE daily_quotes (
    symbol TEXT PRIMARY KEY, date DATE NOT NULL, price FLOAT, market_cap FLOAT,
    pe FLOAT, forward_pe FLOAT, div_yield FLOAT, beta FLOAT, high52 FLOAT, low52 FLOAT,
    avg_vol_20d FLOAT, updated_at TIMESTAMP DEFAULT NOW()
);

-- Macro indicators (FRED, WB, ECB, OECD)
CREATE TABLE daily_macro (
    indicator_id TEXT, country TEXT, date DATE NOT NULL, value FLOAT,
    PRIMARY KEY (indicator_id, country, date), INDEX idx_indicator (indicator_id, date DESC)
);

-- FX rates
CREATE TABLE daily_fx (
    base_ccy CHAR(3), quote_ccy CHAR(3), date DATE NOT NULL, rate FLOAT,
    PRIMARY KEY (base_ccy, quote_ccy, date), INDEX idx_date (date DESC)
);

-- Constituent universe snapshots (for historical drill-down)
CREATE TABLE constituents_snapshot (
    snapshot_date DATE, index_name TEXT, symbol TEXT, name TEXT, sector TEXT, industry TEXT,
    PRIMARY KEY (snapshot_date, index_name, symbol)
);

-- Job execution log
CREATE TABLE job_executions (
    job_id TEXT PRIMARY KEY, job_name TEXT, status TEXT,
    started_at TIMESTAMP, completed_at TIMESTAMP, error_message TEXT, rows_affected INT
);

-- Cache for responses (fallback if specific table missing)
CREATE TABLE cache_entries (
    cache_name TEXT, key TEXT, value JSONB, created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (cache_name, key)
);
```

### 1.2 HybridCache Implementation

Modify `backend/backend/cache.py`:

```python
# Tier 1: In-memory (fast, short TTL)
# Tier 2: DB (resilient, long TTL)
# Query order: memory → DB → None

class HybridCache:
    def __init__(self, db_session, name: str, ttl_sec: int = 3600):
        self.memory = TTLCache(maxsize=2048, ttl=ttl_sec)
        self.db = db_session
        self.name = name

    def get(self, key: str):
        if key in self.memory:
            self._record("hit_mem")
            return self.memory[key]
        
        row = self.db.query(CacheEntry).filter_by(
            cache_name=self.name, key=key
        ).first()
        
        if row:
            self._record("hit_db")
            val = json.loads(row.value)
            self.memory[key] = val  # Promote to memory
            return val
        
        self._record("miss")
        return None

    def set(self, key: str, value: Any):
        self.memory[key] = value
        self.db.upsert(CacheEntry, {
            'cache_name': self.name, 'key': key,
            'value': json.dumps(value), 'created_at': datetime.now()
        })

    def get_stale_while_revalidate(self, key: str, max_age_sec: int = 300):
        """Return immediately if cached (even stale). Spawn background refresh if old."""
        val = self.get(key)
        if val:
            age = time.time() - val.get('_ts', 0)
            if age > max_age_sec and val is not None:
                asyncio.create_task(self._refresh_bg(key))
            return val.get('data') if isinstance(val, dict) else val
        return None
```

### 1.3 Background Job Scheduler

Create `backend/backend/services/jobs.py`:

| Job | Schedule | Scope | Purpose |
|-----|----------|-------|---------|
| `refresh_daily_prices` | 16:00 UTC daily | S&P 500, NDX, Dow, watchlist | Batch yfinance OHLCV → daily_prices |
| `refresh_daily_quotes` | 17:00 UTC daily | Same 600 tickers | Quotes snapshot |
| `refresh_macro_daily` | 08:00 UTC daily | 50 FRED + WB + ECB series | Macro indicators |
| `refresh_fx_rates` | 09:00, 15:00, 21:00 UTC | G10 pairs, major EM | FX rates |
| `refresh_constituents` | Sun 09:00 UTC | S&P 500, NDX, Dow | Wikipedia API |
| `warm_screener_cache` | 08:00 UTC daily | Full universe (parallel to macro) | Existing logic, persist output |

Implementation pattern:

```python
# backend/backend/services/jobs.py

@app.on_event("startup")
async def start_scheduler():
    scheduler = BackgroundScheduler(
        jobstore={'default': MemoryJobStore()},
        timezone='UTC'
    )
    
    scheduler.add_job(
        refresh_daily_prices,
        CronTrigger(hour=16, minute=0),
        id='refresh_daily_prices',
        max_instances=1
    )
    # ... more jobs
    scheduler.start()

def refresh_daily_prices():
    """Fetch & persist OHLCV for tracked tickers."""
    try:
        tickers = get_all_tracked_tickers()
        closes, volumes = yfs.batch_download(tickers, period='5y')
        
        # Upsert into daily_prices
        with db.session() as s:
            for sym, dates_prices in closes.items():
                for date, price in dates_prices.items():
                    s.merge(DailyPrice(symbol=sym, date=date, ...))
            s.commit()
        
        # Update job log
        log_job_success('refresh_daily_prices', len(closes))
    except Exception as e:
        log_job_failure('refresh_daily_prices', str(e))
```

### 1.4 Docker Setup

Add to `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: axiom
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: axiomfinance
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U axiom"]
      interval: 10s
    restart: unless-stopped

  backend:
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://axiom:${DB_PASSWORD}@postgres:5432/axiomfinance
      SCHEDULER_ENABLED: "true"

volumes:
  postgres_data:
```

---

## Part 2: API Optimization

### 2.1 Composite Endpoint

Create `GET /api/market/composite`:

```python
@router.get("/composite")
async def market_composite(
    tickers: str = Query(...), period: str = "1y",
    benchmark: str | None = None
):
    """
    Return prices + risk + quotes in one request.
    - Single OHLCV fetch (reuse for all metrics)
    - Cache key: f"composite:{tickers}:{period}:{benchmark}"
    """
    syms = _parse_tickers(tickers)
    
    # Fetch once
    frame = await asyncio.to_thread(
        yfs.get_close_frame, tuple(syms + [benchmark] if benchmark else syms), period
    )
    
    # Compute both from same frame
    prices = _format_prices(frame, syms)
    risk = metrics.compute_risk(frame, syms, benchmark)
    quotes = await asyncio.gather(
        *[asyncio.to_thread(yfs.get_quote, s) for s in syms]
    )
    
    return {"prices": prices, "risk": risk, "quotes": quotes}
```

Register in `main.py`:

```python
app.include_router(market.router)  # /api/market/composite will be available
```

### 2.2 Request Deduplication

Simple in-memory dedup for identical in-flight requests:

```python
# backend/backend/middleware.py

_inflight: dict[str, asyncio.Future] = {}
_lock = asyncio.Lock()

async def deduplicate_middleware(request, call_next):
    """If identical request in-flight, await existing result instead of fetching again."""
    key = f"{request.url.path}?{request.url.query}"
    
    async with _lock:
        if key in _inflight:
            return await _inflight[key]
        
        future = asyncio.Future()
        _inflight[key] = future
    
    try:
        response = await call_next(request)
        future.set_result(response)
        return response
    except Exception as e:
        future.set_exception(e)
        raise
    finally:
        del _inflight[key]
```

Add to `main.py`:

```python
app.add_middleware(DeduplicationMiddleware)
```

### 2.3 Response Compression

Enable at Nginx:

```nginx
# nginx/default.conf
gzip on;
gzip_types application/json text/plain text/css application/javascript;
gzip_min_length 1000;
```

Reduce proxy timeouts:

```nginx
proxy_read_timeout 60s;  # Was 120s
proxy_connect_timeout 10s;
```

### 2.4 Admin Monitoring

Add `/api/admin/performance`:

```python
@router.get("/performance")
async def performance():
    return {
        "cache": cache.stats(),
        "jobs": db.query(JobExecution)
            .filter(JobExecution.completed_at > now() - timedelta(days=1))
            .all(),
        "database": {
            "connectionPoolSize": db.engine.pool.size(),
            "checkedOutConnections": db.engine.pool.checkedout()
        }
    }
```

---

## Part 3: Frontend Optimization

### 3.1 Upgrade to React Query v5

Install: `npm install @tanstack/react-query@latest`

Create `frontend/lib/queryClient.ts`:

```typescript
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,       // 5 min
      gcTime: 30 * 60 * 1000,          // 30 min (garbage collect)
      retry: 3,
      refetchOnWindowFocus: false,
      refetchOnReconnect: 'stale',
    },
  },
});
```

Wrap app in `frontend/app/layout.tsx`:

```typescript
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/queryClient';

export default function RootLayout({ children }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
```

### 3.2 Markets Page Refactor

Replace `useState` + manual fetches in `frontend/app/markets/page.tsx`:

```typescript
import { useQuery } from '@tanstack/react-query';

export function MarketsPageInner() {
  const [tickers, setTickers] = useState(['AAPL', 'MSFT']);
  const [period, setPeriod] = useState('1y');

  // Single composite query (replaces 3 sequential calls)
  const { data: composite, isLoading } = useQuery({
    queryKey: ['market-composite', tickers.join(','), period],
    queryFn: () => api.marketComposite(tickers.join(','), period),
    staleTime: 5 * 60 * 1000,
  });

  const { data: ratios } = useQuery({
    queryKey: ['ratios', tickers[0]],
    queryFn: () => api.ratios(tickers[0]),
    staleTime: 10 * 60 * 1000,
  });

  return (
    <>
      {isLoading && <Skeleton />}
      {composite && <PriceChart data={composite.prices} />}
      {composite && <RiskTable data={composite.risk} />}
      {ratios && <RatiosTab data={ratios} />}
    </>
  );
}
```

**Benefits:**
- React Query auto-deduplicates identical queries within staleTime
- Auto-retry on failure with exponential backoff
- Automatic garbage collection after gcTime
- Background refetch when data becomes stale

### 3.3 Progressive Tab Loading

Lazy-load below-the-fold tabs:

```typescript
const ValuationTab = lazy(() => import('./ValuationTab'));
const TechnicalsTab = lazy(() => import('./TechnicalsTab'));

export function MarketsPage() {
  const [activeTab, setActiveTab] = useState('overview');

  return (
    <>
      {activeTab === 'overview' && <OverviewTab />}
      
      <Suspense fallback={<Skeleton />}>
        {activeTab === 'valuation' && <ValuationTab />}
        {activeTab === 'technicals' && <TechnicalsTab />}
      </Suspense>
    </>
  );
}
```

---

## Part 4: Implementation Subphases (Agent-Assigned)

Each subphase is **independent** (parallelizable) and **testable**. Dependencies indicated by `→`.

### Phase 17.A: Database Foundation
**Owner**: Backend Agent (Opus)  
**Duration**: 2–3 hours  
**Dependencies**: None (can start immediately)  
**Parallel with**: Phase 17.E (Frontend setup)

**Files to create/modify**:
- `backend/backend/database.py` — SQLAlchemy engine, SessionLocal, ORM session dependency
- `backend/backend/models.py` — SQLAlchemy models: `DailyPrice`, `DailyQuote`, `DailyMacro`, `DailyFX`, `ConstituentsSnapshot`, `JobExecution`, `CacheEntry`
- `backend/backend/migrations/` (optional for MVP) — alembic schema creation scripts

**Acceptance Criteria**:
- [x] `DailyPrice` table exists with `(symbol, date)` PRIMARY KEY
- [x] `CacheEntry` table created for HybridCache fallback
- [x] `JobExecution` table created with status tracking
- [x] `pytest backend/tests/test_database.py` passes (schema + insert/select tests)
- [x] `.env.example` includes `DATABASE_URL=postgresql://...`

**Deliverable**: Schema present, migrations runnable, unit tests pass. No data backfilled yet.

---

### Phase 17.B: Job Infrastructure  
**Owner**: Backend Agent (Opus)  
**Duration**: 2–3 hours  
**Dependencies**: → Phase 17.A (database exists)

**Files to create/modify**:
- `backend/backend/services/jobs.py` — APScheduler setup, 3 job functions: `refresh_daily_prices()`, `refresh_macro_daily()`, `refresh_fx_rates()`
- `backend/backend/main.py` — Add `start_scheduler()` to lifespan, register jobs
- `backend/backend/services/jobs.py` — Job execution logging helper functions

**Acceptance Criteria**:
- [x] APScheduler initializes without errors in dev mode
- [x] `refresh_daily_prices()` callable manually; fetches & persists 5 tickers to DB
- [x] Job execution log entry created in `JobExecution` table
- [x] `pytest backend/tests/test_jobs.py` passes (mock jobs + execution log)
- [x] Scheduler startup doesn't block FastAPI startup

**Deliverable**: Jobs defined, manually testable, logged. Scheduler integrated into main.py. No recurring schedule yet (dry-run only).

---

### Phase 17.C: Cache Layer Upgrade
**Owner**: Backend Agent (Opus)  
**Duration**: 1–2 hours  
**Dependencies**: → Phase 17.A (DB schema exists)

**Files to create/modify**:
- `backend/backend/cache.py` — Add `HybridCache` class (in-memory + DB fallback); keep existing `@cached` / `@async_cached` decorators working
- `backend/backend/cache.py` — Add `get_stale_while_revalidate()` method
- `backend/backend/cache.py` — Extend `stats()` to return memory + DB hit counts

**Acceptance Criteria**:
- [x] `HybridCache` class initializes with DB session
- [x] `get()` returns from memory first, DB second, None third
- [x] `set()` writes to both memory and DB
- [x] Existing `@cached` decorator still works (backward compatible)
- [x] `cache.stats()` includes "hits_mem", "hits_db", "misses"
- [x] `pytest backend/tests/test_cache.py` passes

**Deliverable**: HybridCache implemented. Existing cache continues working. Stats track both layers. No APIs refactored yet.

---

### Phase 17.D: API Optimization Layer
**Owner**: Backend Agent (Opus)  
**Duration**: 2–3 hours  
**Dependencies**: → Phase 17.C (HybridCache exists)

**Files to create/modify**:
- `backend/backend/routers/market.py` — Add `GET /api/market/composite` endpoint
- `backend/backend/middleware.py` — Create `DeduplicationMiddleware` class
- `backend/backend/main.py` — Register dedup middleware
- `backend/backend/routers/admin.py` — Add `GET /api/admin/performance` endpoint
- `backend/nginx/default.conf` — Add gzip compression, reduce timeouts to 60s

**Acceptance Criteria**:
- [x] `GET /api/market/composite?tickers=AAPL,MSFT&period=1y` returns prices + risk + quotes in <300ms
- [x] Composite endpoint uses single OHLCV fetch (verify in logs)
- [x] Dedup middleware: 10 identical simultaneous requests → 1 yfinance call observed
- [x] `/api/admin/performance` returns cache stats + job stats + DB pool info
- [x] `pytest backend/tests/test_api_optimization.py` passes
- [x] Nginx gzip enabled; response size reduced by 60%+

**Deliverable**: Composite endpoint live. Dedup middleware active. Admin endpoint available. No frontend changes yet.

---

### Phase 17.E: Frontend React Query Setup
**Owner**: Frontend Agent (Sonnet)  
**Duration**: 1–2 hours  
**Dependencies**: None (can start immediately)  
**Parallel with**: Phase 17.A (Backend DB setup)

**Files to create/modify**:
- `frontend/package.json` — Add `@tanstack/react-query@latest`
- `frontend/lib/queryClient.ts` — Create QueryClient with config (staleTime, gcTime, retry)
- `frontend/app/layout.tsx` — Wrap with `QueryClientProvider`
- `frontend/lib/api.ts` — Add `marketComposite()` function

**Acceptance Criteria**:
- [x] `npm install` succeeds
- [x] `QueryClient` initializes with defaults (staleTime: 5min, gcTime: 30min)
- [x] `@tanstack/react-query/devtools` can be imported (optional for dev)
- [x] `api.marketComposite()` function defined (calls `/api/market/composite`)
- [x] `npm run build` succeeds (no TypeScript errors)

**Deliverable**: React Query installed, configured, wired into layout. API client ready. No pages refactored yet.

---

### Phase 17.F: Markets Page Refactor → React Query
**Owner**: Frontend Agent (Sonnet)  
**Duration**: 2–3 hours  
**Dependencies**: → Phase 17.D (composite endpoint live) + Phase 17.E (React Query setup)

**Files to create/modify**:
- `frontend/app/markets/page.tsx` — Replace `useState` + manual `useEffect` fetches with `useQuery` calls for:
  - `marketComposite` (replaces old prices + risk + quotes)
  - `ratios` (unchanged, but uses React Query)
- `frontend/components/markets/PriceChart.tsx` — Add loading skeleton
- `frontend/components/markets/RiskMetricsTable.tsx` — Add loading skeleton

**Acceptance Criteria**:
- [x] Markets page renders without waterfall (verify in DevTools Network tab: 1–2 API calls, not 3+)
- [x] React Query DevTools shows query deduplication working (open 2 browser tabs, same ticker → 1 request)
- [x] Page loads in <2s on first visit (measured via Lighthouse)
- [x] Stale data returned immediately; background refetch happens silently
- [x] `npm run build && npm run start` succeeds

**Deliverable**: Markets page uses React Query. No waterfall. Dedup working at browser level. All tabs render simultaneously (next phase).

---

### Phase 17.G: Progressive Tab Loading
**Owner**: Frontend Agent (Sonnet)  
**Duration**: 1–2 hours  
**Dependencies**: → Phase 17.F (Markets page uses React Query)

**Files to create/modify**:
- `frontend/app/markets/page.tsx` — Lazy-load expensive tabs: `ValuationTab`, `TechnicalsTab`, `PortfolioTab`, `RankingsTab`
- `frontend/app/markets/page.tsx` — Wrap lazy tabs in `Suspense` with skeleton fallback
- `frontend/components/markets/TabSkeleton.tsx` — Create placeholder loading state

**Acceptance Criteria**:
- [x] Only "Overview" and "Risk" tabs rendered on page load
- [x] Clicking "Valuation" tab: lazy component loads + renders (no blocking)
- [x] Lighthouse LCP <1.5s (vs ~2s in Phase 17.F)
- [x] Network tab shows lazy-loaded JS chunks for each tab
- [x] `npm run build` completes; no TypeScript errors

**Deliverable**: Below-the-fold tabs lazy-load on activation. Initial page load faster. Bundle split across chunks.

---

### Phase 17.H: Integration & Testing
**Owner**: DevOps/Integration Agent (Haiku)  
**Duration**: 2–3 hours  
**Dependencies**: → Phase 17.D (backend complete) + Phase 17.G (frontend complete)

**Files to create/modify**:
- `docker-compose.yml` — Add `postgres` service, update `backend` depends_on
- `.env.example` — Add `DATABASE_URL`, `SCHEDULER_ENABLED`, `SCHEDULER_TIMEZONE`
- `backend/tests/test_integration.py` — E2E: Docker up → populate DB → Markets page loads → verify <2s
- `backend/backend/main.py` — Add DB initialization + schema creation on startup

**Acceptance Criteria**:
- [x] `docker compose build` succeeds (Postgres + Python + Node all work)
- [x] `docker compose up` brings backend + frontend + postgres healthy within 30s
- [x] `curl http://localhost/api/health` returns `{"status":"ok"}`
- [x] `curl http://localhost/api/market/composite?tickers=AAPL&period=1y` returns data in <500ms
- [x] E2E test: Open `/markets?t=AAPL` in Playwright → LCP <2s, no 504 errors
- [x] Database persists across `docker compose down/up` (volume mounted)
- [x] `/api/admin/performance` shows job stats + cache hit rate >80%

**Deliverable**: End-to-end system works in Docker. Performance targets met. Ready for production.

---

### Phase 17.I: Data Backfill & Warmup (Optional, Async)
**Owner**: Any Agent (low priority, runs in background)  
**Duration**: 4–6 hours (offline, can run during dev)  
**Dependencies**: → Phase 17.A (schema exists) + Phase 17.B (jobs exist)

**Files to create/modify**:
- `backend/scripts/backfill_ohlcv.py` — Offline script: backfill 5Y OHLCV for S&P 500 + Nasdaq-100
- `backend/scripts/backfill_macro.py` — Backfill 5Y macro indicators from FRED

**Acceptance Criteria**:
- [x] `python backend/scripts/backfill_ohlcv.py` completes; 600 tickers × 5Y = ~1.5M rows inserted
- [x] Database size <500MB after backfill
- [x] `SELECT COUNT(*) FROM daily_prices` returns >1M rows
- [x] Job execution log shows no errors during backfill

**Deliverable**: Historical data populated. DB ready for production queries.

---

## Part 5: Testing by Subphase

### Phase 17.A Testing
```bash
pytest backend/tests/test_database.py -v
# Should verify: schema exists, insert/select works, constraints enforced
```

### Phase 17.B Testing
```bash
pytest backend/tests/test_jobs.py -v
# Mock jobs, verify logging to JobExecution table
python -c "from backend.backend.services.jobs import refresh_daily_prices; refresh_daily_prices()"
# Manual dry-run; should create DB entries
```

### Phase 17.C Testing
```bash
pytest backend/tests/test_cache.py -v
# HybridCache get/set, memory vs DB hit counting
```

### Phase 17.D Testing
```bash
pytest backend/tests/test_api_optimization.py -v
curl http://localhost:8000/api/market/composite?tickers=AAPL&period=1y
curl http://localhost:8000/api/admin/performance
# Verify <300ms, gzip enabled in response headers
```

### Phase 17.E Testing
```bash
npm install
npm run build
npm run dev
# Verify React Query DevTools available, queryClient accessible
```

### Phase 17.F Testing
```bash
npm run dev
# Open http://localhost:3000/markets?t=AAPL
# DevTools Network tab: confirm 1–2 API calls (not 3–5)
# React Query DevTools: check query deduplication
lighthouse http://localhost:3000/markets --view
```

### Phase 17.G Testing
```bash
npm run build
# Verify lazy chunks in .next/static/chunks/
npm run dev
# Click between tabs; verify lazy load (Network → JS chunks)
lighthouse http://localhost:3000/markets --view
# Verify LCP <1.5s
```

### Phase 17.H Testing (E2E Docker)
```bash
docker compose down -v  # Clean slate
docker compose build
docker compose up -d
sleep 30
curl http://localhost/api/health
curl http://localhost/api/market/composite?tickers=AAPL&period=1y
# Open http://localhost/markets?t=AAPL in browser
# Measure page load time (should be <2s)
docker compose down
```

---

## Part 6: Deployment Checklist

### Pre-Deployment (Phases 17.A–C Complete)
- [ ] Postgres healthcheck defined and tested
- [ ] `.env.example` updated with all new vars
- [ ] `DATABASE_URL` secrets configured in deployment environment
- [ ] Backup strategy for Postgres volume documented

### Deployment (Phases 17.H Complete)
- [ ] `docker compose build` succeeds
- [ ] `docker compose up` brings services healthy
- [ ] Post-deploy: run `backend/scripts/backfill_ohlcv.py` to warm cache
- [ ] Verify `/api/admin/performance` shows >0 jobs completed
- [ ] Monitor logs for 24h: no job failures expected

### Rollback Plan
**If Postgres is down**: Fall back to SQLite screener cache + in-memory TTL cache. Performance degrades but app remains live.
- API requests miss Postgres, use in-memory cache only (5–60 min lag)
- Expose manual refresh button in `/api/admin/force-refresh` for operators
- Re-enable Postgres; auto-backfill stale data on next job run

---

## Part 7: Expected Improvements

| Metric | Before | After | Gain |
|--------|--------|-------|------|
| First page load | 8–12s | <1.5s | **7–8×** |
| S&P 500 screener | 504 / timeout | <2s | **Fixed** |
| Cache hit rate | ~40% | >80% | **2×** |
| API P99 latency | 15–30s | <500ms | **40×** |
| yfinance API calls/day | ~5,000 | ~50 | **100×** |
| Tech recompute overhead | Per-request (×1000) | 1× daily | **99%** |

---

## Part 8: Maintenance

### Daily Monitoring
- `/api/admin/performance`: check job success rate (target: >99.5%)
- DB size: monitor growth (target: <2GB for 5Y OHLCV)
- Cache stats: track hit rate drift (alert if <75%)

### Weekly Tasks
- Review job logs for failures; fix root causes
- Check disk space on Postgres volume
- Verify constituent list updates from Wikipedia (Sun)

### Monthly Tasks
- Prune old data (keep 5Y rolling window; delete >5Y old)
- Analyze slow queries; add indices if needed
- Review API endpoint latencies; identify bottlenecks

### Yearly Tasks
- Archive yearly database snapshot
- Update APScheduler if new version available
- Capacity planning for next 12 months

---

## Part 9: Handoff & Agent Guidelines

### For Backend Agent (Opus)
- **Phases 17.A–D**: Database → Jobs → Cache → API
- Focus on DB schema first; all else depends on it
- APScheduler can share memory store (no Redis needed initially)
- Use `ThreadPoolExecutor` for job I/O to avoid blocking scheduler
- Test jobs in dry-run before scheduling
- Estimated total: 8–10 hours (can parallelize B & C after A)

### For Frontend Agent (Sonnet)
- **Phases 17.E–G**: React Query → Markets Refactor → Progressive Tabs
- React Query handles all caching automatically; don't implement duplicate cache
- Use `Suspense` for lazy tabs; don't use fallback spinners
- Test Network tab to confirm no waterfall; use Lighthouse CI
- Can work in parallel with backend phases 17.A–D
- Estimated total: 4–7 hours (can parallelize E with backend)

### For DevOps/Integration Agent (Haiku)
- **Phase 17.H**: Docker setup, E2E tests, deployment validation
- Postgres healthcheck is critical; set retries to 5+
- Mount volume for `postgres_data`; backup before deployments
- Nginx timeout can be reduced to 60s once DB caching active
- Estimated total: 2–3 hours (depends on phases 17.D + 17.G complete)

### For Any Agent (Optional Async)
- **Phase 17.I**: Data backfill (can run overnight, no blocking)
- Estimated total: 4–6 hours (runs independently)

### General Guidelines
- Coordinate DB schema before starting backend/frontend work (17.A prerequisite)
- Do not refactor existing cache.py; extend it with HybridCache class only
- Keep existing endpoint signatures; add new `/composite` rather than replacing old ones
- All existing Phase 0–16 features must continue to work unchanged
- Use `.env.example` as the source of truth for required config keys
- Every acceptance criterion must be verified before marking subphase complete
