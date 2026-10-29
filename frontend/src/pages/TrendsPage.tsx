import { useSearchParams } from "react-router-dom";
import TrendChart from "../components/charts/TrendChart.tsx";
import { METRICS, TREND_METRICS } from "../metrics.ts";

const RANGES = [30, 90, 180, 365];
const DEFAULT_METRIC = "recovery";

export default function TrendsPage() {
  const [params, setParams] = useSearchParams();
  const metric = TREND_METRICS.includes(params.get("metric") ?? "")
    ? (params.get("metric") as string)
    : DEFAULT_METRIC;
  const days = Number(params.get("days")) || 90;

  const update = (next: { metric?: string; days?: number }) =>
    setParams({ metric: next.metric ?? metric, days: String(next.days ?? days) });

  return (
    <section className="max-w-6xl">
      <h1 className="mb-4 text-2xl font-semibold tracking-tight">Trends</h1>

      {/* One filter row for the page. */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <select
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-950"
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
        <div className="flex overflow-hidden rounded-md border border-slate-300 dark:border-slate-700" role="group">
          {RANGES.map((r) => (
            <button
              key={r}
              type="button"
              aria-pressed={r === days}
              onClick={() => update({ days: r })}
              className={`px-3 py-1 text-sm ${
                r === days
                  ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                  : "hover:bg-slate-100 dark:hover:bg-slate-800"
              }`}
            >
              {r}d
            </button>
          ))}
        </div>
      </div>

      <TrendChart metric={metric} days={days} height={320} />
    </section>
  );
}
