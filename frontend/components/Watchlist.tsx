"use client";

import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import type { Quote } from "@/lib/types";
import { Card } from "@/components/ui";
import { fmtPct, fmtPrice, currencySymbol } from "@/lib/format";

const STORAGE_KEY = "axiom-watchlist";
const ALERTS_KEY = "axiom-watchlist-alerts";

interface Props {
  onSelect?: (ticker: string) => void;
}

interface Alert {
  price: number;
  dir: "above" | "below";
  triggered: boolean;
}

export function Watchlist({ onSelect }: Props) {
  const [tickers, setTickers] = useState<string[]>([]);
  const [quotes, setQuotes] = useState<Record<string, Quote | null>>({});
  const [alerts, setAlerts] = useState<Record<string, Alert>>({});
  const [input, setInput] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<{ price: string; dir: "above" | "below" }>({ price: "", dir: "above" });
  const alertsRef = useRef(alerts);
  alertsRef.current = alerts;

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      if (Array.isArray(saved)) setTickers(saved);
      const savedAlerts = JSON.parse(localStorage.getItem(ALERTS_KEY) || "{}");
      if (savedAlerts && typeof savedAlerts === "object") setAlerts(savedAlerts);
    } catch {}
  }, []);

  function persistAlerts(next: Record<string, Alert>) {
    setAlerts(next);
    try { localStorage.setItem(ALERTS_KEY, JSON.stringify(next)); } catch {}
  }

  function notify(ticker: string, a: Alert, price: number) {
    const msg = `${ticker} is ${a.dir} ${a.price} — now ${price.toFixed(2)}`;
    try {
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification("Axiom price alert", { body: msg });
      }
    } catch {}
  }

  // Check alerts whenever a quote updates.
  function checkAlert(ticker: string, q: Quote | null) {
    if (!q || q.price == null) return;
    const a = alertsRef.current[ticker];
    if (!a || a.triggered) return;
    const hit = a.dir === "above" ? q.price >= a.price : q.price <= a.price;
    if (hit) {
      notify(ticker, a, q.price);
      persistAlerts({ ...alertsRef.current, [ticker]: { ...a, triggered: true } });
    }
  }

  const tickersKey = tickers.join(",");
  useEffect(() => {
    if (!tickers.length) return;
    let active = true;
    tickers.forEach(async (t) => {
      try {
        const q = await api.quote(t);
        if (active) { setQuotes((prev) => ({ ...prev, [t]: q })); checkAlert(t, q); }
      } catch {
        if (active) setQuotes((prev) => ({ ...prev, [t]: null }));
      }
    });
    return () => { active = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tickersKey]);

  function add() {
    const sym = input.trim().toUpperCase();
    if (!sym || tickers.includes(sym)) { setInput(""); return; }
    const next = [...tickers, sym];
    setTickers(next);
    setInput("");
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch {}
  }

  function remove(sym: string) {
    const next = tickers.filter((t) => t !== sym);
    setTickers(next);
    setQuotes((prev) => { const r = { ...prev }; delete r[sym]; return r; });
    const na = { ...alerts }; delete na[sym]; persistAlerts(na);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch {}
  }

  function openAlertEditor(sym: string) {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission().catch(() => {});
    }
    const existing = alerts[sym];
    const price = quotes[sym]?.price;
    setDraft({
      price: existing ? String(existing.price) : price != null ? price.toFixed(2) : "",
      dir: existing?.dir ?? "above",
    });
    setEditing(sym);
  }

  function saveAlert(sym: string) {
    const p = parseFloat(draft.price);
    if (Number.isNaN(p)) { setEditing(null); return; }
    persistAlerts({ ...alerts, [sym]: { price: p, dir: draft.dir, triggered: false } });
    setEditing(null);
  }

  function clearAlert(sym: string) {
    const na = { ...alerts }; delete na[sym]; persistAlerts(na);
    setEditing(null);
  }

  return (
    <Card>
      <h2 className="text-sm font-semibold mb-3 text-text-secondary">Watchlist</h2>
      <div className="flex gap-2 mb-3">
        <input
          className="input flex-1 text-sm"
          placeholder="Add ticker (e.g. NVDA)"
          value={input}
          onChange={(e) => setInput(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === "Enter" && add()}
        />
        <button
          onClick={add}
          className="px-3 py-1.5 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent/80 transition-colors"
        >
          +
        </button>
      </div>
      {!tickers.length && (
        <p className="text-text-muted text-sm">No tickers — type a symbol above and press Enter or +.</p>
      )}
      <div className="space-y-0">
        {tickers.map((t) => {
          const q = quotes[t];
          const up = (q?.changePercent ?? 0) >= 0;
          const alert = alerts[t];
          return (
            <div key={t} className="border-b border-border/40 last:border-0">
              <div className="flex items-center justify-between py-2 group">
                <button
                  onClick={() => onSelect?.(t)}
                  className="text-left flex-1 min-w-0 cursor-pointer"
                  title={`Add ${t} to chart`}
                >
                  <div className="font-mono text-sm font-semibold flex items-center gap-1.5">
                    {t}
                    {alert && (
                      <span className={`text-[10px] px-1 py-0.5 rounded ${
                        alert.triggered ? "bg-success/20 text-success" : "bg-accent/15 text-accent"
                      }`} title={`Alert ${alert.dir} ${alert.price}`}>
                        {alert.triggered ? "✓" : "🔔"} {alert.dir === "above" ? "≥" : "≤"}{alert.price}
                      </span>
                    )}
                  </div>
                  {q && <div className="text-xs text-text-muted truncate">{q.name}</div>}
                </button>
                <div className="flex items-center gap-2 ml-2 shrink-0">
                  <div className="text-right">
                    {q?.price != null && (
                      <div className="text-sm">{fmtPrice(q.price, currencySymbol(q.currency))}</div>
                    )}
                    {q?.changePercent != null && (
                      <div className={`text-xs font-medium ${up ? "text-success" : "text-danger"}`}>
                        {up ? "+" : ""}{fmtPct(q.changePercent)}
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => openAlertEditor(t)}
                    className={`opacity-0 group-hover:opacity-100 transition-opacity text-sm px-1 ${
                      alert ? "text-accent" : "text-text-muted hover:text-text-primary"
                    }`}
                    title="Set price alert"
                  >🔔</button>
                  <button
                    onClick={() => remove(t)}
                    className="text-text-muted hover:text-danger opacity-0 group-hover:opacity-100 transition-opacity text-lg leading-none px-1"
                    title="Remove from watchlist"
                  >×</button>
                </div>
              </div>
              {editing === t && (
                <div className="flex flex-wrap items-center gap-2 pb-3 pl-1">
                  <span className="text-xs text-text-muted">Alert when price</span>
                  <select
                    value={draft.dir}
                    onChange={(e) => setDraft((d) => ({ ...d, dir: e.target.value as "above" | "below" }))}
                    className="rounded-md bg-surface-alt border border-border px-2 py-1 text-xs"
                  >
                    <option value="above">rises to ≥</option>
                    <option value="below">falls to ≤</option>
                  </select>
                  <input
                    type="number" step="any" value={draft.price}
                    onChange={(e) => setDraft((d) => ({ ...d, price: e.target.value }))}
                    className="w-24 rounded-md bg-surface-alt border border-border px-2 py-1 text-xs font-mono"
                    placeholder="price"
                  />
                  <button onClick={() => saveAlert(t)} className="px-2.5 py-1 rounded-md text-xs font-medium bg-accent text-white hover:bg-accent/90">Save</button>
                  {alert && <button onClick={() => clearAlert(t)} className="px-2 py-1 rounded-md text-xs text-text-muted hover:text-danger">Clear</button>}
                  <button onClick={() => setEditing(null)} className="px-2 py-1 rounded-md text-xs text-text-muted">Cancel</button>
                </div>
              )}
            </div>
          );
        })}
      </div>
      {tickers.length > 0 && (
        <p className="text-xs text-text-muted mt-3">
          Alerts check on refresh and fire a browser notification. Re-open the Watchlist to re-check prices.
        </p>
      )}
    </Card>
  );
}
