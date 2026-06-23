"use client";

import type { MacroResponse } from "@/lib/types";
import { Card } from "@/components/ui";
import { fmtNum } from "@/lib/format";

export function MacroDashboard({ data }: { data: MacroResponse }) {
  const cards = data.series
    .map((s) => {
      const pts = s.data;
      if (!pts.length) return null;
      const latest = pts[pts.length - 1];
      const prev = pts.length > 1 ? pts[pts.length - 2] : null;
      const delta = prev ? latest.value - prev.value : null;
      return { country: s.countryName, year: latest.year, value: latest.value, delta };
    })
    .filter((c): c is NonNullable<typeof c> => c !== null);

  if (!cards.length) return null;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {cards.map((c) => {
        const up = (c.delta ?? 0) >= 0;
        return (
          <Card key={c.country} className="p-4">
            <div className="text-sm text-text-secondary">{c.country}</div>
            <div className="text-2xl font-semibold mt-1">
              {fmtNum(c.value)}{data.unit === "%" ? "%" : ""}
            </div>
            <div className="text-xs text-text-muted">as of {c.year}</div>
            {c.delta != null && (
              <div className={`text-xs font-medium mt-1 ${up ? "text-success" : "text-danger"}`}>
                {up ? "▲" : "▼"} {fmtNum(Math.abs(c.delta))} YoY
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}
