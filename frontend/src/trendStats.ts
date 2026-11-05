import type { TrendResponse } from "./api/types.ts";

/** Summary of one metric's daily values over the shown range (Trends side panel). */
export interface TrendStats {
  latest: { date: string; value: number } | null;
  avg7: number | null;
  avg30: number | null;
  normal: { low: number; high: number } | null;
  /** Last value minus first value in the range. */
  change: number | null;
  min: { date: string; value: number } | null;
  max: { date: string; value: number } | null;
  daysWithData: number;
  daysInRange: number;
}

function mean(values: number[]): number | null {
  return values.length ? values.reduce((sum, v) => sum + v, 0) / values.length : null;
}

/** Pure: computes the stats panel from the points the trend chart already loaded. */
export function trendStats(points: TrendResponse["points"]): TrendStats {
  const known = points.filter((p): p is typeof p & { value: number } => p.value !== null);
  const last = known[known.length - 1];
  const first = known[0];
  const lastDays = (n: number) => points.slice(-n).flatMap((p) => (p.value === null ? [] : [p.value]));
  let min: TrendStats["min"] = null;
  let max: TrendStats["max"] = null;
  for (const p of known) {
    if (!min || p.value < min.value) min = { date: p.date, value: p.value };
    if (!max || p.value > max.value) max = { date: p.date, value: p.value };
  }
  // The most recent day that has a baseline describes "your normal" now.
  const withBand = [...points].reverse().find((p) => p.baseline);
  return {
    latest: last ? { date: last.date, value: last.value } : null,
    avg7: mean(lastDays(7)),
    avg30: mean(lastDays(30)),
    normal: withBand?.baseline ? { low: withBand.baseline.low, high: withBand.baseline.high } : null,
    change: last && first && known.length > 1 ? last.value - first.value : null,
    min,
    max,
    daysWithData: known.length,
    daysInRange: points.length,
  };
}
