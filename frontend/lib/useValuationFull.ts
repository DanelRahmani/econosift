import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

const DEGRADED_RETRY_MS = 15_000;
const DEGRADED_MAX_FETCHES = 8; // ~2 min, then the page keeps the partial data and its notice

/**
 * /valuation/full for one ticker, shared by every Valuation-tab panel (one request, one result; P3-34).
 * While the backend flags the bundle as degraded (Yahoo answered in part, never cached), it is
 * re-requested until the full bundle arrives (P2-39); `refreshing` is true while that is still going on.
 */
export function useValuationFull(ticker: string) {
  const queryKey = ["valuation-full", ticker];
  const query = useQuery({
    queryKey,
    queryFn: () => api.valuationFull(ticker),
    enabled: !!ticker,
    refetchInterval: (q) =>
      q.state.data?.degraded && q.state.dataUpdateCount < DEGRADED_MAX_FETCHES ? DEGRADED_RETRY_MS : false,
  });
  const updates = useQueryClient().getQueryState(queryKey)?.dataUpdateCount ?? 0;
  return { ...query, refreshing: !!query.data?.degraded && updates < DEGRADED_MAX_FETCHES };
}
