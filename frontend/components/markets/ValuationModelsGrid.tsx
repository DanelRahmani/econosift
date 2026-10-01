"use client";

import { Card } from "@/components/ui";
import { fmtPrice, fmtPct, currencySymbol } from "@/lib/format";
import type { ValuationCore, ValModel } from "@/lib/types";

// ── Helpers ───────────────────────────────────────────────────────────────────

function upsidePct(value: number, spot: number): number {
  return ((value - spot) / spot) * 100;
}

// ── Single model card ─────────────────────────────────────────────────────────

interface ModelCardProps {
  model: ValModel;
  spot: number | null;
  sym: string;
  fullWidth?: boolean;
  label?: string; // override display label
  prov: string; // provenance key of this model in the /full response
}

function ModelCard({ model, spot, sym, fullWidth = false, label, prov }: ModelCardProps) {
  const displayLabel = label ?? model.model;

  if (model.locked) {
    return (
      <div
        className={`rounded-xl border border-border bg-surface-alt p-4 opacity-60 flex flex-col gap-1 ${fullWidth ? "col-span-full" : ""}`}
        data-prov={prov}
        data-prov-ctx={displayLabel}
      >
        <div className="flex items-center gap-1.5">
          {/* lock glyph */}
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-3.5 w-3.5 text-text-muted shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            aria-hidden="true"
          >
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          <span className="text-xs font-medium text-text-muted truncate">{displayLabel}</span>
        </div>
        <p className="text-xs text-text-muted mt-1 leading-snug">
          {model.reason ?? "Insufficient data"}
        </p>
      </div>
    );
  }

  const value = model.value;
  const sym_ = sym;

  // value null but not locked → show dash
  if (value === null) {
    return (
      <div
        className={`rounded-xl border border-border bg-surface-alt p-4 flex flex-col gap-1 ${fullWidth ? "col-span-full" : ""}`}
        data-prov={prov}
        data-prov-ctx={displayLabel}
      >
        <p className="text-xs text-text-muted truncate">{displayLabel}</p>
        <p className="text-2xl font-mono font-semibold text-text-primary">—</p>
      </div>
    );
  }

  const upside = spot !== null && spot > 0 ? upsidePct(value, spot) : null;
  const upsideColor =
    upside === null
      ? "text-text-secondary"
      : upside > 0
      ? "text-success"
      : "text-danger";
  const arrow = upside === null ? null : upside > 0 ? "▲" : "▼";

  // Bar: percentage of value relative to spot, clamped 0–200%
  const barRatio =
    spot !== null && spot > 0
      ? Math.min(Math.max(value / spot, 0), 2) / 2 // normalize 0..2x → 0..1
      : null;

  return (
    <div
      className={`rounded-xl border border-border bg-surface-alt p-4 flex flex-col gap-1 ${fullWidth ? "col-span-full" : ""}`}
      data-prov={prov}
      data-prov-ctx={displayLabel}
    >
      <p className="text-xs text-text-muted truncate">{displayLabel}</p>
      <p className="text-2xl font-mono font-semibold text-text-primary">
        {fmtPrice(value, sym_)}
      </p>

      {upside !== null && (
        <p className={`text-sm font-semibold ${upsideColor}`}>
          {arrow} {fmtPct(Math.abs(upside))}
          <span className="text-xs font-normal text-text-muted ml-1">vs spot</span>
        </p>
      )}

      {/* Faint progress bar: position of model value relative to spot */}
      {barRatio !== null && (
        <div className="mt-2 h-1 w-full rounded-full bg-border overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              upside !== null && upside > 0 ? "bg-success/60" : "bg-danger/60"
            }`}
            style={{ width: `${barRatio * 100}%` }}
          />
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function ValuationModelsGrid({ valuation }: { valuation: ValuationCore }) {
  const sym = currencySymbol(valuation.currency);
  const spot = valuation.spotPrice;

  return (
    <div className="space-y-4">
      {/* ── 8-model 2×4 grid ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {valuation.models.map((m) => (
          <ModelCard key={m.model} model={m} spot={spot} sym={sym} prov={`valuation.models.${m.model}`} />
        ))}
      </div>

      {/* ── CAPM Implied (full-width row below the grid) ─────────────────────── */}
      <div className="grid grid-cols-1">
        <ModelCard
          model={valuation.capmImplied}
          spot={spot}
          sym={sym}
          label="CAPM Implied Fair Value"
          prov="valuation.capmImplied"
        />
      </div>

      {/* ── Caption + legend ────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
        <p className="text-xs text-text-muted">
          Fair value per share by model · as of {valuation.asOf}
        </p>
        <div className="flex items-center gap-1.5">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-3 w-3 text-text-muted shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            aria-hidden="true"
          >
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          <span className="text-xs text-text-muted">
            Locked — insufficient data to compute this model
          </span>
        </div>
      </div>
    </div>
  );
}
