import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,       // 5 minutes
      gcTime: 30 * 60 * 1000,          // 30 minutes
      // Desktop app: backend starts alongside the window and some endpoints are
      // slow on a cold cache. Retry longer (capped delay) so slow first-calls
      // recover instead of leaving panels stuck on "unavailable".
      retry: 6,
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 3000),
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
  },
});
