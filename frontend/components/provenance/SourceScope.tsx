"use client";

import { useEffect, useId } from "react";
import { registerScope, unregisterScope, type Provenance } from "@/lib/provenance";

/**
 * Marks an element as showing data from one response. Spread the returned
 * props on the component's existing root element:
 *
 *   const scope = useSourceScope(data?.provenance);
 *   return <div className="card" {...scope}>…</div>;
 *
 * Right-clicking anywhere inside then opens the Source menu. Values that name
 * their key with `data-prov="<key>"` resolve to that key's source; everything
 * else falls back to the map's `"*"` default.
 */
export function useSourceScope(prov: Provenance | null | undefined) {
  const id = useId();

  useEffect(() => {
    registerScope(id, prov);
    return () => unregisterScope(id);
  }, [id, prov]);

  return { "data-prov-scope": id };
}

interface Props {
  /** The `provenance` map of the response this subtree renders. */
  prov: Provenance | null | undefined;
  children: React.ReactNode;
  className?: string;
}

/**
 * Wrapper form of {@link useSourceScope}, for callers without a root element
 * of their own. It renders a block `<div>`; pass `className` for layout.
 */
export function SourceScope({ prov, children, className }: Props) {
  const scope = useSourceScope(prov);
  return (
    <div className={className} {...scope}>
      {children}
    </div>
  );
}
