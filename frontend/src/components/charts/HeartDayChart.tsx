import type { EChartsOption } from "echarts";
import { useEffect, useMemo, useRef, useState } from "react";
import type { TimeWindow } from "../../api/data.ts";
import type { HeartResponse, Point } from "../../api/types.ts";
import { formatNumber } from "../../format.ts";
import { useHeartWindow } from "../../hooks/useData.ts";
import ChartCard from "../ChartCard.tsx";
import Chart, { type ChartInstance } from "./Chart.tsx";
import { axisTooltip, grid, timeAxis, timeLabel, valueAxis } from "./options.ts";
import { useChartTokens } from "./tokens.ts";

/** Below this visible span the chart swaps in full-resolution readings for the window. */
const DETAIL_SPAN_MS = 4 * 3_600_000;
const ZOOM_SETTLE_MS = 180;
const MIN_SPAN_MS = 10 * 60_000;
const NO_DETAIL: Point[] = [];

// Wheel/drag zoom inside the plot only with a precise pointer; on touch it would trap the
// page scroll. The slider strip below the chart works everywhere.
const FINE_POINTER = typeof window !== "undefined" && window.matchMedia("(pointer: fine)").matches;

interface ZoomState {
  startValue?: number;
  endValue?: number;
  start?: number;
  end?: number;
}

function visibleWindow(chart: ChartInstance): TimeWindow | null {
  const zoom = (chart.getOption() as unknown as { dataZoom?: ZoomState[] }).dataZoom?.[0];
  if (!zoom || zoom.startValue === undefined || zoom.endValue === undefined) return null;
  if ((zoom.start ?? 0) <= 0 && (zoom.end ?? 100) >= 100) return null;
  return { start: zoom.startValue, end: zoom.endValue };
}

