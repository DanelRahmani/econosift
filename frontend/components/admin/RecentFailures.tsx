"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ErrorLogResponse } from "@/lib/types";
import { Card } from "@/components/ui";

/**
 * Live-ops view of recent backend warnings — Phase 41 (task B2).
 *
 * Every service degrades quietly by design: a dead source logs a warning and
 * returns empty so one provider cannot take a page down. The cost is that a
 * broken fetch and a genuinely empty result look identical in the UI. This
 * surfaces the difference.
 *
 * In-memory and process-local: it clears on restart, and says so.
 */
function relativeTime(iso: string): string {
  const secs = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return `${Math.floor(secs)}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

export function RecentFailures() {
  const [data, setData] = useState<ErrorLogResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    api
      .adminErrors(100)
      .then((d) => {
        setData(d);
        setFailed(false);
      })
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [load]);

  async function clear() {
    try {
      await api.clearAdminErrors();
      load();
    } catch {
      /* leave the current view in place */
    }
  }

  if (loading) {
    return (
      <Card>
        <h2 className="text-sm font-semibold mb-3 text-text-secondary">Recent Failures</h2>
        <div className="h-16 animate-pulse bg-surface-alt rounded" />
      </Card>
    );
  }

  if (failed || !data) {
    return (
      <Card>
        <h2 className="text-sm font-semibold mb-3 text-text-secondary">Recent Failures</h2>
        <div className="text-sm text-text-muted">Could not reach the backend.</div>
      </Card>
    );
  }

  const { entries, stats } = data;
  const topSources = Object.entries(stats.bySource).slice(0, 4);

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-text-secondary">
          Recent Failures{" "}
          <span className="font-normal text-text-muted">
            ({stats.total}/{stats.capacity})
          </span>
        </h2>
        {entries.length > 0 && (
          <button
            onClick={clear}
            className="px-2 py-1 text-xs rounded border border-border text-text-muted hover:text-text-primary transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {entries.length === 0 ? (
        <div className="text-sm text-text-muted">
          No warnings recorded since the backend started. Sources are degrading
          gracefully or not being exercised.
        </div>
      ) : (
        <>
          {topSources.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {topSources.map(([source, count]) => (
                <span
                  key={source}
                  className="px-2 py-0.5 text-xs rounded-full border border-border text-text-secondary"
                >
                  {source} · {count}
                </span>
              ))}
            </div>
          )}

          <div className="overflow-x-auto max-h-80 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-surface">
                <tr className="text-left text-text-muted border-b border-border">
                  <th className="py-1.5 pr-3 font-medium whitespace-nowrap">When</th>
                  <th className="py-1.5 pr-3 font-medium">Level</th>
                  <th className="py-1.5 pr-3 font-medium">Source</th>
                  <th className="py-1.5 font-medium">Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {entries.map((e, i) => (
                  <tr key={`${e.timestamp}-${i}`}>
                    <td
                      className="py-1.5 pr-3 text-text-muted whitespace-nowrap"
                      title={e.timestamp}
                    >
                      {relativeTime(e.timestamp)}
                    </td>
                    <td className="py-1.5 pr-3">
                      <span
                        className={
                          e.level === "WARNING" ? "text-warning" : "text-danger"
                        }
                      >
                        {e.level}
                      </span>
                    </td>
                    <td className="py-1.5 pr-3 font-mono text-text-secondary whitespace-nowrap">
                      {e.source}
                    </td>
                    <td className="py-1.5 text-text-secondary break-words">{e.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <p className="text-[11px] text-text-muted mt-3">
        In-memory and process-local — this clears when the backend restarts. It is
        a live view, not an audit trail.
      </p>
    </Card>
  );
}
