import type { ReactNode } from "react";

/**
 * Recharts <Legend formatter> that tags each legend label with the provenance
 * key of its line, so right-clicking a legend entry opens that series' source.
 * `keys` maps the line's legend name to its `data-prov` key; names without an
 * entry are left plain.
 */
export function legendProv(keys: Record<string, string>) {
  return function LegendLabel(value: string): ReactNode {
    const key = keys[value];
    return key ? <span data-prov={key} data-prov-ctx={value}>{value}</span> : value;
  };
}
