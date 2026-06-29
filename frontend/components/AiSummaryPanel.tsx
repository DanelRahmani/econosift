"use client";

import { useState, useMemo } from "react";
import type { AiSummaryResponse } from "@/lib/types";
import { Card } from "@/components/ui";

const AVAILABLE_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"];

interface Option {
  key: string;
  label: string;
}

interface Props {
  summaryType: "company" | "macro" | "dashboard";
  title: string;
  /** Optional list of selectable items. When provided, clickable chips appear. */
  options?: Option[];
  /** Called with model, force flag, and the selected item keys. */
  onGenerate: (model: string, force: boolean, selected: string[]) => Promise<AiSummaryResponse>;
}

export function AiSummaryPanel({ summaryType, title, options, onGenerate }: Props) {
  const [model, setModel] = useState("gemini-2.0-flash");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AiSummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(() => {
    // Default: all options selected
    if (options && options.length > 0) return new Set(options.map((o) => o.key));
    return new Set();
  });

  const hasOptions = options && options.length > 0;

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  async function handleGenerate(force: boolean) {
    setLoading(true);
    setError(null);
    try {
      const sel = hasOptions ? Array.from(selected) : [];
      const r = await onGenerate(model, force, sel);
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate summary.");
    } finally {
      setLoading(false);
    }
  }

  const hasResult = result && !result.summary_text.startsWith("Error:");

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-text-secondary">{title}</h2>
        {/* Model selector */}
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          className="input max-w-[180px] text-xs"
          disabled={loading}
        >
          {AVAILABLE_MODELS.map((m) => (
            <option key={m} value={m} className="bg-surface">{m}</option>
          ))}
        </select>
      </div>

      {/* Clickable option chips */}
      {hasOptions && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {options.map((opt) => (
            <button
              key={opt.key}
              onClick={() => toggle(opt.key)}
              disabled={loading}
              className={`px-2 py-0.5 rounded-md text-xs font-medium border transition-colors ${
                selected.has(opt.key)
                  ? "bg-accent/15 border-accent/40 text-accent"
                  : "bg-surface-alt border-border text-text-muted hover:text-text-secondary"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex items-center gap-3 py-6">
          <div className="animate-spin rounded-full h-5 w-5 border-2 border-accent border-t-transparent" />
          <span className="text-text-muted text-sm">Generating summary…</span>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="space-y-2">
          <p className="text-danger text-sm">{error}</p>
          <button
            onClick={() => handleGenerate(true)}
            className="px-3 py-1 rounded text-xs font-medium border border-border text-text-secondary hover:text-text-primary"
          >
            Retry
          </button>
        </div>
      )}

      {/* Result */}
      {hasResult && !loading && (
        <div className="space-y-2">
          {/* Date/model badge */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-text-muted bg-surface-alt rounded px-2 py-0.5">
              Generated {new Date(result.created_at).toLocaleDateString()} · via {result.model_used}
            </span>
            {result.cached && (
              <span className="text-xs text-warning bg-warning/10 rounded px-2 py-0.5">
                cached
              </span>
            )}
          </div>
          {/* Summary text — preserve line breaks */}
          <div className="text-sm text-text-secondary whitespace-pre-line leading-relaxed">
            {result.summary_text}
          </div>
          {/* Regenerate button */}
          <button
            onClick={() => handleGenerate(true)}
            disabled={loading}
            className="px-3 py-1 rounded text-xs font-medium border border-border text-text-secondary hover:text-text-primary hover:bg-surface-alt transition-colors disabled:opacity-50"
          >
            Regenerate
          </button>
        </div>
      )}

      {/* Error within result text (Gemini returned an error string) */}
      {result && !hasResult && !loading && (
        <div className="space-y-2">
          <p className="text-danger text-sm">{result.summary_text}</p>
          <button
            onClick={() => handleGenerate(true)}
            className="px-3 py-1 rounded text-xs font-medium border border-border text-text-secondary hover:text-text-primary"
          >
            Retry
          </button>
        </div>
      )}

      {/* Idle state — no result yet */}
      {!result && !loading && !error && (
        <button
          onClick={() => handleGenerate(false)}
          className="px-3 py-1.5 rounded-lg text-sm font-medium border border-accent/40 bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
        >
          Generate Summary
        </button>
      )}
    </Card>
  );
}
