import HeartDayChart from "../components/charts/HeartDayChart.tsx";
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
  const [date] = useSelectedDate();
  const { data, error, isLoading } = useHeart(date);

  if (isLoading) return <Loading />;
  if (error) return <LoadError error={error} />;
  if (!data) return null;

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
        <HeartDayChart data={data} />
      </div>

      {data.zones.length > 0 && (
        <section className="mt-4 rounded-lg border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
          <h2 className="mb-2 text-sm font-semibold">Your heart-rate zones (from Google)</h2>
          <ul className="grid gap-1 text-sm sm:grid-cols-2">
            {data.zones.map((z) => (
              <li key={z.zone} className="flex justify-between gap-4">
                <span className="text-stone-600 dark:text-stone-400">{ZONE_LABELS[z.zone] ?? z.zone}</span>
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
