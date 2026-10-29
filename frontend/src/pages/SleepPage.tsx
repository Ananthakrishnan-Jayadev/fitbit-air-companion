import type { EChartsOption } from "echarts";
import type { Point, SleepStageOut } from "../api/types.ts";
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
import { addDays, formatClock, formatMinutes, formatNumber } from "../format.ts";
import { useSleep, useSleepRange } from "../hooks/useData.ts";
import { useSelectedDate } from "../hooks/useSelectedDate.ts";

// Bottom to top: deeper sleep sits lower, like a classic hypnogram.
const STAGE_ORDER = ["deep", "light", "rem", "awake"];
const STAGE_LABELS: Record<string, string> = {
  deep: "Deep",
  light: "Light",
  rem: "REM",
  awake: "Awake",
  asleep: "Asleep",
};

function hypnogram(t: ChartTokens, stages: SleepStageOut[]): EChartsOption {
  const present = new Set(stages.map((s) => s.stage));
  // "asleep" only appears in classic (non-staged) logs.
  const categories = present.has("asleep") ? [...STAGE_ORDER, "asleep"] : STAGE_ORDER;
  const data: [number, string][] = [];
  for (const s of stages) {
    data.push([Date.parse(s.start), STAGE_LABELS[s.stage] ?? s.stage]);
  }
  const last = stages[stages.length - 1];
  if (last) data.push([Date.parse(last.end), STAGE_LABELS[last.stage] ?? last.stage]);
  return {
    grid: grid(),
    tooltip: axisTooltip(t, (raw) => {
      const value = firstParam(raw).value;
      if (!Array.isArray(value)) return "";
      return `${timeLabel(Number(value[0]))}<br/><b>${String(value[1])}</b>`;
    }),
    xAxis: timeAxis(t),
    yAxis: {
      type: "category",
      data: categories.map((c) => STAGE_LABELS[c] ?? c),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: t["ink-muted"] },
      splitLine: { show: true, lineStyle: { color: t.grid, width: 1 } },
    },
    series: [
      {
        type: "line",
        step: "end",
        data,
        symbol: "none",
        lineStyle: { width: 2, color: t["series-1"] },
      },
    ],
  };
}

function overnightLine(t: ChartTokens, points: Point[], unit: string, digits: number): EChartsOption {
  return {
    grid: grid(),
    tooltip: axisTooltip(t, (raw) => {
      const value = firstParam(raw).value;
      if (!Array.isArray(value)) return "";
      const [ms, v] = value as [number, number];
      return `${timeLabel(ms)}<br/><b>${formatNumber(v, digits)} ${unit}</b>`;
    }),
    xAxis: timeAxis(t),
    yAxis: valueAxis(t, { scale: true }),
    series: [
      {
        type: "line",
        data: points,
        symbol: "none",
        lineStyle: { width: 2, color: t["series-1"] },
      },
    ],
  };
}

