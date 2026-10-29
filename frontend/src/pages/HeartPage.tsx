import type { EChartsOption } from "echarts";
import ChartCard from "../components/ChartCard.tsx";
import Chart from "../components/charts/Chart.tsx";
import { axisTooltip, firstParam, grid, timeAxis, timeLabel, valueAxis } from "../components/charts/options.ts";
import { useChartTokens } from "../components/charts/tokens.ts";
import TrendChart from "../components/charts/TrendChart.tsx";
import DateNav from "../components/DateNav.tsx";
import { LoadError, Loading } from "../components/PageState.tsx";
import StatTile from "../components/StatTile.tsx";
import { formatNumber } from "../format.ts";
import { useHeart } from "../hooks/useData.ts";
import { useSelectedDate } from "../hooks/useSelectedDate.ts";

const ZONE_LABELS: Record<string, string> = {
  LIGHT: "Light",
  MODERATE: "Moderate (fat burn)",
  VIGOROUS: "Vigorous (cardio)",
  PEAK: "Peak",
};

export default function HeartPage() {
  const t = useChartTokens();
  const [date] = useSelectedDate();
  const { data, error, isLoading } = useHeart(date);

  if (isLoading) return <Loading />;
  if (error) return <LoadError error={error} />;
  if (!data) return null;

  const option: EChartsOption = {
    grid: grid(),
    tooltip: axisTooltip(t, (raw) => {
      const value = firstParam(raw).value;
      if (!Array.isArray(value)) return "";
      const [ms, bpm] = value as [number, number];
      return `${timeLabel(ms)}<br/><b>${Math.round(bpm)} bpm</b>`;
    }),
    xAxis: timeAxis(t),
    yAxis: valueAxis(t, { scale: true, name: "bpm", nameTextStyle: { color: t["ink-muted"] } }),
    series: [
      {
        type: "line",
        name: "Heart rate",
        data: data.samples,
        symbol: "none",
        lineStyle: { width: 1.5, color: t["series-1"], join: "round" },
        markLine:
          data.resting_hr === null
            ? undefined
            : {
                silent: true,
                symbol: "none",
                lineStyle: { color: t.axis, width: 1, type: "solid" },
                label: {
                  formatter: `Resting ${Math.round(data.resting_hr)}`,
                  color: t["ink-2"],
                  position: "insideEndTop",
                },
                data: [{ yAxis: data.resting_hr }],
              },
      },
    ],
  };

  return (
    <section className="max-w-6xl">
      <h1 className="mb-4 text-2xl font-semibold tracking-tight">Heart</h1>
      <DateNav shownDate={data.date} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Resting heart rate" value={formatNumber(data.resting_hr)} unit="bpm" />
        <StatTile label="HRV (RMSSD)" value={formatNumber(data.hrv_rmssd_ms)} unit="ms" />
        <StatTile label="Lowest" value={formatNumber(data.min_bpm)} unit="bpm" />
        <StatTile label="Highest" value={formatNumber(data.max_bpm)} unit="bpm" />
      </div>

      <div className="mt-4">
        <ChartCard
          title="Heart rate through the day"
          subtitle={`${formatNumber(data.sample_count)} readings, simplified for display (peaks kept)`}
          table={{
            columns: ["Time", "bpm"],
            rows: data.samples.map(([ms, bpm]) => [timeLabel(ms), Math.round(bpm)]),
          }}
        >
          {data.samples.length === 0 ? (
            <p className="py-8 text-sm text-slate-500">No heart-rate readings for this day.</p>
          ) : (
            <Chart option={option} height={300} label="Heart rate through the selected day" />
          )}
        </ChartCard>
      </div>

      {data.zones.length > 0 && (
        <section className="mt-4 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
          <h2 className="mb-2 text-sm font-semibold">Your heart-rate zones (from Google)</h2>
          <ul className="grid gap-1 text-sm sm:grid-cols-2">
            {data.zones.map((z) => (
              <li key={z.zone} className="flex justify-between gap-4">
                <span className="text-slate-600 dark:text-slate-400">{ZONE_LABELS[z.zone] ?? z.zone}</span>
                <span className="tabular-nums">
                  {z.min_bpm ?? "—"}–{z.max_bpm ?? "—"} bpm
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <TrendChart metric="resting_hr" days={60} end={data.date} />
        <TrendChart metric="hrv_rmssd_ms" days={60} end={data.date} />
      </div>
    </section>
  );
}
