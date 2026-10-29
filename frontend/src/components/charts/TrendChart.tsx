import type { EChartsOption } from "echarts";
import { formatDayLabel } from "../../format.ts";
import { useTrend } from "../../hooks/useData.ts";
import { formatMetric, metricDef } from "../../metrics.ts";
import ChartCard from "../ChartCard.tsx";
import Chart from "./Chart.tsx";
import { axisTooltip, firstParam, grid, timeAxis, valueAxis } from "./options.ts";
import { useChartTokens } from "./tokens.ts";

interface TrendChartProps {
  metric: string;
  days: number;
  end?: string;
  height?: number;
}

/** Daily values of one metric with your normal range (30-day mean ± 1 SD) shaded behind. */
export default function TrendChart({ metric, days, end, height = 240 }: TrendChartProps) {
  const t = useChartTokens();
  const { data } = useTrend(metric, days, end);
  const def = metricDef(metric);
  const scale = def.scale ?? 1;
  const points = data?.points ?? [];
  const hasBand = points.some((p) => p.baseline);

  const option: EChartsOption = {
    grid: grid(),
    tooltip: axisTooltip(t, (raw) => {
      const index = firstParam(raw).dataIndex;
      const point = index === undefined ? undefined : points[index];
      if (!point) return "";
      const normal = point.baseline
        ? `<br/>Normal ${formatMetric(metric, point.baseline.low)} – ${formatMetric(metric, point.baseline.high)}`
        : "";
      return `${formatDayLabel(point.date)}<br/><b>${formatMetric(metric, point.value)}</b>${normal}`;
    }),
    xAxis: timeAxis(t),
    yAxis: valueAxis(t, { scale: true }),
    series: [
      {
        type: "line",
        data: points.map((p) => [p.date, p.baseline ? p.baseline.low * scale : null]),
        stack: "band",
        symbol: "none",
        lineStyle: { opacity: 0 },
        silent: true,
      },
      {
        type: "line",
        data: points.map((p) => [
          p.date,
          p.baseline ? (p.baseline.high - p.baseline.low) * scale : null,
        ]),
        stack: "band",
        symbol: "none",
        lineStyle: { opacity: 0 },
        areaStyle: { color: t["series-1-wash"], opacity: 1 },
        silent: true,
      },
      {
        type: "line",
        name: def.label,
        data: points.map((p) => [p.date, p.value === null ? null : p.value * scale]),
        lineStyle: { width: 2, color: t["series-1"], cap: "round", join: "round" },
        itemStyle: { color: t["series-1"], borderColor: t["surface-1"], borderWidth: 2 },
        symbol: "circle",
        symbolSize: 8,
        showSymbol: false,
      },
    ],
  };

  return (
    <ChartCard
      title={def.label}
      subtitle={hasBand ? "Shaded: your normal range (30-day average ± 1 SD)" : `Last ${days} days`}
      table={{
        columns: ["Date", def.label, "Normal range"],
        rows: points.map((p) => [
          p.date,
          formatMetric(metric, p.value),
          p.baseline
            ? `${formatMetric(metric, p.baseline.low)} – ${formatMetric(metric, p.baseline.high)}`
            : "—",
        ]),
      }}
    >
      {points.length === 0 ? (
        <p className="py-8 text-sm text-slate-500">No data in this range.</p>
      ) : (
        <Chart option={option} height={height} label={`${def.label} over the last ${days} days`} />
      )}
    </ChartCard>
  );
}
