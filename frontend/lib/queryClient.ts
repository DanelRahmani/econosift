import { QueryClient } from '@tanstack/react-query';
import { isBackendStarting } from './backendStatus';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,       // 5 minutes
      gcTime: 30 * 60 * 1000,          // 30 minutes
      // One retry: each retry of a slow page re-hits the backend (and Yahoo)
      // while it is already overloaded. Only while the desktop backend is still
      // starting (BackendGate) do queries retry longer, with a capped delay.
      retry: (failureCount) => failureCount < (isBackendStarting() ? 6 : 1),
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 3000),
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
  },
});
