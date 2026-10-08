"use client";

import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { Card } from "@/components/ui";
import { api } from "@/lib/api";
import type { FxMacroLinkItem } from "@/lib/types";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf, type Provenance } from "@/lib/provenance";
import { useRefreshNonce } from "@/lib/refresh";

export function FxMacroLink() {
  const [links, setLinks] = useState<FxMacroLinkItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<number>(0);
  // the response is unwrapped into `links`, so its provenance map is kept alongside
  const [linksProv, setLinksProv] = useState<Provenance | undefined>();
  const scope = useSourceScope(linksProv);

  const refreshNonce = useRefreshNonce(); // re-fetch on the Navbar's Refresh (P1-20)
  useEffect(() => {
    setLoading(true);
    api.fxMacroLink()
      .then((r) => { setLinks(r.links || []); setLinksProv(provOf(r)); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [refreshNonce]);

  const link = links[selected];
  const linkKey = `links.${link?.label}`;

  return (
    <div className="space-y-6" {...scope}>
      {loading && <div className="h-64 animate-pulse bg-surface-alt rounded-lg" />}
      {error && (
        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/30 text-sm text-red-500">{error}</div>
      )}

      {!loading && !error && links.length === 0 && (
        <div className="text-center py-16 text-text-muted text-sm">No FX-macro link data available.</div>
      )}

      {links.length > 0 && (
        <>
          {/* Pair selector */}
          <Card>
            <div className="flex flex-wrap gap-2">
              {links.map((l, i) => (
                <button
                  key={l.fxPair}
                  onClick={() => setSelected(i)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    i === selected
                      ? "bg-accent text-white"
                      : "bg-surface-alt text-text-secondary hover:text-text-primary"
                  }`}
                >
                  {l.label}
                </button>
              ))}
            </div>
          </Card>

          {/* KPIs */}
          {link && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Card data-prov={`${linkKey}.currentCorrelation`} data-prov-ctx={link.label}>
                  <div className="text-xs text-text-muted">Current Correlation</div>
                  <div className={`text-xl font-bold tabular-nums ${
                    link.currentCorrelation !== null && Math.abs(link.currentCorrelation) >= 0.5
                      ? "text-green-500" : "text-text-primary"
                  }`}>
                    {link.currentCorrelation !== null ? link.currentCorrelation.toFixed(3) : "—"}
                  </div>
                </Card>
                <Card data-prov={`${linkKey}.bestLag`} data-prov-ctx={link.label}>
                  <div className="text-xs text-text-muted">Best Lag</div>
                  <div className="text-xl font-bold tabular-nums">
                    {link.bestLag > 0 ? `Comm leads ${link.bestLag}d` : link.bestLag < 0 ? `FX leads ${-link.bestLag}d` : "Concurrent"}
                  </div>
                </Card>
                <Card data-prov={`${linkKey}.bestLagCorrelation`} data-prov-ctx={link.label}>
                  <div className="text-xs text-text-muted">Lag Correlation</div>
                  <div className="text-xl font-bold tabular-nums text-accent">
                    {link.bestLagCorrelation.toFixed(3)}
                  </div>
                </Card>
                <Card data-prov={linkKey} data-prov-ctx={link.label}>
                  <div className="text-xs text-text-muted">FX Pair</div>
                  <div className="text-xl font-bold font-mono text-sm">{link.fxPair}</div>
                </Card>
              </div>

              {/* Price overlay chart */}
              {link.series.length > 0 && (
                <Card data-prov={`${linkKey}.series`} data-prov-ctx={link.label}>
                  <h3 className="text-sm font-semibold mb-3">
                    Price Overlay (Base 100) — {link.label}
                  </h3>
                  <div className="h-64">
                    <ResponsiveContainer>
                      <LineChart data={link.series}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--border))" />
                        <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                        <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10 }} />
                        <Tooltip />
                        <Legend />
                        <Line type="monotone" dataKey="fx" stroke="#3b82f6" dot={false} name="FX" />
                        <Line type="monotone" dataKey="commodity" stroke="#f59e0b" dot={false} name="Commodity" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </Card>
              )}

              {/* Rolling correlation chart */}
              {link.rollingCorrelation.dates.length > 0 && (
                <Card data-prov={linkKey} data-prov-ctx={link.label}>
                  <h3 className="text-sm font-semibold mb-3">60-Day Rolling Correlation</h3>
                  <div className="h-48">
                    <ResponsiveContainer>
                      <LineChart data={link.rollingCorrelation.dates.map((d, i) => ({
                        date: d,
                        correlation: link.rollingCorrelation.values[i],
                      }))}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--border))" />
                        <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                        <YAxis domain={[-1, 1]} tick={{ fontSize: 10 }} />
                        <Tooltip />
                        <Line type="monotone" dataKey="correlation" stroke="#8b5cf6" dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </Card>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
