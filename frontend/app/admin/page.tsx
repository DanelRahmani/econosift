"use client";

// cache-bust: 2026-06-28 api-keys-admin
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { HealthResponse, PrefetchStatus, BulkDatasetStatus, ConfigResponse } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";

function fmtUptime(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  return h ? `${h}h ${m}m` : m ? `${m}m ${s}s` : `${s}s`;
}

export default function AdminPage() {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [pf, setPf] = useState<PrefetchStatus | null>(null);
  const [pfRunning, setPfRunning] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setData(await api.health());
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  const startPrefetch = useCallback(async () => {
    setPfRunning(true);
    try {
      const res = await api.prefetchStart();
      setPf(res.progress);
    } catch (e) {
      setPfRunning(false);
    }
  }, []);

  // Poll prefetch status while running
  useEffect(() => {
    if (!pfRunning) return;
    const id = setInterval(async () => {
      try {
        const s = await api.prefetchStatus();
        setPf(s);
        if (!s.running) setPfRunning(false);
      } catch { setPfRunning(false); }
    }, 2000);
    return () => clearInterval(id);
  }, [pfRunning]);

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, []);

  const pct = pf && pf.total ? Math.round((pf.done / pf.total) * 100) : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-display font-bold">Backend Health</h1>
        <div className="flex gap-2">
          <button
            onClick={startPrefetch}
            disabled={pfRunning}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
              pfRunning
                ? "border-accent/30 bg-accent/10 text-accent cursor-wait"
                : "border-accent/40 bg-accent text-white hover:bg-accent-light"
            }`}
          >{pfRunning ? "Prefetching…" : "Warm Cache"}</button>
          <button
            onClick={load}
            className="px-3 py-1.5 rounded-lg text-sm font-medium border border-border text-text-secondary hover:text-text-primary hover:bg-surface-alt transition-colors"
          >Refresh</button>
        </div>
      </div>

      {/* Prefetch progress */}
      {pf && (pfRunning || pf.done > 0) && (
        <Card>
          <h2 className="text-sm font-semibold mb-3 text-text-secondary">
            Cache Warming {pfRunning ? "in progress…" : pf.failed ? "— completed with errors" : "— complete"}
          </h2>
          {/* Progress bar */}
          <div className="w-full h-2 bg-surface-alt rounded-full mb-3 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${pf.failed > 0 ? "bg-warning" : "bg-success"}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="flex gap-6 text-sm">
            <span className="text-text-secondary">{pf.done}/{pf.total} tasks</span>
            <span className="text-success">{pf.ok} ok</span>
            {pf.failed > 0 && <span className="text-danger">{pf.failed} failed</span>}
            {pf.current && <span className="text-text-muted truncate max-w-xs">· {pf.current}</span>}
          </div>
          {/* Error list */}
          {pf.errors.length > 0 && (
            <div className="mt-3 space-y-1 max-h-32 overflow-y-auto">
              {pf.errors.map((e, i) => (
                <div key={i} className="text-xs text-danger bg-danger/5 rounded px-2 py-1 font-mono">
                  {e.label}: {e.error}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {loading && !data ? (
        <Skeleton className="h-40" />
      ) : data ? (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <Stat label="Status" value={data.status.toUpperCase()} tone="pos" />
            <Stat label="Uptime" value={fmtUptime(data.uptimeSeconds)} />
            <Stat
              label="Cache Hit Rate"
              value={data.cache.overallHitRate !== null ? `${(data.cache.overallHitRate * 100).toFixed(1)}%` : "—"}
            />
            <Stat label="FRED API Key" value={data.config.fredApiKey ? "Set" : "Missing"} tone={data.config.fredApiKey ? "pos" : "neg"} />
            <Stat label="Finnhub API Key" value={data.config.finnhubApiKey ? "Set" : "Missing"} tone={data.config.finnhubApiKey ? "pos" : "neg"} />
          </div>

          {/* API Keys */}
          <ApiKeysSection />

          <Card>
            <h2 className="text-sm font-semibold mb-4 text-text-secondary">Cache Performance by Source</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-text-secondary border-b border-border">
                    <th className="text-left py-2 px-3 font-medium">Cache</th>
                    <th className="text-right py-2 px-3 font-medium">Hits</th>
                    <th className="text-right py-2 px-3 font-medium">Misses</th>
                    <th className="text-right py-2 px-3 font-medium">Hit Rate</th>
                    <th className="text-right py-2 px-3 font-medium">Entries</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.cache.byName).map(([name, s]) => (
                    <tr key={name} className="border-b border-border/50">
                      <td className="py-2 px-3 font-mono">{name}</td>
                      <td className="py-2 px-3 text-right font-mono text-success">{s.hits}</td>
                      <td className="py-2 px-3 text-right font-mono text-text-muted">{s.misses}</td>
                      <td className="py-2 px-3 text-right font-mono">{s.hitRate !== null ? `${(s.hitRate * 100).toFixed(0)}%` : "—"}</td>
                      <td className="py-2 px-3 text-right font-mono">{s.size}</td>
                    </tr>
                  ))}
                  {!Object.keys(data.cache.byName).length && (
                    <tr><td colSpan={5} className="py-6 text-center text-text-muted">No cache activity yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-text-muted mt-3">TTL: {Math.round(data.cache.ttlSeconds / 60)} min · auto-refreshes every 15s</p>
          </Card>

          {/* Database Health */}
          {data.database && !data.database.error && (
            <Card>
              <h2 className="text-sm font-semibold mb-4 text-text-secondary">Database Health</h2>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                <DbStat label="Cache Entries" value={data.database.cache_entries?.toLocaleString() ?? "—"} />
                <DbStat label="Cache Size" value={data.database.cache_size_kb != null ? `${(data.database.cache_size_kb >= 1024 ? (data.database.cache_size_kb / 1024).toFixed(1) + " MB" : data.database.cache_size_kb + " KB")}` : "—"} />
                <DbStat label="Price Rows" value={data.database.daily_price?.toLocaleString() ?? "—"} />
                <DbStat label="Quote Rows" value={data.database.daily_quote?.toLocaleString() ?? "—"} />
                <DbStat label="Macro Rows" value={data.database.daily_macro?.toLocaleString() ?? "—"} />
                <DbStat label="FX Rows" value={data.database.daily_fx?.toLocaleString() ?? "—"} />
                <DbStat label="Job Executions" value={data.database.job_execution?.toLocaleString() ?? "—"} />
              </div>
            </Card>
          )}
          {data.database?.error && (
            <Card><div className="text-red-500 text-sm">DB Error: {data.database.error}</div></Card>
          )}

          {/* Bulk Data Status */}
          <BulkDataSection />
        </>
      ) : (
        <Card><div className="text-text-muted text-sm">Could not reach backend.</div></Card>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "pos" | "neg" }) {
  return (
    <Card>
      <div className="text-xs text-text-muted mb-1">{label}</div>
      <div className={`text-lg font-mono ${tone === "pos" ? "text-success" : tone === "neg" ? "text-danger" : "text-text-primary"}`}>{value}</div>
    </Card>
  );
}

function DbStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface-alt rounded-lg p-3">
      <div className="text-xs text-text-muted mb-0.5">{label}</div>
      <div className="text-sm font-mono text-text-primary">{value}</div>
    </div>
  );
}

function ApiKeysSection() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [editing, setEditing] = useState<"fred" | "finnhub" | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [restartBanner, setRestartBanner] = useState(false);

  useEffect(() => {
    api.config().then(setConfig).catch(() => setConfig(null));
  }, []);

  const startEdit = (key: "fred" | "finnhub") => {
    setEditing(key);
    setError(null);
    setSaved(false);
    setInputValue("");
  };

  const cancelEdit = () => {
    setEditing(null);
    setInputValue("");
    setError(null);
    setSaved(false);
  };

  const save = async () => {
    const val = inputValue.trim();
    if (!val) {
      setError("API key cannot be empty.");
      return;
    }
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const body = editing === "fred"
        ? { fredApiKey: val }
        : { finnhubApiKey: val };
      const res = await api.updateConfig(body);
      setConfig(res);
      setSaved(true);
      setEditing(null);
      if (res.restartRequired) {
        setRestartBanner(true);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save.");
    } finally {
      setSaving(false);
    }
  };

  const masked = (v: string | null | undefined) => v ?? <span className="text-text-muted">Not set</span>;

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-text-secondary">API Keys</h2>
        {restartBanner && (
          <span className="text-xs text-warning bg-warning/10 rounded px-2 py-0.5 font-medium">
            Restart required to apply changes
          </span>
        )}
      </div>
      <p className="text-xs text-text-muted mb-4">
        Keys are validated before saving and written to <code className="bg-surface-alt px-1 rounded">.env</code>.
        Recreate the Docker container for changes to take effect.
      </p>

      {/* FRED */}
      <div className="flex items-center justify-between py-2 border-b border-border/50">
        <div>
          <span className="text-sm font-medium text-text-primary">FRED</span>
          <span className="text-xs text-text-muted ml-2">api.stlouisfed.org</span>
        </div>
        <div className="flex items-center gap-3">
          {editing === "fred" ? (
            <>
              <input
                type="text"
                placeholder="Paste FRED API key…"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                disabled={saving}
                className="w-64 px-2 py-1 text-xs font-mono border border-border rounded bg-surface text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
              />
              <button
                onClick={save}
                disabled={saving}
                className="px-2 py-1 text-xs font-medium rounded bg-success text-white hover:bg-success/80 disabled:opacity-50"
              >{saving ? "Validating…" : "Save"}</button>
              <button
                onClick={cancelEdit}
                disabled={saving}
                className="px-2 py-1 text-xs font-medium rounded border border-border text-text-secondary hover:text-text-primary"
              >Cancel</button>
            </>
          ) : (
            <>
              <span className="text-xs font-mono text-text-primary">
                {masked(config?.fredApiKey)}
              </span>
              <button
                onClick={() => startEdit("fred")}
                className="px-2 py-0.5 text-xs font-medium rounded border border-border text-text-secondary hover:text-text-primary hover:bg-surface-alt transition-colors"
              >Edit</button>
            </>
          )}
        </div>
      </div>
      {editing === "fred" && error && (
        <div className="text-xs text-danger mt-1">{error}</div>
      )}
      {editing === "fred" && saved && (
        <div className="text-xs text-success mt-1">✓ Key saved</div>
      )}

      {/* Finnhub */}
      <div className="flex items-center justify-between py-2">
        <div>
          <span className="text-sm font-medium text-text-primary">Finnhub</span>
          <span className="text-xs text-text-muted ml-2">finnhub.io</span>
        </div>
        <div className="flex items-center gap-3">
          {editing === "finnhub" ? (
            <>
              <input
                type="text"
                placeholder="Paste Finnhub API key…"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                disabled={saving}
                className="w-64 px-2 py-1 text-xs font-mono border border-border rounded bg-surface text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
              />
              <button
                onClick={save}
                disabled={saving}
                className="px-2 py-1 text-xs font-medium rounded bg-success text-white hover:bg-success/80 disabled:opacity-50"
              >{saving ? "Validating…" : "Save"}</button>
              <button
                onClick={cancelEdit}
                disabled={saving}
                className="px-2 py-1 text-xs font-medium rounded border border-border text-text-secondary hover:text-text-primary"
              >Cancel</button>
            </>
          ) : (
            <>
              <span className="text-xs font-mono text-text-primary">
                {masked(config?.finnhubApiKey)}
              </span>
              <button
                onClick={() => startEdit("finnhub")}
                className="px-2 py-0.5 text-xs font-medium rounded border border-border text-text-secondary hover:text-text-primary hover:bg-surface-alt transition-colors"
              >Edit</button>
            </>
          )}
        </div>
      </div>
      {editing === "finnhub" && error && (
        <div className="text-xs text-danger mt-1">{error}</div>
      )}
      {editing === "finnhub" && saved && (
        <div className="text-xs text-success mt-1">✓ Key saved</div>
      )}
    </Card>
  );
}

function BulkDataSection() {
  const [bulk, setBulk] = useState<Record<string, BulkDatasetStatus> | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api.bulkDataStatus();
      setBulk(r.datasets);
    } catch { setBulk(null); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const doRefresh = async () => {
    setRefreshing(true);
    try {
      await api.bulkDataRefresh();
      await load();
    } catch { /* ignore */ }
    finally { setRefreshing(false); }
  };

  const labels: Record<string, string> = {
    worldbank: "World Bank",
    famafrench: "Fama-French",
    imf_weo: "IMF WEO",
    bis: "BIS",
    factbook: "OpenFactbook",
    reinhart_rogoff: "Reinhart & Rogoff",
    factbook_profiles: "CIA Factbook",
  };

  const descriptions: Record<string, string> = {
    worldbank: "GDP growth, inflation, unemployment, debt/GDP, current account, GDP/capita — ~200 countries, 1960–2024",
    famafrench: "3-factor model: Mkt-RF, SMB, HML, RF — monthly, 1926–present",
    imf_weo: "GDP growth, inflation, unemployment, debt/GDP, current account, GDP/capita — ~190 countries with forecasts",
    bis: "CPI, policy rates, exchange rates, credit gaps, property prices, cross-border banking claims — annual/quarterly",
    factbook: "REST Countries JSON — ~250 countries with ISO codes, flags, languages, currencies",
    reinhart_rogoff: "Historical sovereign default dataset — 70+ countries, 1800–2019, external + domestic default flags",
    factbook_profiles: "CIA World Factbook country profiles — ~260 countries with Introduction, Geography, People, Government, Economy, Military & more",
  };

  if (!bulk || !Object.keys(bulk).length) return null;

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-text-secondary">Bulk Data Downloads</h2>
        <button
          onClick={doRefresh}
          disabled={refreshing}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
            refreshing
              ? "border-accent/30 bg-accent/10 text-accent cursor-wait"
              : "border-border text-text-secondary hover:text-text-primary hover:bg-surface-alt"
          }`}
        >{refreshing ? "Downloading…" : "Refresh"}</button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-text-secondary border-b border-border">
              <th className="text-left py-2 px-3 font-medium">Source</th>
              <th className="text-right py-2 px-3 font-medium">Rows</th>
              <th className="text-right py-2 px-3 font-medium">Size</th>
              <th className="text-right py-2 px-3 font-medium">Last OK</th>
              <th className="text-left py-2 px-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(bulk).map(([key, ds]) => (
              <tr key={key} className="border-b border-border/50">
                <td className="py-2 px-3 text-xs">
                  <div className="font-mono text-text-primary">{labels[key] || key}</div>
                  <div className="text-text-muted mt-0.5 leading-relaxed">{descriptions[key] || ""}</div>
                </td>
                <td className="py-2 px-3 text-right font-mono text-xs">{ds.rows?.toLocaleString() ?? "—"}</td>
                <td className="py-2 px-3 text-right font-mono text-xs">{ds.size_kb != null ? `${ds.size_kb >= 1024 ? (ds.size_kb / 1024).toFixed(1) + " MB" : ds.size_kb + " KB"}` : "—"}</td>
                <td className="py-2 px-3 text-right font-mono text-xs text-text-muted">{ds.last_ok ? new Date(ds.last_ok).toLocaleDateString() : "never"}</td>
                <td className="py-2 px-3 font-mono text-xs">
                  {ds.error
                    ? <span className="text-danger" title={ds.error}>⚠ Failed</span>
                    : ds.rows
                      ? <span className="text-success">✓ OK</span>
                      : <span className="text-text-muted">No data</span>
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-text-muted mt-3">Downloads run weekly (Sun 4:00 UTC) · falls back to API on failure</p>
    </Card>
  );
}
