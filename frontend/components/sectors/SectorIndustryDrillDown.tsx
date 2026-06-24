"use client";

import Link from "next/link";
import type { IndustryGroup } from "@/lib/types";

interface Props {
  sector: string;
  data: IndustryGroup[] | null;
  loading: boolean;
}

export function SectorIndustryDrillDown({ sector, data, loading }: Props) {
  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="animate-pulse bg-surface-alt rounded-lg h-16" />
        ))}
      </div>
    );
  }
  if (!data) return null;

  return (
    <div>
      <h3 className="text-sm font-semibold text-text-secondary mb-3">
        Industries in {sector}
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {data.map((group) => (
          <div key={group.industry} className="rounded-lg border border-border p-3 bg-surface">
            <div className="text-xs font-semibold text-text-primary mb-2">{group.industry}</div>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {group.stocks.map((s) => (
                <Link
                  key={s.symbol}
                  href={`/markets?ticker=${encodeURIComponent(s.symbol)}`}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-surface-alt hover:bg-accent/10 transition-colors text-xs font-mono"
                >
                  <span className="text-text-primary">{s.symbol}</span>
                  {s.change1d !== null && (
                    <span className={s.change1d >= 0 ? "text-success" : "text-danger"}>
                      {s.change1d >= 0 ? "+" : ""}{s.change1d.toFixed(1)}%
                    </span>
                  )}
                </Link>
              ))}
            </div>
            <Link
              href={`/screener?sector=${encodeURIComponent(sector)}`}
              className="text-xs text-accent hover:underline"
            >
              See all in {sector} →
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
