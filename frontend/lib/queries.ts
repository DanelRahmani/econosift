import { queryOptions } from "@tanstack/react-query";
import { api } from "./api";
import { staleTimeFor } from "./queryPolicy";
import { pendingRefetchInterval } from "./asOf";

type Api = typeof api;
type ApiName = { [K in keyof Api]: Api[K] extends (...args: never[]) => Promise<unknown> ? K : never }[keyof Api];
type Fn<K extends ApiName> = Api[K] extends (...args: infer A) => Promise<infer R> ? (...args: A) => Promise<R> : never;

/**
 * Query options for one api.ts call: the key is the method name plus its
 * arguments, so every panel asking for the same data shares one cache entry
 * (and one request), and the stale time comes from the data class
 * (lib/queryPolicy.ts). A response the fetcher has not stored yet (`status: "pending"`)
 * is polled until it arrives (lib/asOf.ts). Use as `useQuery(apiQuery("breadth", index))`.
 */
export function apiQuery<K extends ApiName>(name: K, ...args: Parameters<Fn<K>>) {
  const fn = api[name] as unknown as Fn<K>;
  return queryOptions({
    queryKey: [name, ...args] as const,
    queryFn: () => fn(...args) as Promise<Awaited<ReturnType<Fn<K>>>>,
    staleTime: staleTimeFor(name),
    refetchInterval: (q) => pendingRefetchInterval(q.state.data, q.state.dataUpdateCount),
  });
}
