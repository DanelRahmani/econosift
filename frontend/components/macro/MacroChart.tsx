"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine,
} from "recharts";
import type { MacroResponse, MacroSeries } from "@/lib/types";
import { CHART_COLORS } from "@/lib/format";
import { chartTooltipStyle, chartPalette } from "@/components/ui";
import { useTheme } from "@/components/ThemeProvider";

export function MacroChart({ data, forecast: forecastProp = [] }: { data: MacroResponse; forecast?: MacroSeries[] }) {
  const { theme } = useTheme();
  const pal = chartPalette(theme);
  // Projection points inside the main series (e.g. IMF WEO filling the current
  // year) are drawn on the dashed forecast line, never as solid actuals.
  const series = data.series.map((s) => ({ ...s, data: s.data.filter((d) => !d.estimate) }));
  const forecast = [
    ...forecastProp,
    ...data.series
      .filter((s) => s.data.some((d) => d.estimate) && !forecastProp.some((f) => f.country === s.country))
      .map((s) => ({ ...s, data: s.data.filter((d) => d.estimate) })),
  ];
  if (!series.length || data.series.every((s) => s.data.length === 0)) {
    return <div className="text-text-muted text-sm">No data for this selection.</div>;
  }

  // Last historical year per country — forecast lines start here so they connect.
  const lastActual: Record<string, string> = {};
  series.forEach((s) => {
    if (s.data.length) lastActual[s.country] = s.data[s.data.length - 1].year;
  });
  const forecastByCountry = new Map(forecast.map((s) => [s.country, s]));

  // Merge historical + forecast series by year into wide rows.
  const years = new Set<string>();
  series.forEach((s) => s.data.forEach((d) => years.add(d.year)));
  forecast.forEach((s) => s.data.forEach((d) => { if (d.year >= (lastActual[s.country] ?? "0")) years.add(d.year); }));
  const sorted = Array.from(years).sort();
  const boundaryYear = Object.values(lastActual).sort()[0];

  const rows = sorted.map((year) => {
    const row: Record<string, string | number | null> = { year };
    series.forEach((s) => {
      const pt = s.data.find((d) => d.year === year);
      row[s.country] = pt ? pt.value : null;
    });
    forecast.forEach((s) => {
      const start = lastActual[s.country];
      if (!start || year < start) { row[`${s.country}_fc`] = null; return; }
      if (year === start) {
        const a = series.find((x) => x.country === s.country)?.data.find((d) => d.year === year);
        row[`${s.country}_fc`] = a ? a.value : null; // junction point
      } else {
        const pt = s.data.find((d) => d.year === year);
        row[`${s.country}_fc`] = pt ? pt.value : null;
      }
    });
    return row;
  });

  return (
    <div>
      <div className="h-96 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows}>
            <CartesianGrid stroke={pal.grid} strokeDasharray="3 3" />
            <XAxis dataKey="year" tick={{ fill: pal.axis, fontSize: 12 }} />
            <YAxis tick={{ fill: pal.axis, fontSize: 12 }}
              tickFormatter={(v) => `${v}${data.unit === "%" ? "%" : ""}`} />
            <Tooltip
              {...chartTooltipStyle(theme)}
              formatter={(value: number | string, name: string) => {
                const n = typeof value === "number" ? value : Number(value);
                if (!Number.isFinite(n)) return ["—", name];
                const unit = data.unit === "%" ? "%" : "";
                return [`${n.toFixed(2)}${unit}`, name];
              }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {forecast.length > 0 && boundaryYear && (
              <ReferenceLine x={boundaryYear} stroke={pal.axis} strokeDasharray="4 4" strokeOpacity={0.5}
                label={{ value: "forecast →", position: "insideTopRight", fontSize: 10, fill: pal.axis }} />
            )}
            {series.map((s, i) => (
              <Line
                key={s.country}
                type="monotone"
                dataKey={s.country}
                name={s.countryName}
                stroke={CHART_COLORS[i % CHART_COLORS.length]}
                strokeWidth={2}
                dot={false}
                connectNulls
              />
            ))}
            {series.map((s, i) =>
              forecastByCountry.has(s.country) ? (
                <Line
                  key={`${s.country}_fc`}
                  type="monotone"
                  dataKey={`${s.country}_fc`}
                  name={`${s.countryName} (IMF forecast)`}
                  stroke={CHART_COLORS[i % CHART_COLORS.length]}
                  strokeWidth={2}
                  strokeDasharray="5 4"
                  strokeOpacity={0.75}
                  dot={false}
                  connectNulls
                  legendType="none"
                />
              ) : null,
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 text-xs text-text-muted">
        Sources: {Array.from(new Set(series.map((s) => s.source_label))).join(", ")}
        {forecast.length > 0 && " · IMF WEO projections (dashed)"}
      </div>
    </div>
  );
}
