import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CotData, CotContract } from "@/lib/types";
import { Card } from "@/components/ui";
import { useSourceScope } from "@/components/provenance/SourceScope";
import { provOf } from "@/lib/provenance";

function CotIndexBar({ value }: { value: number | null }) {
  if (value == null) return <span className="text-text-secondary">—</span>;
  const pct = Math.max(0, Math.min(100, value));
  const color = pct >= 70 ? "#10b981" : pct <= 30 ? "#ef4444" : "#f59e0b";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-surface-alt rounded-full h-2 overflow-hidden">
        <div className="h-2 rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs w-8 text-right">{pct.toFixed(0)}</span>
    </div>
  );
}

function fmtCot(v: number | null): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return v.toFixed(0);
}

export function SentimentTab() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [cotData, setCotData] = useState<CotData | null>(null);
  const scope = useSourceScope(provOf(data));
  const cotScope = useSourceScope(provOf(cotData));

  useEffect(() => {
    api.macroSentiment().then(setData).catch(console.error).finally(() => setLoading(false));
    api.macroCot().then(setCotData).catch(() => {});
  }, []);

  if (loading) return <div className="h-64 animate-pulse bg-surface rounded"></div>;
  if (!data || data.error) return <div className="text-red-500">{data?.error || "Failed to load"}</div>;

  const colorClass = data.overall === "Bullish" ? "text-green-500" : data.overall === "Bearish" ? "text-red-500" : "text-yellow-500";

  return (
    <div className="space-y-6">
      <Card className="p-5 flex items-center justify-between" {...scope}>
        <div>
          <h2 className="text-base font-semibold text-text-primary">Macro Sentiment</h2>
          <p className="text-sm text-text-secondary">Overall Tone: <span className={`font-bold ${colorClass}`} data-prov="overall" data-prov-ctx="Overall tone">{data.overall}</span></p>
        </div>
        <div className="text-right" data-prov="score" data-prov-ctx="Sentiment score">
          <div className="text-xs text-text-secondary">Sentiment Score</div>
          <div className={`text-2xl font-bold ${colorClass}`}>{data.score > 0 ? "+" : ""}{data.score.toFixed(2)}</div>
        </div>
      </Card>

      <div className="space-y-4" {...scope}>
        <h3 className="font-semibold text-sm">Recent News</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data.articles?.map((article: any, i: number) => (
            <a key={i} href={article.url} target="_blank" rel="noreferrer" className="block p-4 bg-surface border border-border rounded-lg hover:border-accent transition-colors" data-prov="articles" data-prov-ctx={article.source}>
              <div className="flex justify-between items-start mb-2">
                <span className="text-xs text-text-muted">{new Date(article.datetime * 1000).toLocaleString()}</span>
                <span data-prov="articles.sentiment" data-prov-ctx="Keyword sentiment label" className={`text-xs px-2 py-0.5 rounded ${
                  article.sentiment === "positive" ? "bg-green-500/10 text-green-500" :
                  article.sentiment === "negative" ? "bg-red-500/10 text-red-500" : "bg-surface-alt text-text-secondary"
                }`}>
                  {article.sentiment.toUpperCase()}
                </span>
              </div>
              <h4 className="text-sm font-semibold mb-1 line-clamp-2">{article.headline}</h4>
              <p className="text-xs text-text-secondary line-clamp-3">{article.summary}</p>
              <div className="text-xs text-text-muted mt-2">{article.source}</div>
            </a>
          ))}
        </div>
      </div>

      {/* ── COT Positioning ── */}
      {cotData && !cotData.error && cotData.contracts?.length > 0 && (
        <div className="space-y-4" {...cotScope}>
          <h2 className="font-semibold text-lg border-t border-border pt-6 mt-2">
            Commitments of Traders (CFTC)
            <span className="text-xs text-text-secondary font-normal ml-2">
              Source: {cotData.source}{cotData.asOf ? ` · as of ${cotData.asOf}` : ""}
            </span>
          </h2>
          <Card className="p-4">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-text-secondary border-b border-border">
                    <th className="pb-2 pr-4">Contract</th>
                    <th className="pb-2 pr-4 text-right">Net Speculator</th>
                    <th className="pb-2 pr-4 text-right">Net Commercial</th>
                    <th className="pb-2 pr-4 text-right">Open Interest</th>
                    <th className="pb-2 min-w-[120px]">COT Index (0–100)</th>
                  </tr>
                </thead>
                <tbody>
                  {cotData.contracts.map((c: CotContract) => (
                    <tr key={c.code} className="border-b border-border/40 hover:bg-surface-alt/30 transition-colors" data-prov-ctx={c.name}>
                      <td className="py-2 pr-4"><div className="font-medium">{c.name}</div><div className="text-xs text-text-secondary">{c.code}</div></td>
                      <td data-prov="contracts.net_speculator" className={`py-2 pr-4 text-right font-mono font-semibold ${c.net_speculator != null && c.net_speculator >= 0 ? "text-success" : "text-danger"}`}>
                        {c.net_speculator != null ? `${c.net_speculator >= 0 ? "+" : ""}${fmtCot(c.net_speculator)}` : "—"}
                      </td>
                      <td data-prov="contracts.net_commercial" className={`py-2 pr-4 text-right font-mono ${c.net_commercial != null && c.net_commercial >= 0 ? "text-success" : "text-danger"}`}>
                        {c.net_commercial != null ? `${c.net_commercial >= 0 ? "+" : ""}${fmtCot(c.net_commercial)}` : "—"}
                      </td>
                      <td data-prov="contracts.open_interest" className="py-2 pr-4 text-right font-mono text-text-secondary">{fmtCot(c.open_interest)}</td>
                      <td data-prov="contracts.cot_index" className="py-2">
                        {c.cot_index != null && <CotIndexBar value={c.cot_index} />}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* COT unavailable message */}
      {cotData && (cotData.error || !cotData.contracts?.length) && (
        <div className="border-t border-border pt-6 mt-2">
          <h2 className="font-semibold text-lg mb-2">Commitments of Traders (CFTC)</h2>
          <p className="text-text-secondary text-sm">
            {cotData.error ?? "COT data unavailable — CFTC source may be delayed. Data published weekly on Fridays."}
          </p>
        </div>
      )}
    </div>
  );
}
