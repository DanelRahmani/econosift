import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui";

export function SentimentTab() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.macroSentiment().then(setData).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="h-64 animate-pulse bg-surface rounded"></div>;
  if (!data || data.error) return <div className="text-red-500">{data?.error || "Failed to load"}</div>;

  const colorClass = data.overall === "Bullish" ? "text-green-500" : data.overall === "Bearish" ? "text-red-500" : "text-yellow-500";

  return (
    <div className="space-y-6">
      <Card className="p-5 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-text-primary">Macro Sentiment</h2>
          <p className="text-sm text-text-secondary">Overall Tone: <span className={`font-bold ${colorClass}`}>{data.overall}</span></p>
        </div>
        <div className="text-right">
          <div className="text-xs text-text-secondary">Sentiment Score</div>
          <div className={`text-2xl font-bold ${colorClass}`}>{data.score > 0 ? "+" : ""}{data.score.toFixed(2)}</div>
        </div>
      </Card>

      <div className="space-y-4">
        <h3 className="font-semibold text-sm">Recent News</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data.articles?.map((article: any, i: number) => (
            <a key={i} href={article.url} target="_blank" rel="noreferrer" className="block p-4 bg-surface border border-border rounded-lg hover:border-accent transition-colors">
              <div className="flex justify-between items-start mb-2">
                <span className="text-xs text-text-muted">{new Date(article.datetime * 1000).toLocaleString()}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${
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
    </div>
  );
}
