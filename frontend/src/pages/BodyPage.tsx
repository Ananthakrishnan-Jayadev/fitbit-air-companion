import { useState } from "react";
import TrendChart from "../components/charts/TrendChart.tsx";
import { Page, WithAside } from "../components/PageLayout.tsx";
import { LoadError, Loading } from "../components/PageState.tsx";
import StatTile from "../components/StatTile.tsx";
import { formatDayLabel, formatNumber } from "../format.ts";
import { useBody } from "../hooks/useData.ts";

const RANGES = [30, 90, 180, 365];

function signed(value: number | null, unit: string): string | undefined {
  if (value === null) return undefined;
  const sign = value > 0 ? "+" : value < 0 ? "−" : "±";
  return `${sign}${formatNumber(Math.abs(value), 1)} ${unit}`;
}

export default function BodyPage() {
  const [days, setDays] = useState(90);
  const { data, error, isLoading } = useBody(days);

  if (isLoading) return <Loading />;
  if (error) return <LoadError error={error} />;
  if (!data) return null;

  if (data.latest_date === null) {
    return (
      <Page>
        <h1 className="page-title">Body</h1>
        <p className="rounded-lg border border-dashed border-stone-300 p-8 text-center text-sm text-stone-600 dark:border-stone-700 dark:text-stone-400">
          No weigh-ins yet. Readings from your smart scale appear here once they reach Google
          Health (for Renpho: via Health Connect) and the next sync runs.
        </p>
      </Page>
    );
  }

  const change7 = signed(data.weight_change_7d, "kg");
  const change30 = signed(data.weight_change_30d, "kg");
  const fatChange = signed(data.body_fat_change_30d, "pts");

  return (
    <Page>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="page-title !mb-1">Body</h1>
          <p className="text-sm text-stone-500">Last weigh-in: {formatDayLabel(data.latest_date)}</p>
        </div>
        <div className="flex border border-stone-300 dark:border-stone-700" role="group" aria-label="Range">
          {RANGES.map((r) => (
            <button
              key={r}
              type="button"
              aria-pressed={r === days}
              onClick={() => setDays(r)}
              className={`px-3 py-1.5 text-sm ${
                r === days
                  ? "bg-cobalt text-white"
                  : "hover:bg-stone-100 dark:hover:bg-stone-800"
              }`}
            >
              {r}d
            </button>
          ))}
        </div>
      </div>

      <WithAside
        label="Latest body composition"
        aside={
          <>
            <div className="grid grid-cols-2 gap-4">
              <StatTile
                label="Weight"
                value={formatNumber(data.weight_kg, 1)}
                unit="kg"
                detail={[change7 && `${change7} in 7 days`, change30 && `${change30} in 30 days`]
                  .filter(Boolean)
                  .join(" · ") || undefined}
              />
              <StatTile
                label="Body fat"
                value={formatNumber(data.body_fat_pct, 1)}
                unit="%"
                detail={fatChange ? `${fatChange} in 30 days` : undefined}
              />
              <StatTile label="Lean mass" value={formatNumber(data.lean_mass_kg, 1)} unit="kg" detail="Weight minus fat mass" />
              <StatTile label="Fat mass" value={formatNumber(data.fat_mass_kg, 1)} unit="kg" />
            </div>
            <p className="text-xs text-stone-600 dark:text-stone-400">
              Weight can swing 1–2 kg day to day with water and food; watch the trend, not single
              readings. Scale body-fat estimates are approximate and work best for tracking change
              over time.
            </p>
          </>
        }
      >
        <div className="grid gap-6">
          <TrendChart metric="weight_kg" days={days} end={data.latest_date} height={300} />
          <TrendChart metric="body_fat_pct" days={days} end={data.latest_date} height={300} />
        </div>
      </WithAside>
    </Page>
  );
}
