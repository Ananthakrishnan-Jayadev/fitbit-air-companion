// Shared ECharts building blocks: recessive hairline axes, one y-axis, themed tooltip.
import type {
  GridComponentOption,
  TooltipComponentOption,
  XAXisComponentOption,
  YAXisComponentOption,
} from "echarts";
import type { ChartTokens } from "./tokens.ts";

export const FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif';

export function grid(): GridComponentOption {
  return { left: 8, right: 16, top: 16, bottom: 8, containLabel: true };
}

export function axisTooltip(t: ChartTokens, formatter: (raw: unknown) => string): TooltipComponentOption {
  return {
    trigger: "axis",
    backgroundColor: t["surface-1"],
    borderColor: t.grid,
    textStyle: { color: t["ink-1"], fontFamily: FONT, fontSize: 12 },
    axisPointer: { type: "line", lineStyle: { color: t.axis, width: 1 } },
    formatter,
  };
}

export function itemTooltip(t: ChartTokens, formatter: (raw: unknown) => string): TooltipComponentOption {
  return { ...axisTooltip(t, formatter), trigger: "item" };
}

export function timeAxis(t: ChartTokens): XAXisComponentOption {
  return {
    type: "time",
    axisLine: { lineStyle: { color: t.axis, width: 1 } },
    axisTick: { show: false },
    axisLabel: { color: t["ink-muted"], fontFamily: FONT, hideOverlap: true },
    splitLine: { show: false },
  };
}

export function categoryAxis(t: ChartTokens, data: string[]): XAXisComponentOption {
  return {
    type: "category",
    data,
    axisLine: { lineStyle: { color: t.axis, width: 1 } },
    axisTick: { show: false },
    axisLabel: { color: t["ink-muted"], fontFamily: FONT, hideOverlap: true },
  };
}

export function valueAxis(t: ChartTokens, extra: YAXisComponentOption = {}): YAXisComponentOption {
  return {
    type: "value",
    splitLine: { lineStyle: { color: t.grid, width: 1, type: "solid" } },
    axisLabel: { color: t["ink-muted"], fontFamily: FONT },
    ...extra,
  } as YAXisComponentOption;
}

/** First data item of an axis/item tooltip callback. */
export interface TooltipParam {
  value?: unknown;
  axisValue?: unknown;
  name?: unknown;
  dataIndex?: number;
}

export function firstParam(raw: unknown): TooltipParam {
  const first: unknown = Array.isArray(raw) ? raw[0] : raw;
  return (first ?? {}) as TooltipParam;
}

export function timeLabel(ms: number): string {
  return new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
