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
  // Sparse metrics (weigh-ins) keep only days with a reading, joined by a line.
  const points = (data?.points ?? []).filter((p) => !def.sparse || p.value !== null);
  const hasBand = points.some((p) => p.baseline);
  // Sleep and strain metrics keep their pillar hue; everything else uses the series blue.
  const color = def.tone ? t[def.tone] : t["series-1"];
  const wash = def.tone ? t[def.tone === "sleep" ? "sleep-wash" : "strain-wash"] : t["series-1-wash"];

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
        id: "band-low",
        type: "line",
        data: points.map((p) => [p.date, p.baseline ? p.baseline.low * scale : null]),
        stack: "band",
        symbol: "none",
        lineStyle: { opacity: 0 },
        silent: true,
      },
      {
        id: "band-width",
        type: "line",
        data: points.map((p) => [
          p.date,
          p.baseline ? (p.baseline.high - p.baseline.low) * scale : null,
        ]),
        stack: "band",
        symbol: "none",
        lineStyle: { opacity: 0 },
        areaStyle: { color: wash, opacity: 1 },
        silent: true,
      },
      {
        id: "value",
        type: "line",
        name: def.label,
        data: points.map((p) => [p.date, p.value === null ? null : p.value * scale]),
        lineStyle: { width: 2, color, cap: "round", join: "round" },
        itemStyle: { color, borderColor: t["surface-1"], borderWidth: 2 },
        symbol: "circle",
        symbolSize: 8,
        showSymbol: Boolean(def.sparse),
      },
    ],
  };

  return (
    <ChartCard
      title={def.label}
      ask={`How has my ${def.label.toLowerCase()} trended over the last ${days} days?`}
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
        <p className="py-8 text-sm text-stone-500">No data in this range.</p>
      ) : (
        <Chart option={option} height={height} label={`${def.label} over the last ${days} days`} />
      )}
    </ChartCard>
  );
}
