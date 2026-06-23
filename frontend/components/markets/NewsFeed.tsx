"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { NewsItem, Sentiment } from "@/lib/types";
import { Card, Skeleton } from "@/components/ui";

const SENTIMENT_STYLE: Record<Sentiment, { dot: string; label: string; text: string }> = {
  positive: { dot: "bg-success", label: "Positive", text: "text-success" },
  neutral: { dot: "bg-text-muted", label: "Neutral", text: "text-text-muted" },
  negative: { dot: "bg-danger", label: "Negative", text: "text-danger" },
};

export function NewsFeed({ tickers }: { tickers: string[] }) {
  const [active, setActive] = useState<string>(tickers[0] ?? "");
  const [items, setItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(false);

  // Keep the selected ticker valid as the basket changes.
  useEffect(() => {
    if (!tickers.length) { setActive(""); return; }
    if (!tickers.includes(active)) setActive(tickers[0]);
  }, [tickers, active]);

  useEffect(() => {
    if (!active) { setItems([]); return; }
    let live = true;
    setLoading(true);
    api.news(active)
      .then((r) => live && setItems(r.news))
      .catch(() => live && setItems([]))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [active]);

  if (!tickers.length) return null;

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="text-sm font-semibold text-text-secondary">Latest News</h2>
        {tickers.length > 1 && (
          <div className="flex flex-wrap gap-1">
            {tickers.map((t) => (
              <button
                key={t}
                onClick={() => setActive(t)}
                className={`px-2 py-0.5 rounded text-xs font-mono transition-colors ${
                  active === t ? "bg-accent text-white" : "text-text-muted hover:text-text-primary"
                }`}
              >{t}</button>
            ))}
          </div>
        )}
      </div>

      {loading && !items.length ? (
        <Skeleton className="h-40" />
      ) : !items.length ? (
        <div className="text-text-muted text-sm">No recent headlines for {active}.</div>
      ) : (
        <ul className="space-y-3">
          {items.map((n, i) => {
            const s = SENTIMENT_STYLE[n.sentiment];
            return (
              <li key={i} className="flex gap-3">
                <span className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${s.dot}`} title={s.label} />
                <div className="min-w-0">
                  <a
                    href={n.url} target="_blank" rel="noopener noreferrer"
                    className="text-sm text-text-primary hover:text-accent transition-colors line-clamp-2"
                  >{n.title}</a>
                  <div className="flex items-center gap-2 text-xs text-text-muted mt-0.5">
                    <span className="truncate">{n.publisher || "—"}</span>
                    {n.published && <span>· {n.published}</span>}
                    <span className={s.text}>· {s.label}</span>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
