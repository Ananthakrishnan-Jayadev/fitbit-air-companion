import type { EChartsOption } from "echarts";
import { BarChart, LineChart } from "echarts/charts";
import {
  DataZoomInsideComponent,
  DataZoomSliderComponent,
  GridComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import ReactEChartsCore from "echarts-for-react/lib/core";
import { useReducedMotion } from "motion/react";
import { useMemo } from "react";

// Only the pieces we use, to keep the bundle small.
echarts.use([
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  MarkAreaComponent,
  DataZoomInsideComponent,
  DataZoomSliderComponent,
  CanvasRenderer,
]);

export type ChartInstance = echarts.ECharts;

interface ChartProps {
  option: EChartsOption;
  label: string; // accessible description of what the chart shows
  height?: number;
  onReady?: (chart: ChartInstance) => void;
  onEvents?: Record<string, (event: unknown) => void>;
}

/*
 * Fluid charts: one ECharts instance per chart for its whole life. New data is merged into
 * the existing series (matched by id), so a line glides from one day or metric to the next
 * instead of being redrawn. First paint is instant: motion is spent on change, not on load.
 */
const MOTION: EChartsOption = {
  animationDuration: 0,
  animationDurationUpdate: 480,
  animationEasingUpdate: "cubicInOut",
  // A day of heart rate is up to 5000 points; still smooth on canvas.
  animationThreshold: 8000,
};

function withStableIds(option: EChartsOption): EChartsOption {
  const series = option.series;
  if (!Array.isArray(series)) return option;
  return { ...option, series: series.map((s, i) => ({ ...s, id: s.id ?? `s${i}` })) };
}

export default function Chart({ option, label, height = 240, onReady, onEvents }: ChartProps) {
  const reduce = useReducedMotion();
  const merged = useMemo<EChartsOption>(
    () => ({ ...MOTION, ...withStableIds(option), animation: !reduce }),
    [option, reduce],
  );
  return (
    <div role="img" aria-label={label}>
      <ReactEChartsCore
        echarts={echarts}
        option={merged}
        // Series not in the new option are removed; the rest update (and animate) in place.
        replaceMerge={["series"]}
        style={{ height, width: "100%" }}
        opts={{ renderer: "canvas" }}
        onChartReady={onReady}
        onEvents={onEvents}
      />
    </div>
  );
}