function stageBars(t: ChartTokens, minutes: Record<string, number>): EChartsOption {
  const stages = STAGE_ORDER.filter((s) => minutes[s] !== undefined);
  return {
    grid: grid(),
    tooltip: itemTooltip(t, (raw) => {
      const p = firstParam(raw);
      return `${String(p.name)}<br/><b>${formatMinutes(Number(p.value))}</b>`;
    }),
    xAxis: categoryAxis(t, stages.map((s) => STAGE_LABELS[s] ?? s)),
    yAxis: valueAxis(t, { axisLabel: { color: t["ink-muted"], formatter: (v: number) => formatMinutes(v) } }),
    series: [
      {
        type: "bar",
        data: stages.map((s) => Math.round(minutes[s] ?? 0)),
        barMaxWidth: 24,
        itemStyle: { color: t["series-1"], borderRadius: [4, 4, 0, 0] },
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

export default function SleepPage() {
  const t = useChartTokens();
  const [date] = useSelectedDate();
  const { data, error, isLoading } = useSleep(date);
  const rangeEnd = data?.date;
  const recent = useSleepRange(rangeEnd ? addDays(rangeEnd, -13) : undefined, rangeEnd);

  if (isLoading) return <Loading />;
  if (error) return <LoadError error={error} />;
  if (!data) return null;

  const night = data.night;
  const asleep = data.components.asleep_min;
  return (
    <section className="max-w-6xl">
      <h1 className="mb-4 text-2xl font-semibold tracking-tight">Sleep</h1>
      <DateNav shownDate={data.date} />

      {!night ? (
        <p className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700">
          No sleep recorded for the night before this day.
        </p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile label="Sleep score" value={formatNumber(data.score)} unit="/100" />
            <StatTile
              label="Time asleep"
              value={formatMinutes(asleep)}
              detail={`${formatMinutes(night.duration_min)} in bed`}
            />
            <StatTile
              label="Bedtime → wake"
              value={`${formatClock(night.start)} → ${formatClock(night.end)}`}
            />
            <StatTile
              label="Efficiency"
              value={formatNumber(night.efficiency)}
              unit="%"
              detail="Share of time in bed spent asleep"
            />
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <StatTile label="Blood oxygen (avg)" value={formatNumber(data.spo2_avg, 1)} unit="%" />
            <StatTile label="Breathing rate" value={formatNumber(data.respiratory_rate, 1)} unit="br/min" />
            <StatTile
              label="Skin temperature"
              value={data.skin_temp_delta_c === null ? "—" : `${data.skin_temp_delta_c > 0 ? "+" : ""}${formatNumber(data.skin_temp_delta_c, 2)}`}
              unit="°C vs usual"
            />
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-[2fr_1fr]">
            <ChartCard
              title="Sleep stages"
              table={{
                columns: ["From", "To", "Stage"],
                rows: data.stages.map((s) => [formatClock(s.start), formatClock(s.end), STAGE_LABELS[s.stage] ?? s.stage]),
              }}
            >
              <Chart option={hypnogram(t, data.stages)} height={220} label="Sleep stages through the night" />
            </ChartCard>
            <ChartCard
              title="Time in each stage"
              table={{
                columns: ["Stage", "Time"],
                rows: Object.entries(data.stage_minutes).map(([s, m]) => [STAGE_LABELS[s] ?? s, formatMinutes(m)]),
              }}
            >
              <Chart option={stageBars(t, data.stage_minutes)} height={220} label="Minutes in each sleep stage" />
            </ChartCard>
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <ChartCard
              title="Blood oxygen overnight"
              table={{ columns: ["Time", "SpO2 %"], rows: data.spo2.map(([ms, v]) => [timeLabel(ms), formatNumber(v, 1)]) }}
            >
              {data.spo2.length ? (
                <Chart option={overnightLine(t, data.spo2, "%", 1)} height={200} label="Blood oxygen overnight" />
              ) : (
                <p className="py-8 text-sm text-slate-500">No SpO2 readings.</p>
              )}
            </ChartCard>
            <ChartCard
              title="HRV overnight"
              table={{ columns: ["Time", "RMSSD ms"], rows: data.hrv.map(([ms, v]) => [timeLabel(ms), formatNumber(v)]) }}
            >
              {data.hrv.length ? (
                <Chart option={overnightLine(t, data.hrv, "ms", 0)} height={200} label="HRV overnight" />
              ) : (
                <p className="py-8 text-sm text-slate-500">No HRV readings.</p>
              )}
            </ChartCard>
          </div>
        </>
      )}

      <section className="mt-4 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="mb-2 text-sm font-semibold">Last 14 nights</h2>
        <DataTable
          data={{
            columns: ["Night ending", "Bedtime", "Wake", "Asleep", "Deep", "REM", "Score"],
            rows: [...(recent.data ?? [])].reverse().map((n) => [
              n.date,
              n.bedtime_local,
              n.wake_local,
              formatMinutes(n.asleep_min),
              formatMinutes(n.stage_minutes.deep),
              formatMinutes(n.stage_minutes.rem),
              formatNumber(n.score),
            ]),
          }}
        />
      </section>
    </section>
  );
}
