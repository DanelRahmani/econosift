"use client";

import { Skeleton } from "@/components/ui";
import { fmtNum, fmtPrice } from "@/lib/format";
import type { OptionsChain, OptionRow } from "@/lib/types";

interface Props {
  chain: OptionsChain | null;
  loading: boolean;
  showOTMOnly: boolean;
}

function fmt(v: number | null, digits = 2) {
  return v !== null ? fmtNum(v, digits) : "—";
}

function fmtIV(v: number | null) {
  return v !== null ? `${fmtNum(v, 1)}%` : "—";
}

function fmtVol(v: number | null) {
  if (v === null) return "—";
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return String(v);
}

export function ChainTable({ chain, loading, showOTMOnly }: Props) {
  if (loading) {
    return <Skeleton className="h-64 w-full rounded-xl" />;
  }

  if (!chain) {
    return (
      <div className="flex items-center justify-center h-40 text-text-muted text-sm">
        No chain data available. Select a ticker and expiry above.
      </div>
    );
  }

  const calls = showOTMOnly ? chain.calls.filter((r) => !r.itm) : chain.calls;
  const puts = showOTMOnly ? chain.puts.filter((r) => !r.itm) : chain.puts;

  // Build a merged set of strikes
  const allStrikes = Array.from(
    new Set([...calls.map((r) => r.strike), ...puts.map((r) => r.strike)])
  ).sort((a, b) => a - b);

  const callByStrike = new Map(calls.map((r) => [r.strike, r]));
  const putByStrike = new Map(puts.map((r) => [r.strike, r]));

  const spot = chain.spot;

  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full min-w-[820px] border-collapse">
        <thead>
          <tr className="bg-surface-alt text-[10px] text-text-muted uppercase tracking-wider">
            {/* Calls header */}
            <th className="py-2 px-2 text-right font-semibold">IV%</th>
            <th className="py-2 px-2 text-right font-semibold">Delta</th>
            <th className="py-2 px-2 text-right font-semibold">BS Price</th>
            <th className="py-2 px-2 text-right font-semibold">Bid</th>
            <th className="py-2 px-2 text-right font-semibold">Ask</th>
            <th className="py-2 px-2 text-right font-semibold">Volume</th>
            <th className="py-2 px-2 text-right font-semibold">OI</th>
            {/* Strike */}
            <th className="py-2 px-4 text-center font-bold text-text-primary border-x border-border bg-surface">
              Strike
            </th>
            {/* Puts header */}
            <th className="py-2 px-2 text-left font-semibold">OI</th>
            <th className="py-2 px-2 text-left font-semibold">Volume</th>
            <th className="py-2 px-2 text-left font-semibold">Bid</th>
            <th className="py-2 px-2 text-left font-semibold">Ask</th>
            <th className="py-2 px-2 text-left font-semibold">BS Price</th>
            <th className="py-2 px-2 text-left font-semibold">Delta</th>
            <th className="py-2 px-2 text-left font-semibold">IV%</th>
          </tr>
          <tr className="bg-surface-alt/60">
            <th colSpan={7} className="py-1 text-center text-[10px] font-semibold text-success">
              CALLS
            </th>
            <th className="border-x border-border" />
            <th colSpan={7} className="py-1 text-center text-[10px] font-semibold text-danger">
              PUTS
            </th>
          </tr>
        </thead>
        <tbody>
          {allStrikes.map((strike) => {
            const call = callByStrike.get(strike);
            const put = putByStrike.get(strike);
            const isAtm = Math.abs(strike - spot) / spot < 0.005;

            return (
              <tr
                key={strike}
                className={`border-b border-border ${
                  isAtm ? "ring-1 ring-accent/40" : ""
                }`}
              >
                {/* Call side */}
                {call ? (
                  <>
                    <td className={`py-1.5 px-2 text-right text-xs font-mono text-text-secondary ${call.itm ? "bg-green-950/30" : ""}`}>{fmtIV(call.iv)}</td>
                    <td className={`py-1.5 px-2 text-right text-xs font-mono text-text-secondary ${call.itm ? "bg-green-950/30" : ""}`}>{fmt(call.delta)}</td>
                    <td className={`py-1.5 px-2 text-right text-xs font-mono text-text-secondary ${call.itm ? "bg-green-950/30" : ""}`}>{call.bsPrice !== null ? fmtPrice(call.bsPrice) : "—"}</td>
                    <td className={`py-1.5 px-2 text-right text-xs font-mono ${call.itm ? "bg-green-950/30" : ""}`}>{call.bid !== null ? fmtPrice(call.bid) : "—"}</td>
                    <td className={`py-1.5 px-2 text-right text-xs font-mono ${call.itm ? "bg-green-950/30" : ""}`}>{call.ask !== null ? fmtPrice(call.ask) : "—"}</td>
                    <td className={`py-1.5 px-2 text-right text-xs font-mono text-text-muted ${call.itm ? "bg-green-950/30" : ""}`}>{fmtVol(call.volume)}</td>
                    <td className={`py-1.5 px-2 text-right text-xs font-mono text-text-muted ${call.itm ? "bg-green-950/30" : ""}`}>{fmtVol(call.openInterest)}</td>
                  </>
                ) : (
                  <td colSpan={7} className="py-1.5 px-2 text-center text-xs text-text-muted">—</td>
                )}

                {/* Strike */}
                <td className={`py-1.5 px-4 text-center text-xs font-bold border-x border-border ${isAtm ? "text-accent" : "text-text-primary"}`}>
                  {fmtPrice(strike)}
                  {isAtm && <span className="ml-1 text-[9px] text-accent">ATM</span>}
                </td>

                {/* Put side */}
                {put ? (
                  <>
                    <td className={`py-1.5 px-2 text-left text-xs font-mono text-text-muted ${put.itm ? "bg-red-950/30" : ""}`}>{fmtVol(put.openInterest)}</td>
                    <td className={`py-1.5 px-2 text-left text-xs font-mono text-text-muted ${put.itm ? "bg-red-950/30" : ""}`}>{fmtVol(put.volume)}</td>
                    <td className={`py-1.5 px-2 text-left text-xs font-mono ${put.itm ? "bg-red-950/30" : ""}`}>{put.bid !== null ? fmtPrice(put.bid) : "—"}</td>
                    <td className={`py-1.5 px-2 text-left text-xs font-mono ${put.itm ? "bg-red-950/30" : ""}`}>{put.ask !== null ? fmtPrice(put.ask) : "—"}</td>
                    <td className={`py-1.5 px-2 text-left text-xs font-mono text-text-secondary ${put.itm ? "bg-red-950/30" : ""}`}>{put.bsPrice !== null ? fmtPrice(put.bsPrice) : "—"}</td>
                    <td className={`py-1.5 px-2 text-left text-xs font-mono text-text-secondary ${put.itm ? "bg-red-950/30" : ""}`}>{fmt(put.delta)}</td>
                    <td className={`py-1.5 px-2 text-left text-xs font-mono text-text-secondary ${put.itm ? "bg-red-950/30" : ""}`}>{fmtIV(put.iv)}</td>
                  </>
                ) : (
                  <td colSpan={7} className="py-1.5 px-2 text-center text-xs text-text-muted">—</td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="px-4 py-2 text-[10px] text-text-muted border-t border-border bg-surface-alt/40">
        Options data delayed ~15min · Source: Yahoo Finance · ITM calls{" "}
        <span className="inline-block w-2 h-2 rounded-sm bg-green-700/60 align-middle" /> green ·
        ITM puts <span className="inline-block w-2 h-2 rounded-sm bg-red-800/60 align-middle" /> red
      </div>
    </div>
  );
}
