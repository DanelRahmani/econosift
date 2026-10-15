import { QueryClient } from '@tanstack/react-query';
import { isBackendStarting } from './backendStatus';
import { STALE_MS, retryFor } from './queryPolicy';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: STALE_MS.default,     // per data class via apiQuery() (lib/queries.ts)
      gcTime: 30 * 60 * 1000,          // 30 minutes
      // One retry: each retry of a slow page re-hits the backend (and Yahoo)
      // while it is already overloaded. Only while the desktop backend is still
      // starting (BackendGate) do queries retry longer, with a capped delay.
      retry: (failureCount) => retryFor(failureCount, isBackendStarting()),
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 3000),
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
  },
});