/** One day of heart rate with drag/pinch zoom; zooming in fetches every reading in view. */
export default function HeartDayChart({ data }: { data: HeartResponse }) {
  const t = useChartTokens();
  const chart = useRef<ChartInstance | null>(null);
  const settle = useRef<number | undefined>(undefined);
  const [zoom, setZoom] = useState<TimeWindow | null>(null);

  const detailWindow = zoom && zoom.end - zoom.start <= DETAIL_SPAN_MS ? zoom : null;
  const detailQuery = useHeartWindow(data.date, detailWindow);
  const detail: Point[] =
    detailWindow && detailQuery.data?.date === data.date ? detailQuery.data.samples : NO_DETAIL;

  // A new day starts zoomed out; the overview line glides to the new day's shape.
  useEffect(() => {
    setZoom(null);
    chart.current?.dispatchAction({ type: "dataZoom", start: 0, end: 100 });
  }, [data.date]);

  useEffect(() => () => window.clearTimeout(settle.current), []);

  const onEvents = useMemo(
    () => ({
      // Fires on every drag frame; only settle on the window once the gesture pauses.
      datazoom: () => {
        window.clearTimeout(settle.current);
        settle.current = window.setTimeout(() => {
          if (chart.current) setZoom(visibleWindow(chart.current));
        }, ZOOM_SETTLE_MS);
      },
    }),
    [],
  );

  const option = useMemo<EChartsOption>(() => {
    const line = { width: 1.5, color: t["series-1"], join: "round" as const };
    return {
      grid: { ...grid(), bottom: 44 },
      tooltip: axisTooltip(t, (raw) => {
        const params = (Array.isArray(raw) ? raw : [raw]) as { seriesId?: string; value?: unknown }[];
        // Prefer the full-detail reading when the zoomed window has one.
        const hit = params.find((p) => p.seriesId === "detail") ?? params[0];
        if (!hit || !Array.isArray(hit.value)) return "";
        const [ms, bpm] = hit.value as Point;
        return `${timeLabel(ms)}<br/><b>${Math.round(bpm)} bpm</b>`;
      }),
      xAxis: timeAxis(t),
      yAxis: valueAxis(t, { scale: true, name: "bpm", nameTextStyle: { color: t["ink-muted"] } }),
      dataZoom: [
        {
          type: "inside",
          xAxisIndex: 0,
          filterMode: "none",
          minValueSpan: MIN_SPAN_MS,
          disabled: !FINE_POINTER,
          zoomOnMouseWheel: "ctrl",
          moveOnMouseWheel: false,
          moveOnMouseMove: true,
        },
        {
          type: "slider",
          xAxisIndex: 0,
          filterMode: "none",
          minValueSpan: MIN_SPAN_MS,
          height: 24,
          bottom: 6,
          borderColor: t.grid,
          backgroundColor: "transparent",
          fillerColor: t["series-1-wash"],
          dataBackground: { lineStyle: { color: t.axis, width: 1 }, areaStyle: { color: t.grid } },
          selectedDataBackground: {
            lineStyle: { color: t["series-1"], width: 1 },
            areaStyle: { color: t["series-1-wash"] },
          },
          handleStyle: { color: t["surface-1"], borderColor: t["ink-muted"] },
          moveHandleStyle: { color: t.axis },
          emphasis: { handleStyle: { borderColor: t["series-1"] } },
          textStyle: { color: t["ink-muted"] },
          labelFormatter: (value: number) => timeLabel(value),
          brushSelect: true,
        },
      ],
      series: [
        {
          id: "day",
          type: "line",
          name: "Heart rate",
          data: data.samples,
          symbol: "none",
          lineStyle: line,
          markLine: {
            silent: true,
            symbol: "none",
            lineStyle: { color: t.axis, width: 1, type: "solid" },
            label: {
              formatter: `Resting ${Math.round(data.resting_hr ?? 0)}`,
              color: t["ink-2"],
              position: "insideEndTop",
            },
            data: data.resting_hr === null ? [] : [{ yAxis: data.resting_hr }],
          },
        },
        {
          // Every reading in the zoomed window, drawn over the simplified day line.
          id: "detail",
          type: "line",
          name: "Heart rate (full detail)",
          data: detail,
          symbol: "none",
          lineStyle: line,
          // Don't morph a fresh window in from the previous one; it should simply sharpen.
          animation: false,
        },
      ],
    };
  }, [t, data, detail]);

  const zoomed = zoom !== null;
  const subtitle = zoomed
    ? `${timeLabel(zoom.start)} – ${timeLabel(zoom.end)} · ${
        detailWindow
          ? detailQuery.isFetching
            ? "loading every reading…"
            : `all ${formatNumber(detail.length)} readings`
          : "zoom in below 4 hours to see every reading"
      }`
    : `${formatNumber(data.sample_count)} readings, simplified (peaks kept). ${
        FINE_POINTER ? "Drag the strip below, or Ctrl/⌘ + scroll, to zoom." : "Drag the strip below to zoom."
      }`;

  const rows = (detail.length > 0 ? detail : data.samples).map(([ms, bpm]) => [timeLabel(ms), Math.round(bpm)]);

  return (
    <ChartCard
      title="Heart rate through the day"
      ask={`How did my heart rate look through the day on ${data.date}?`}
      subtitle={subtitle}
      table={{ columns: ["Time", "bpm"], rows }}
      actions={
        zoomed ? (
          <button
            type="button"
            className="text-xs text-stone-600 underline hover:text-stone-900 dark:text-stone-400 dark:hover:text-stone-100"
            onClick={() => chart.current?.dispatchAction({ type: "dataZoom", start: 0, end: 100 })}
          >
            Show whole day
          </button>
        ) : undefined
      }
    >
      {data.samples.length === 0 ? (
        <p className="py-8 text-sm text-stone-500">No heart-rate readings for this day.</p>
      ) : (
        <Chart
          option={option}
          height={320}
          label="Heart rate through the selected day; zoomable"
          onReady={(instance) => {
            chart.current = instance;
          }}
          onEvents={onEvents}
        />
      )}
    </ChartCard>
  );
}
