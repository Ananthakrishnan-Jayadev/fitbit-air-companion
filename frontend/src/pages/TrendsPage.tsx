import { useSearchParams } from "react-router-dom";
import TrendChart from "../components/charts/TrendChart.tsx";
import { Page, Panel, WithAside } from "../components/PageLayout.tsx";
import { formatDayLabel } from "../format.ts";
import { useTrend } from "../hooks/useData.ts";
import { formatMetric, METRICS, metricDef, TREND_METRICS } from "../metrics.ts";
import { trendStats } from "../trendStats.ts";

const RANGES = [30, 90, 180, 365];
const DEFAULT_METRIC = "recovery";

// What usually moves with each metric: shown as small charts under the main one.
const RELATED: Record<string, string[]> = {
  recovery: ["hrv_rmssd_ms", "resting_hr", "sleep_min"],
  sleep_perf: ["sleep_min", "hrv_rmssd_ms", "respiratory_rate"],
  sleep_min: ["sleep_perf", "recovery", "hrv_rmssd_ms"],
  strain: ["active_zone_minutes", "steps", "recovery"],
  stress_avg: ["resting_hr", "hrv_rmssd_ms", "recovery"],
  resting_hr: ["hrv_rmssd_ms", "recovery", "respiratory_rate"],
  hrv_rmssd_ms: ["resting_hr", "recovery", "sleep_min"],
  spo2_avg: ["respiratory_rate", "sleep_perf", "recovery"],
  respiratory_rate: ["spo2_avg", "resting_hr", "recovery"],
  skin_temp_delta_c: ["resting_hr", "respiratory_rate", "recovery"],
  steps: ["active_zone_minutes", "strain", "sedentary_min"],
  distance_m: ["steps", "active_zone_minutes", "strain"],
  active_zone_minutes: ["strain", "steps", "recovery"],
  total_calories: ["active_calories", "steps", "strain"],
  active_calories: ["total_calories", "active_zone_minutes", "strain"],
  sedentary_min: ["steps", "stress_avg", "sleep_min"],
  weight_kg: ["body_fat_pct", "steps", "total_calories"],
  body_fat_pct: ["weight_kg", "active_zone_minutes", "steps"],
};

/** Signed difference with the metric's unit, e.g. "+3 bpm", "−0.4 kg". */
function signedChange(metric: string, value: number): string {
  const text = formatMetric(metric, Math.abs(value));
  if (value === 0) return `±${text}`;
  return `${value > 0 ? "+" : "−"}${text}`;
}

function StatsPanel({ metric, days }: { metric: string; days: number }) {
  const { data } = useTrend(metric, days);
  const stats = trendStats(data?.points ?? []);
  const def = metricDef(metric);
  const fmt = (v: number | null | undefined) => formatMetric(metric, v);
  const rows: [string, string][] = [
    ["7-day average", fmt(stats.avg7)],
    ["30-day average", fmt(stats.avg30)],
    ["Your normal", stats.normal ? `${fmt(stats.normal.low)} – ${fmt(stats.normal.high)}` : "Learning…"],
    [`Change over ${days} days`, stats.change === null ? "—" : signedChange(metric, stats.change)],
    ["Highest", stats.max ? `${fmt(stats.max.value)} · ${formatDayLabel(stats.max.date)}` : "—"],
    ["Lowest", stats.min ? `${fmt(stats.min.value)} · ${formatDayLabel(stats.min.date)}` : "—"],
    ["Days with data", `${stats.daysWithData} of ${stats.daysInRange}`],
  ];
  return (
    <Panel title={def.label}>
      <p className="font-condensed text-[3.25rem] font-extrabold leading-none">{fmt(stats.latest?.value)}</p>
      <p className="mt-1 text-sm text-stone-600 dark:text-stone-400">
        {stats.latest ? `Latest · ${formatDayLabel(stats.latest.date)}` : "No data in this range"}
      </p>
      <dl className="mt-4 divide-y divide-stone-200 text-sm dark:divide-stone-800">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-baseline justify-between gap-4 py-2">
            <dt className="text-stone-600 dark:text-stone-400">{label}</dt>
            <dd className="text-right font-medium">{value}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

export default function TrendsPage() {
  const [params, setParams] = useSearchParams();
  const metric = TREND_METRICS.includes(params.get("metric") ?? "")
    ? (params.get("metric") as string)
    : DEFAULT_METRIC;
  const days = Number(params.get("days")) || 90;
  const related = (RELATED[metric] ?? []).filter((m) => m !== metric);

  const update = (next: { metric?: string; days?: number }) =>
    setParams({ metric: next.metric ?? metric, days: String(next.days ?? days) });

  return (
    <Page>
      <h1 className="page-title">Trends</h1>

      {/* One filter row for the page. */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <select
          className="border border-stone-300 bg-white px-2 py-1.5 text-sm dark:border-stone-700 dark:bg-stone-950"
          value={metric}
          onChange={(e) => update({ metric: e.target.value })}
          aria-label="Metric"
        >
          {TREND_METRICS.map((key) => (
            <option key={key} value={key}>
              {METRICS[key]?.label ?? key}
            </option>
          ))}
        </select>
        <div className="flex border border-stone-300 dark:border-stone-700" role="group" aria-label="Range">
          {RANGES.map((r) => (
            <button
              key={r}
              type="button"
              aria-pressed={r === days}
              onClick={() => update({ days: r })}
              className={`px-3 py-1.5 text-sm ${
                r === days ? "bg-cobalt text-white" : "hover:bg-stone-100 dark:hover:bg-stone-800"
              }`}
            >
              {r}d
            </button>
          ))}
        </div>
      </div>

      <WithAside label={`${metricDef(metric).label} summary`} aside={<StatsPanel metric={metric} days={days} />}>
        <TrendChart metric={metric} days={days} height={320} />
        {related.length > 0 && (
          <section aria-labelledby="related-heading" className="mt-10">
            <h2 id="related-heading" className="section-title">
              Moves with {metricDef(metric).label.toLowerCase()}
            </h2>
            <div className="grid gap-6 lg:grid-cols-3">
              {related.map((m) => (
                <TrendChart key={m} metric={m} days={days} height={180} />
              ))}
            </div>
            <p className="mt-3 text-xs text-stone-600 dark:text-stone-400">
              Shown side by side for comparison; moving together is not proof that one causes the other.
            </p>
          </section>
        )}
      </WithAside>
    </Page>
  );
}
