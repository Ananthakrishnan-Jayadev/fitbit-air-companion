import { formatMinutes, formatNumber } from "./format.ts";

export interface MetricDef {
  label: string;
  unit: string;
  digits: number;
  /** Converts the stored value for display (e.g. metres -> km). */
  scale?: number;
  minutes?: boolean;
  /** Whether a higher value is generally better (for "above/below normal" wording). */
  higherIsBetter?: boolean;
  /** Not measured every day (e.g. weigh-ins): charts join the readings and mark each one. */
  sparse?: boolean;
  /** Pillar hue for charts of this metric (index.css); default is the neutral series blue. */
  tone?: PillarTone;
}

export type PillarTone = "sleep" | "strain";

export const METRICS: Record<string, MetricDef> = {
  recovery: { label: "Recovery", unit: "/100", digits: 0, higherIsBetter: true },
  sleep_perf: { label: "Sleep score", unit: "/100", digits: 0, higherIsBetter: true, tone: "sleep" },
  strain: { label: "Strain", unit: "/21", digits: 1, tone: "strain" },
  stress_avg: { label: "Stress", unit: "/100", digits: 0, higherIsBetter: false },
  resting_hr: { label: "Resting heart rate", unit: "bpm", digits: 0, higherIsBetter: false },
  hrv_rmssd_ms: { label: "HRV (RMSSD)", unit: "ms", digits: 0, higherIsBetter: true },
  spo2_avg: { label: "Blood oxygen", unit: "%", digits: 1, higherIsBetter: true },
  respiratory_rate: { label: "Breathing rate", unit: "br/min", digits: 1, higherIsBetter: false },
  skin_temp_delta_c: { label: "Skin temperature", unit: "°C vs usual", digits: 2 },
  sleep_min: { label: "Time asleep", unit: "", digits: 0, minutes: true, higherIsBetter: true, tone: "sleep" },
  steps: { label: "Steps", unit: "", digits: 0 },
  distance_m: { label: "Distance", unit: "km", digits: 2, scale: 0.001 },
  active_zone_minutes: { label: "Active zone minutes", unit: "min", digits: 0, tone: "strain" },
  total_calories: { label: "Calories", unit: "kcal", digits: 0 },
  active_calories: { label: "Active calories", unit: "kcal", digits: 0 },
  sedentary_min: { label: "Sedentary time", unit: "", digits: 0, minutes: true },
  weight_kg: { label: "Weight", unit: "kg", digits: 1, sparse: true },
  body_fat_pct: { label: "Body fat", unit: "%", digits: 1, sparse: true },
};

export const TREND_METRICS = Object.keys(METRICS);

export function metricDef(key: string): MetricDef {
  return METRICS[key] ?? { label: key, unit: "", digits: 1 };
}

/** Value with its unit, e.g. "57 bpm", "7h 32m", "8.42 km". */
export function formatMetric(key: string, value: number | null | undefined): string {
  const def = metricDef(key);
  if (value === null || value === undefined) return "—";
  if (def.minutes) return formatMinutes(value);
  const shown = formatNumber(value * (def.scale ?? 1), def.digits);
  return def.unit && !def.unit.startsWith("/") ? `${shown} ${def.unit}` : shown;
}

export const FLAG_TEXT: Record<string, string> = {
  temp_elevated: "Skin temperature is elevated",
  rhr_elevated: "Resting heart rate is well above your normal",
  hrv_suppressed: "HRV is well below your normal",
  resp_elevated: "Breathing rate is above your normal",
  spo2_low: "Blood oxygen is below your normal",
  illness_watch: "Several signals look like your body is fighting something",
  hrv_suppressed_3d: "HRV has been low for 3 days",
  load_spike: "Training load jumped well above your recent average",
  load_low: "Training load is well below your recent average",
};

export type RecoveryTone = "good" | "warning" | "critical";

/** Recovery bands (shown with a text label, never colour alone). */
export function recoveryBand(score: number): { label: string; tone: RecoveryTone } {
  if (score >= 67) return { label: "High", tone: "good" };
  if (score >= 34) return { label: "Moderate", tone: "warning" };
  return { label: "Low", tone: "critical" };
}
