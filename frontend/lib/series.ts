// Pairing time series for charts.
//
// Series that share a chart often differ in frequency (daily breakevens vs a
// monthly survey) or start date. Pairing them by array position puts values
// next to the wrong dates; pair them by date with `asOf` instead.

export interface DatedValue {
  date: string;
  value: number | null;
}

const DAY_MS = 86_400_000;

/**
 * Returns a lookup giving the series' value at or before a date (an as-of
 * join). A lookup more than 1.5 of the series' own periods past its last
 * observation returns null, so a gap or an ended series is not stretched
 * across the chart. Dates are ISO strings ("YYYY-MM-DD"); the series must be
 * in ascending date order, as the API returns it.
 */
export function asOf(series: DatedValue[] | undefined | null): (date: string) => number | null {
  const pts = (series ?? []).filter((p) => p.value !== null && p.value !== undefined);
  if (!pts.length) return () => null;
  const times = pts.map((p) => Date.parse(p.date));
  const gaps = times.slice(1).map((t, i) => t - times[i]).sort((a, b) => a - b);
  const period = gaps.length ? gaps[Math.floor(gaps.length / 2)] : 31 * DAY_MS;
  const maxAge = Math.max(period * 1.5, 4 * DAY_MS);

  return (date: string) => {
    const t = Date.parse(date);
    let lo = 0;
    let hi = times.length - 1;
    if (Number.isNaN(t) || t < times[0]) return null;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (times[mid] <= t) lo = mid;
      else hi = mid - 1;
    }
    return t - times[lo] <= maxAge ? pts[lo].value : null;
  };
}
