import type { EChartsOption } from "echarts";
import type { ActivityResponse } from "../api/types.ts";
import ChartCard, { DataTable } from "../components/ChartCard.tsx";
import Chart from "../components/charts/Chart.tsx";
import {
  axisTooltip,
  categoryAxis,
  firstParam,
  grid,
  itemTooltip,
  timeAxis,
  timeLabel,
  valueAxis,
} from "../components/charts/options.ts";
import { useChartTokens, type ChartTokens } from "../components/charts/tokens.ts";
import DateNav from "../components/DateNav.tsx";
import { LoadError, Loading } from "../components/PageState.tsx";
import StatTile from "../components/StatTile.tsx";
import { formatClock, formatMinutes, formatNumber } from "../format.ts";
import { useActivity } from "../hooks/useData.ts";
import { useSelectedDate } from "../hooks/useSelectedDate.ts";
import { formatMetric, metricDef } from "../metrics.ts";

// Ordered least -> most active, drawn with the ordinal blue ramp.
const LEVELS = [
  { key: "SEDENTARY", label: "Sedentary", token: "seq-250" },
  { key: "LIGHTLY_ACTIVE", label: "Light", token: "seq-350" },
  { key: "MODERATELY_ACTIVE", label: "Moderate", token: "seq-450" },
  { key: "VERY_ACTIVE", label: "Vigorous", token: "seq-600" },
] as const;

const TOTALS = ["steps", "distance_m", "active_zone_minutes", "active_calories", "total_calories", "sedentary_min"];

function hourLabel(ms: number): string {
  return new Date(ms).toLocaleTimeString([], { hour: "2-digit" });
}

function stepsChart(t: ChartTokens, data: ActivityResponse): EChartsOption {
  return {
    grid: grid(),
    tooltip: itemTooltip(t, (raw) => {
      const p = firstParam(raw);
      return `${String(p.name)}<br/><b>${formatNumber(Number(p.value))} steps</b>`;
    }),
    xAxis: categoryAxis(t, data.hourly.map((h) => hourLabel(h.start))),
    yAxis: valueAxis(t),
    series: [
      {
        type: "bar",
        data: data.hourly.map((h) => h.steps),
        barMaxWidth: 24,
        itemStyle: { color: t["series-1"], borderRadius: [4, 4, 0, 0] },
      },
    ],
  };
}

function levelsChart(t: ChartTokens, data: ActivityResponse): EChartsOption {
  return {
    grid: grid(),
    tooltip: itemTooltip(t, (raw) => {
      const p = firstParam(raw);
      return `${String(p.name)}<br/><b>${formatMinutes(Number(p.value))}</b>`;
    }),
    xAxis: categoryAxis(t, LEVELS.map((l) => l.label)),
    yAxis: valueAxis(t, { axisLabel: { color: t["ink-muted"], formatter: (v: number) => formatMinutes(v) } }),
    series: [
      {
        type: "bar",
        barMaxWidth: 24,
        data: LEVELS.map((l) => ({
          value: data.level_minutes[l.key] ?? 0,
          itemStyle: { color: t[l.token], borderRadius: [4, 4, 0, 0] },
        })),
        label: {
          show: true,
          position: "top",
          color: t["ink-2"],
          formatter: (p: { value?: unknown }) => formatMinutes(Number(p.value)),
        },
      },
    ],
  };
}

function stressChart(t: ChartTokens, data: ActivityResponse): EChartsOption {
  return {
    grid: grid(),
    tooltip: axisTooltip(t, (raw) => {
      const value = firstParam(raw).value;
      if (!Array.isArray(value)) return "";
      const [ms, v] = value as [number, number];
      return `${timeLabel(ms)}<br/><b>Stress ${formatNumber(v)}</b>`;
    }),
    xAxis: timeAxis(t),
    yAxis: valueAxis(t, { min: 0, max: 100 }),
    series: [
      {
        type: "line",
        data: data.stress,
        symbol: "none",
        connectNulls: false,
        lineStyle: { width: 2, color: t["series-1"] },
        areaStyle: { color: t["series-1-wash"], opacity: 1 },
      },
    ],
  };
}

export default function ActivityPage() {
  const t = useChartTokens();
  const [date] = useSelectedDate();
  const { data, error, isLoading } = useActivity(date);

  if (isLoading) return <Loading />;
  if (error) return <LoadError error={error} />;
  if (!data) return null;

  return (
    <section className="max-w-6xl">
      <h1 className="mb-4 text-2xl font-semibold tracking-tight">Activity</h1>
      <DateNav shownDate={data.date} />

      <div className="grid gap-4 sm:grid-cols-3 xl:grid-cols-6">
        {TOTALS.map((m) => (
          <StatTile key={m} label={metricDef(m).label} value={formatMetric(m, data.totals[m])} />
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[2fr_1fr]">
        <ChartCard
          title="Steps by hour"
          ask={`How active was I on ${data.date}?`}
          table={{
            columns: ["Hour", "Steps", "Calories"],
            rows: data.hourly.map((h) => [hourLabel(h.start), h.steps, formatNumber(h.calories)]),
          }}
        >
          <Chart option={stepsChart(t, data)} height={240} label="Steps per hour" />
        </ChartCard>
        <ChartCard
          title="Activity level"
          subtitle="Minutes at each intensity"
          table={{
            columns: ["Level", "Time"],
            rows: LEVELS.map((l) => [l.label, formatMinutes(data.level_minutes[l.key] ?? 0)]),
          }}
        >
          <Chart option={levelsChart(t, data)} height={240} label="Minutes at each activity level" />
        </ChartCard>
      </div>

      <div className="mt-4">
        <ChartCard
          title="Stress through the day"
          ask={`What drove my stress on ${data.date}?`}
          subtitle={`Day average ${formatNumber(data.stress_avg)} / 100 · only calm, awake minutes are scored`}
          table={{
            columns: ["Time", "Stress"],
            rows: data.stress.map(([ms, v]) => [timeLabel(ms), formatNumber(v)]),
          }}
        >
          {data.stress.length ? (
            <Chart option={stressChart(t, data)} height={220} label="Stress level through the day" />
          ) : (
            <p className="py-8 text-sm text-slate-500">Not enough calm, awake time with heart-rate data.</p>
          )}
        </ChartCard>
      </div>

      <section className="mt-4 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="mb-2 text-sm font-semibold">Workouts</h2>
        {data.workouts.length === 0 ? (
          <p className="text-sm text-slate-500">No workouts recorded.</p>
        ) : (
          <DataTable
            data={{
              columns: ["Start", "Type", "Duration", "Avg HR", "Max HR", "Calories", "Distance"],
              rows: data.workouts.map((w) => [
                formatClock(w.start),
                w.activity_type.replaceAll("_", " ").toLowerCase(),
                formatMinutes(w.duration_min),
                formatNumber(w.avg_hr),
                formatNumber(w.max_hr),
                formatNumber(w.calories),
                formatMetric("distance_m", w.distance_m),
              ]),
            }}
          />
        )}
      </section>
    </section>
  );
}
