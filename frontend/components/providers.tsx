'use client';

import { useEffect, useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/queryClient';
import { LearningProvider } from '@/lib/learningContext';

// Relative by default (Docker/web hit /api via nginx); the Tauri desktop build
// sets NEXT_PUBLIC_API_URL=http://localhost:8000 in .env.production.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

/**
 * Desktop startup gate.
 *
 * In the Tauri app the backend is spawned alongside the window and takes a few
 * seconds to be ready. Without this, the first wave of data fetches fires before
 * the backend answers and slow panels get stuck on "unavailable". We poll
 * /api/health and hold a lightweight splash until the backend responds (or a
 * grace period elapses, so a genuinely-down backend still shows the app rather
 * than hanging forever). In Docker/web the health check passes immediately, so
 * the splash is effectively invisible.
 */
function BackendGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const start = Date.now();
    const MAX_WAIT = 45_000; // give up gating after 45s and render anyway

    async function poll() {
      while (!cancelled) {
        try {
          const res = await fetch(`${API_BASE}/api/health`, { cache: 'no-store' });
          if (res.ok) break;
        } catch {
          /* backend not up yet */
        }
        if (Date.now() - start > MAX_WAIT) break;
        await new Promise((r) => setTimeout(r, 500));
      }
      if (!cancelled) setReady(true);
    }
    poll();
    return () => {
      cancelled = true;
    };
  }, []);

  if (ready) return <>{children}</>;

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-white dark:bg-neutral-950">
      <div className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
        Axiom <span className="text-red-600">Finance</span>
      </div>
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-300 border-t-red-600" />
      <div className="text-sm text-neutral-500">Starting analysis engine…</div>
    </div>
  );
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <LearningProvider>
        <BackendGate>{children}</BackendGate>
      </LearningProvider>
    </QueryClientProvider>
  );
}
