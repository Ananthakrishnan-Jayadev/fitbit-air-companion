import HeartDayChart from "../components/charts/HeartDayChart.tsx";
import TrendChart from "../components/charts/TrendChart.tsx";
import DateNav from "../components/DateNav.tsx";
import { Page, Panel, WithAside } from "../components/PageLayout.tsx";
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

  const zones = (
    <Panel title="Your heart-rate zones">
      {data.zones.length === 0 ? (
        <p className="text-sm text-stone-600 dark:text-stone-400">No zone data from Google for this day.</p>
      ) : (
        <ul className="divide-y divide-stone-200 text-sm dark:divide-stone-800">
          {data.zones.map((z) => (
            <li key={z.zone} className="flex justify-between gap-4 py-2">
              <span className="text-stone-600 dark:text-stone-400">{ZONE_LABELS[z.zone] ?? z.zone}</span>
              <span>
                {z.min_bpm ?? "—"}–{z.max_bpm ?? "—"} bpm
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-xs text-stone-600 dark:text-stone-400">Zone limits as Google calculates them.</p>
    </Panel>
  );

  return (
    <Page>
      <h1 className="page-title">Heart</h1>
      <DateNav shownDate={data.date} />

      <WithAside
        label="Heart summary"
        aside={
          <>
            <div className="grid grid-cols-2 gap-4">
              <StatTile label="Resting heart rate" value={formatNumber(data.resting_hr)} unit="bpm" />
              <StatTile label="HRV (RMSSD)" value={formatNumber(data.hrv_rmssd_ms)} unit="ms" />
              <StatTile label="Lowest" value={formatNumber(data.min_bpm)} unit="bpm" />
              <StatTile label="Highest" value={formatNumber(data.max_bpm)} unit="bpm" />
            </div>
            {zones}
          </>
        }
      >
        <HeartDayChart data={data} />
        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          <TrendChart metric="resting_hr" days={60} end={data.date} />
          <TrendChart metric="hrv_rmssd_ms" days={60} end={data.date} />
        </div>
      </WithAside>
    </Page>
  );
}
