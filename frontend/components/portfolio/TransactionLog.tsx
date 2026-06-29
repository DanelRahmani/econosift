"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { Transaction, PnLSummary } from "@/lib/types";

const LS_KEY = "axiom_transactions";

function loadTransactions(): Transaction[] {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Transaction[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveTransactions(txs: Transaction[]) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(txs));
  } catch {
    // ignore
  }
}

function generateId(): number {
  return Date.now() * 1000 + Math.floor(Math.random() * 1000);
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

export function TransactionLog() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  // Form state
  const [ticker, setTicker] = useState("");
  const [date, setDate] = useState(todayStr());
  const [type, setType] = useState<"buy" | "sell">("buy");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [fees, setFees] = useState("0");

  // P&L state
  const [pnl, setPnl] = useState<PnLSummary | null>(null);
  const [pnlLoading, setPnlLoading] = useState(false);
  const [pnlError, setPnlError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const [importMsg, setImportMsg] = useState<string | null>(null);

  useEffect(() => {
    setTransactions(loadTransactions());
  }, []);

  function resetForm() {
    setTicker("");
    setDate(todayStr());
    setType("buy");
    setQuantity("");
    setPrice("");
    setFees("0");
    setEditingId(null);
  }

  function handleSubmit() {
    const q = parseFloat(quantity);
    const p = parseFloat(price);
    const f = parseFloat(fees) || 0;
    if (!ticker.trim() || !date || isNaN(q) || q <= 0 || isNaN(p) || p <= 0) return;

    const tx: Transaction = {
      id: editingId ?? generateId(),
      ticker: ticker.trim().toUpperCase(),
      date,
      type,
      quantity: q,
      price: p,
      fees: f,
    };

    let updated: Transaction[];
    if (editingId) {
      updated = transactions.map((t) => (t.id === editingId ? tx : t));
    } else {
      updated = [...transactions, tx];
    }

    // Sort by date desc
    updated.sort((a, b) => b.date.localeCompare(a.date) || (b.id ?? 0) - (a.id ?? 0));

    setTransactions(updated);
    saveTransactions(updated);
    resetForm();
    setShowForm(false);
    setPnl(null); // invalidate P&L cache
  }

  function handleEdit(tx: Transaction) {
    setTicker(tx.ticker);
    setDate(tx.date);
    setType(tx.type);
    setQuantity(String(tx.quantity));
    setPrice(String(tx.price));
    setFees(String(tx.fees ?? 0));
    setEditingId(tx.id ?? null);
    setShowForm(true);
  }

  function handleDelete(id: number | undefined) {
    if (id === undefined) return;
    const updated = transactions.filter((t) => t.id !== id);
    setTransactions(updated);
    saveTransactions(updated);
    setPnl(null);
  }

  async function handleSync() {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const res = await api.syncTransactions(transactions);
      setSyncMsg(`Synced ${res.saved} transactions to server.`);
    } catch {
      setSyncMsg("Sync failed — server may be unavailable.");
    } finally {
      setSyncing(false);
    }
  }

  async function handleServerLoad() {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const res = await api.fetchTransactions();
      if (res.transactions.length > 0) {
        setTransactions(res.transactions);
        saveTransactions(res.transactions);
        setSyncMsg(`Loaded ${res.transactions.length} transactions from server.`);
      } else {
        setSyncMsg("No transactions found on server.");
      }
    } catch {
      setSyncMsg("Failed to load from server.");
    } finally {
      setSyncing(false);
    }
  }

  async function handleComputePnl() {
    if (transactions.length === 0) return;
    setPnlLoading(true);
    setPnlError(null);
    try {
      // Gather unique tickers
      const tickers = [...new Set(transactions.map((t) => t.ticker))];
      // Try to get current prices from server; fallback to latest transaction price
      const priceMap: Record<string, number> = {};
      for (const t of transactions) {
        if (!priceMap[t.ticker]) {
          priceMap[t.ticker] = t.price;
        }
      }
      // Use the backend PnL endpoint if available, else compute locally
      try {
        const result = await api.computePnL(transactions, priceMap);
        setPnl(result);
      } catch {
        // Fallback: compute simple P&L locally
        computeLocalPnl();
      }
    } catch (e) {
      setPnlError("Failed to compute P&L.");
    } finally {
      setPnlLoading(false);
    }
  }

  function computeLocalPnl() {
    // Group by ticker, compute simple cost basis
    const byTicker: Record<string, { qty: number; cost: number; realized: number }> = {};
    for (const t of transactions) {
      const tk = t.ticker;
      if (!byTicker[tk]) byTicker[tk] = { qty: 0, cost: 0, realized: 0 };
      if (t.type === "buy") {
        byTicker[tk].qty += t.quantity;
        byTicker[tk].cost += t.quantity * t.price + (t.fees ?? 0);
      } else {
        const avgCost = byTicker[tk].qty > 0 ? byTicker[tk].cost / byTicker[tk].qty : 0;
        const sellQty = Math.min(t.quantity, byTicker[tk].qty);
        byTicker[tk].realized += sellQty * (t.price - avgCost) - (t.fees ?? 0);
        byTicker[tk].qty -= sellQty;
        byTicker[tk].cost -= sellQty * avgCost;
      }
    }

    const items = Object.entries(byTicker).map(([ticker, data]) => ({
      ticker,
      quantity: data.qty,
      cost_basis: data.cost,
      avg_cost: data.qty > 0 ? data.cost / data.qty : 0,
      market_value: data.qty * (transactions.find((t) => t.ticker === ticker)?.price ?? 0),
      unrealized_pnl: 0,
      realized_pnl: data.realized,
      total_return_pct: data.cost > 0 ? (data.realized / data.cost) * 100 : 0,
    }));

    const total_cb = items.reduce((s, i) => s + i.cost_basis, 0);
    const total_real = items.reduce((s, i) => s + i.realized_pnl, 0);

    setPnl({
      items,
      total_cost_basis: total_cb,
      total_market_value: items.reduce((s, i) => s + i.market_value, 0),
      total_unrealized_pnl: items.reduce((s, i) => s + i.unrealized_pnl, 0),
      total_realized_pnl: total_real,
      total_return_pct: total_cb > 0 ? (total_real / total_cb) * 100 : 0,
    });
  }

  function exportJSON() {
    const blob = new Blob([JSON.stringify(transactions, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `axiom_transactions_${todayStr()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportMsg(null);
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(reader.result as string);
        if (Array.isArray(parsed) && parsed.every((t: unknown) =>
          typeof t === "object" && t !== null && "ticker" in t && "date" in t && "type" in t
        )) {
          setTransactions(parsed as Transaction[]);
          saveTransactions(parsed as Transaction[]);
          setImportMsg(`Imported ${parsed.length} transactions.`);
          setPnl(null);
        } else {
          setImportMsg("Invalid file format.");
        }
      } catch {
        setImportMsg("Failed to parse file.");
      }
    };
    reader.readAsText(file);
  }

  const totalBuys = transactions.filter((t) => t.type === "buy").length;
  const totalSells = transactions.filter((t) => t.type === "sell").length;

  return (
    <div className="space-y-4">
      {/* KPI strip */}
      <div className="flex gap-3 flex-wrap">
        <div className="bg-surface-alt rounded-lg p-3 min-w-[100px]">
          <div className="text-xs text-text-muted">Transactions</div>
          <div className="text-xl font-bold tabular-nums">{transactions.length}</div>
        </div>
        <div className="bg-surface-alt rounded-lg p-3 min-w-[100px]">
          <div className="text-xs text-text-muted">Buys</div>
          <div className="text-xl font-bold tabular-nums text-green-500">{totalBuys}</div>
        </div>
        <div className="bg-surface-alt rounded-lg p-3 min-w-[100px]">
          <div className="text-xs text-text-muted">Sells</div>
          <div className="text-xl font-bold tabular-nums text-red-500">{totalSells}</div>
        </div>
        {pnl && (
          <>
            <div className="bg-surface-alt rounded-lg p-3 min-w-[120px]">
              <div className="text-xs text-text-muted">Realized P&L</div>
              <div className={`text-xl font-bold tabular-nums ${pnl.total_realized_pnl >= 0 ? "text-green-500" : "text-red-500"}`}>
                ${pnl.total_realized_pnl.toFixed(2)}
              </div>
            </div>
            <div className="bg-surface-alt rounded-lg p-3 min-w-[120px]">
              <div className="text-xs text-text-muted">Cost Basis</div>
              <div className="text-xl font-bold tabular-nums">${pnl.total_cost_basis.toFixed(2)}</div>
            </div>
          </>
        )}
      </div>

      {/* Action bar */}
      <div className="flex flex-wrap gap-2 items-center">
        <button
          onClick={() => { resetForm(); setShowForm(!showForm); }}
          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-accent text-white hover:opacity-90 transition-opacity"
        >
          {showForm ? "Cancel" : "+ Add Transaction"}
        </button>
        <button
          onClick={handleComputePnl}
          disabled={transactions.length === 0 || pnlLoading}
          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-surface-alt border border-border text-text-secondary hover:text-text-primary disabled:opacity-50"
        >
          {pnlLoading ? "Computing…" : "Compute P&L"}
        </button>
        <button
          onClick={handleSync}
          disabled={syncing || transactions.length === 0}
          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-surface-alt border border-border text-text-secondary hover:text-text-primary disabled:opacity-50"
        >
          {syncing ? "Syncing…" : "Save to Server"}
        </button>
        <button
          onClick={handleServerLoad}
          disabled={syncing}
          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-surface-alt border border-border text-text-secondary hover:text-text-primary disabled:opacity-50"
        >
          Load from Server
        </button>
        <button
          onClick={exportJSON}
          disabled={transactions.length === 0}
          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-surface-alt border border-border text-text-secondary hover:text-text-primary disabled:opacity-50"
        >
          Export JSON
        </button>
        <label className="px-3 py-1.5 text-xs font-medium rounded-lg bg-surface-alt border border-border text-text-secondary hover:text-text-primary cursor-pointer">
          Import JSON
          <input type="file" accept=".json" onChange={handleImport} className="hidden" />
        </label>
      </div>

      {syncMsg && (
        <div className="text-xs text-text-muted bg-surface-alt rounded-lg px-3 py-2">{syncMsg}</div>
      )}
      {importMsg && (
        <div className="text-xs text-accent bg-accent/10 rounded-lg px-3 py-2">{importMsg}</div>
      )}

      {/* Add/Edit form */}
      {showForm && (
        <div className="rounded-xl border border-border bg-surface p-4 space-y-3">
          <h4 className="text-sm font-semibold">{editingId ? "Edit Transaction" : "New Transaction"}</h4>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className="text-xs text-text-muted block mb-1">Ticker</label>
              <input
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                placeholder="AAPL"
                className="w-full px-2 py-1.5 text-sm rounded-lg bg-surface-alt border border-border text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
              />
            </div>
            <div>
              <label className="text-xs text-text-muted block mb-1">Date</label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-full px-2 py-1.5 text-sm rounded-lg bg-surface-alt border border-border text-text-primary focus:outline-none focus:border-accent"
              />
            </div>
            <div>
              <label className="text-xs text-text-muted block mb-1">Type</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value as "buy" | "sell")}
                className="w-full px-2 py-1.5 text-sm rounded-lg bg-surface-alt border border-border text-text-primary focus:outline-none focus:border-accent"
              >
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-text-muted block mb-1">Quantity</label>
              <input
                type="number"
                step="any"
                min="0.0001"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="10"
                className="w-full px-2 py-1.5 text-sm rounded-lg bg-surface-alt border border-border text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
              />
            </div>
            <div>
              <label className="text-xs text-text-muted block mb-1">Price</label>
              <input
                type="number"
                step="any"
                min="0.01"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder="150.00"
                className="w-full px-2 py-1.5 text-sm rounded-lg bg-surface-alt border border-border text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
              />
            </div>
            <div>
              <label className="text-xs text-text-muted block mb-1">Fees</label>
              <input
                type="number"
                step="any"
                min="0"
                value={fees}
                onChange={(e) => setFees(e.target.value)}
                placeholder="0"
                className="w-full px-2 py-1.5 text-sm rounded-lg bg-surface-alt border border-border text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
              />
            </div>
          </div>
          <button
            onClick={handleSubmit}
            className="px-4 py-1.5 text-xs font-medium rounded-lg bg-accent text-white hover:opacity-90"
          >
            {editingId ? "Update" : "Add"}
          </button>
        </div>
      )}

      {/* P&L detail */}
      {pnlError && (
        <div className="text-xs text-red-500 bg-red-500/10 rounded-lg px-3 py-2">{pnlError}</div>
      )}
      {pnl && pnl.items.length > 0 && (
        <div className="rounded-xl border border-border bg-surface p-4">
          <h4 className="text-sm font-semibold mb-3">P&L Summary</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-text-muted text-xs">
                  <th className="text-left py-2 pr-3">Ticker</th>
                  <th className="text-right py-2 pr-3">Qty</th>
                  <th className="text-right py-2 pr-3">Avg Cost</th>
                  <th className="text-right py-2 pr-3">Cost Basis</th>
                  <th className="text-right py-2 pr-3">Realized P&L</th>
                  <th className="text-right py-2">Return</th>
                </tr>
              </thead>
              <tbody>
                {pnl.items.map((item) => (
                  <tr key={item.ticker} className="border-b border-border/50 hover:bg-surface-alt/50">
                    <td className="py-2 pr-3 font-mono font-medium">{item.ticker}</td>
                    <td className="py-2 pr-3 text-right text-text-secondary">{item.quantity.toFixed(4)}</td>
                    <td className="py-2 pr-3 text-right text-text-secondary">${item.avg_cost.toFixed(2)}</td>
                    <td className="py-2 pr-3 text-right text-text-secondary">${item.cost_basis.toFixed(2)}</td>
                    <td className={`py-2 pr-3 text-right font-medium ${item.realized_pnl >= 0 ? "text-green-500" : "text-red-500"}`}>
                      ${item.realized_pnl.toFixed(2)}
                    </td>
                    <td className={`py-2 text-right font-medium ${item.total_return_pct >= 0 ? "text-green-500" : "text-red-500"}`}>
                      {item.total_return_pct >= 0 ? "+" : ""}{item.total_return_pct.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-border font-semibold text-xs">
                  <td className="py-2 pr-3">Total</td>
                  <td />
                  <td />
                  <td className="py-2 pr-3 text-right">${pnl.total_cost_basis.toFixed(2)}</td>
                  <td className={`py-2 pr-3 text-right ${pnl.total_realized_pnl >= 0 ? "text-green-500" : "text-red-500"}`}>
                    ${pnl.total_realized_pnl.toFixed(2)}
                  </td>
                  <td className={`py-2 text-right ${pnl.total_return_pct >= 0 ? "text-green-500" : "text-red-500"}`}>
                    {pnl.total_return_pct >= 0 ? "+" : ""}{pnl.total_return_pct.toFixed(2)}%
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {/* Transaction history table */}
      {transactions.length > 0 && (
        <div className="rounded-xl border border-border bg-surface p-4">
          <h4 className="text-sm font-semibold mb-3">Transaction History</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-text-muted text-xs">
                  <th className="text-left py-2 pr-3">Date</th>
                  <th className="text-left py-2 pr-3">Ticker</th>
                  <th className="text-center py-2 pr-3">Type</th>
                  <th className="text-right py-2 pr-3">Qty</th>
                  <th className="text-right py-2 pr-3">Price</th>
                  <th className="text-right py-2 pr-3">Total</th>
                  <th className="text-right py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((tx) => (
                  <tr key={tx.id} className="border-b border-border/50 hover:bg-surface-alt/50">
                    <td className="py-2 pr-3 text-text-secondary">{tx.date}</td>
                    <td className="py-2 pr-3 font-mono font-medium">{tx.ticker}</td>
                    <td className="py-2 pr-3 text-center">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${tx.type === "buy" ? "bg-green-500/10 text-green-500" : "bg-red-500/10 text-red-500"}`}>
                        {tx.type.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-right text-text-secondary">{tx.quantity.toFixed(4)}</td>
                    <td className="py-2 pr-3 text-right text-text-secondary">${tx.price.toFixed(2)}</td>
                    <td className="py-2 pr-3 text-right text-text-secondary">
                      ${(tx.quantity * tx.price + (tx.fees ?? 0)).toFixed(2)}
                    </td>
                    <td className="py-2 text-right">
                      <button
                        onClick={() => handleEdit(tx)}
                        className="px-2 py-0.5 text-[10px] rounded bg-surface-alt text-text-muted hover:text-text-primary mr-1"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(tx.id)}
                        className="px-2 py-0.5 text-[10px] rounded bg-red-500/10 text-red-500 hover:bg-red-500/20"
                      >
                        Del
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {transactions.length === 0 && (
        <div className="text-center py-16 text-text-muted text-sm">
          No transactions yet. Add your first buy or sell above.
        </div>
      )}
    </div>
  );
}
