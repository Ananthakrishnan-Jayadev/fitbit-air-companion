import type { TodayResponse } from "../api/types.ts";
import { DataTable } from "../components/ChartCard.tsx";
import { useChartTokens } from "../components/charts/tokens.ts";
import DateNav from "../components/DateNav.tsx";
import Meter from "../components/Meter.tsx";
import { LoadError, Loading } from "../components/PageState.tsx";
import StatTile from "../components/StatTile.tsx";
import { formatMinutes, formatNumber } from "../format.ts";
import { useToday } from "../hooks/useData.ts";
import { useSelectedDate } from "../hooks/useSelectedDate.ts";
import { FLAG_TEXT, formatMetric, metricDef } from "../metrics.ts";

const BASELINE_ROWS = [
  "resting_hr",
  "hrv_rmssd_ms",
  "spo2_avg",
  "respiratory_rate",
  "skin_temp_delta_c",
  "sleep_min",
];
const ACTIVITY_TILES = ["steps", "active_zone_minutes", "total_calories", "distance_m", "sedentary_min"];

const COMPONENT_LABELS: Record<string, string> = {
  hrv: "HRV",
  resting_hr: "Resting heart rate",
  sleep: "Sleep",
  respiratory_rate: "Breathing rate",
  duration: "Duration vs need",
  efficiency: "Efficiency",
  restorative: "Deep + REM",
  consistency: "Bedtime consistency",
};

type Band = { label: string; tone: "good" | "warning" | "critical" };

function recoveryBand(score: number): Band {
  if (score >= 67) return { label: "High", tone: "good" };
  if (score >= 34) return { label: "Moderate", tone: "warning" };
  return { label: "Low", tone: "critical" };
}

function RecoveryHero({ recovery }: { recovery: number | null }) {
  const t = useChartTokens();
  const band = recovery === null ? null : recoveryBand(recovery);
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
      <div className="text-sm text-slate-600 dark:text-slate-400">Recovery</div>
      {recovery === null || band === null ? (
        <p className="mt-2 text-sm text-slate-500">
          Not enough history yet. Recovery needs about a week of data to learn your normal.
        </p>
      ) : (
        <>
          <div className="mt-1 flex items-baseline gap-3">
            <span className="text-5xl font-semibold">{formatNumber(recovery)}</span>
            <span className="flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-300">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: t[band.tone] }}
                aria-hidden
              />
              {band.label}
            </span>
          </div>
          <div className="mt-3">
            <Meter value={recovery} color={t[band.tone]} label="Recovery out of 100" />
          </div>
          <p className="mt-2 text-xs text-slate-500">
            HRV, resting heart rate, sleep and breathing compared with your last 30 days.
          </p>
        </>
      )}
    </div>
  );
}

function Flags({ flags }: { flags: string[] }) {
  return (
    <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
      <p className="font-medium">⚠ Worth paying attention to</p>
      <ul className="mt-1 list-disc pl-5">
        {flags.map((flag) => (
          <li key={flag}>{FLAG_TEXT[flag] ?? flag}</li>
        ))}
      </ul>
      <p className="mt-2 text-xs opacity-80">
        Patterns in your own data, not a diagnosis. See a doctor if you feel unwell.
      </p>
    </div>
  );
}

function zWords(z: number | null | undefined): string {
  if (z === null || z === undefined) return "—";
  if (z >= 2) return "↑ Well above";
  if (z >= 1) return "↑ Above";
  if (z <= -2) return "↓ Well below";
  if (z <= -1) return "↓ Below";
  return "Normal";
}

function Breakdown({ title, components }: { title: string; components?: Record<string, number | null> }) {
  const t = useChartTokens();
  const entries = Object.entries(components ?? {}).filter(
    (entry): entry is [string, number] => entry[1] !== null,
  );
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <h2 className="mb-3 text-sm font-semibold">{title}</h2>
      {entries.length === 0 ? (
        <p className="text-sm text-slate-500">Not available for this day.</p>
      ) : (
        <ul className="space-y-2">
          {entries.map(([key, value]) => (
            <li key={key} className="grid grid-cols-[9rem_1fr_2.5rem] items-center gap-3 text-sm">
              <span className="text-slate-600 dark:text-slate-400">{COMPONENT_LABELS[key] ?? key}</span>
              <Meter value={value} color={t["series-1"]} label={`${COMPONENT_LABELS[key] ?? key} score`} />
              <span className="text-right tabular-nums">{formatNumber(value)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function BaselineTable({ data }: { data: TodayResponse }) {
  const rows = BASELINE_ROWS.filter((m) => data.metrics[m] !== undefined || data.baselines[m]).map(
    (m) => {
      const band = data.baselines[m];
      return [
        metricDef(m).label,
        formatMetric(m, data.metrics[m]),
        band ? `${formatMetric(m, band.low)} – ${formatMetric(m, band.high)}` : "Learning…",
        zWords(data.z[m]),
      ];
    },
  );
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <h2 className="mb-2 text-sm font-semibold">Compared with your normal</h2>
      <DataTable data={{ columns: ["Metric", "Today", "Your normal range", "Status"], rows }} />
    </section>
  );
}

export default function TodayPage() {
  const [date] = useSelectedDate();
  const { data, error, isLoading } = useToday(date);

  if (isLoading) return <Loading />;
  if (error) return <LoadError error={error} />;
  if (!data) return null;

  const sleepJson = data.components.sleep;
  const target = data.strain_target;
  return (
    <section className="max-w-6xl">
      <h1 className="mb-4 text-2xl font-semibold tracking-tight">Today</h1>
      <DateNav shownDate={data.date} />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-[2fr_1fr_1fr_1fr]">
        <RecoveryHero recovery={data.recovery} />
        <StatTile
          label="Sleep"
          value={formatNumber(data.sleep_perf)}
          unit="/100"
          detail={sleepJson?.asleep_min ? `${formatMinutes(sleepJson.asleep_min)} asleep` : undefined}
        />
        <StatTile
          label="Strain"
          value={formatNumber(data.strain, 1)}
          unit="/21"
          detail={target ? `Suggested today: ${target[0]}–${target[1]}` : undefined}
        />
        <StatTile
          label="Stress"
          value={formatNumber(data.stress_avg)}
          unit="/100"
          detail="Heart rate above resting while sitting still"
        />
      </div>

      {data.flags.length > 0 && <Flags flags={data.flags} />}

      <div className="mt-4 grid gap-4 sm:grid-cols-3 xl:grid-cols-5">
        {ACTIVITY_TILES.map((m) => (
          <StatTile key={m} label={metricDef(m).label} value={formatMetric(m, data.metrics[m])} />
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <BaselineTable data={data} />
        <div className="grid gap-4">
          <Breakdown title="Recovery breakdown" components={data.components.recovery?.components} />
          <Breakdown title="Sleep breakdown" components={sleepJson?.components} />
        </div>
      </div>
    </section>
  );
}
