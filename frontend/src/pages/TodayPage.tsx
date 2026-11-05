import { motion } from "motion/react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { TodayResponse } from "../api/types.ts";
import AskLink from "../components/AskLink.tsx";
import BriefCard from "../components/BriefCard.tsx";
import { DataTable } from "../components/ChartCard.tsx";
import { useChartTokens } from "../components/charts/tokens.ts";
import DateNav from "../components/DateNav.tsx";
import { AlertTriangle, ChevronRight } from "../components/icons.tsx";
import Meter from "../components/Meter.tsx";
import CountUp from "../components/motion/CountUp.tsx";
import { LoadError, Loading } from "../components/PageState.tsx";
import { addDays, formatMinutes, formatNumber, formatWeekday } from "../format.ts";
import { useInsights } from "../hooks/useAI.ts";
import { useDaily, useToday } from "../hooks/useData.ts";
import { useSelectedDate } from "../hooks/useSelectedDate.ts";
import { FLAG_TEXT, formatMetric, metricDef, recoveryBand } from "../metrics.ts";
import { BASE } from "../motion.ts";

/*
 * Layout (design.md "Today"): one reading path for the morning check.
 *   1. Recovery, with its last 7 days, leads.
 *   2. Sleep and strain, the other two pillars, sit beside it (below on a phone).
 *   3. Warnings, then the coach's brief.
 *   4. The day in numbers, then what's behind the scores, for the deep dive.
 */

const BASELINE_ROWS = [
  "resting_hr",
  "hrv_rmssd_ms",
  "spo2_avg",
  "respiratory_rate",
  "skin_temp_delta_c",
  "sleep_min",
];
const DAY_STATS = ["steps", "active_zone_minutes", "total_calories", "distance_m", "sedentary_min"];

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

const SURFACE = "rounded-lg border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900";

function SectionHeading({ id, children }: { id: string; children: ReactNode }) {
  return (
    <h2 id={id} className="mb-3 text-base font-semibold tracking-tight">
      {children}
    </h2>
  );
}

function RecoveryPanel({ recovery, date }: { recovery: number | null; date: string }) {
  const t = useChartTokens();
  const verdict = useInsights(date).data?.daily_brief?.content.headline;
  const band = recovery === null ? null : recoveryBand(recovery);
  // The band's hue tints the whole panel; the label beside the number carries the meaning.
  const tint = band ? `color-mix(in oklab, ${t[band.tone]} 9%, transparent)` : undefined;

  return (
    <section
      aria-labelledby="recovery-heading"
      className={`${SURFACE} flex flex-col transition-colors duration-500`}
      style={{ backgroundImage: tint ? `linear-gradient(${tint}, ${tint})` : undefined }}
    >
      <div className="p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <h2 id="recovery-heading" className="text-sm font-medium text-stone-700 dark:text-stone-300">
            Recovery
          </h2>
          {band && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/70 px-2.5 py-0.5 text-xs font-medium text-stone-800 dark:bg-stone-950/40 dark:text-stone-100">
              <span aria-hidden className="h-2 w-2 rounded-full" style={{ backgroundColor: t[band.tone] }} />
              {band.label}
            </span>
          )}
        </div>

        {recovery === null || band === null ? (
          <p className="mt-3 max-w-prose text-sm text-stone-600 dark:text-stone-400">
            Not enough history yet. Recovery needs about a week of data to learn your normal.
          </p>
        ) : (
          <>
            <p className="mt-1 text-7xl font-semibold leading-none tracking-tight sm:text-8xl">
              <CountUp value={recovery} />
              <span className="ml-1 text-xl font-normal text-stone-500 sm:text-2xl">/100</span>
            </p>
            <div className="mt-4">
              <Meter value={recovery} color={t[band.tone]} label="Recovery out of 100" size="md" />
            </div>
            {verdict && <p className="mt-4 max-w-prose text-base font-medium">{verdict}</p>}
            <div className="mt-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
              <p className="text-xs text-stone-600 dark:text-stone-400">
                HRV, resting heart rate, sleep and breathing against your last 30 days.
              </p>
              <AskLink question={`Why is my recovery ${formatNumber(recovery)} on ${date}?`} label="Ask why" />
            </div>
          </>
        )}
      </div>
      <WeekStrip date={date} />
    </section>
  );
}

/** Last 7 days of recovery; each day opens that day. The selection slides between days. */
function WeekStrip({ date }: { date: string }) {
  const t = useChartTokens();
  const start = addDays(date, -6);
  const { data } = useDaily(start, date);
  const recoveryByDay = new Map((data ?? []).map((row) => [row.date, row.scores.recovery ?? null]));
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));

  return (
    <nav aria-label="Recovery, last 7 days" className="mt-auto border-t border-stone-900/10 px-2 py-2 dark:border-white/10">
      <ul className="grid grid-cols-7">
        {days.map((day) => {
          const value = recoveryByDay.get(day) ?? null;
          const band = value === null ? null : recoveryBand(value);
          const selected = day === date;
          return (
            <li key={day} className="relative">
              {selected && (
                <motion.span
                  layoutId="week-selected"
                  transition={BASE}
                  aria-hidden
                  className="absolute inset-0 rounded-lg bg-white shadow-sm ring-1 ring-stone-900/10 dark:bg-stone-800 dark:ring-white/10"
                />
              )}
              <Link
                to={`/?date=${day}`}
                aria-current={selected ? "date" : undefined}
                aria-label={`${formatWeekday(day)} ${day}: recovery ${value === null ? "not available" : `${formatNumber(value)}, ${band?.label}`}`}
                className="relative flex min-h-11 flex-col items-center rounded-lg py-1.5 text-xs hover:bg-white/60 dark:hover:bg-stone-800/60"
              >
                <span className="text-stone-600 dark:text-stone-400">{formatWeekday(day)}</span>
                <span className="text-sm font-semibold">{formatNumber(value)}</span>
                <span
                  aria-hidden
                  className="mt-1 h-1 w-4 rounded-full"
                  style={{ backgroundColor: band ? t[band.tone] : t.grid }}
                />
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

interface PillarProps {
  to: string;
  label: string;
  color: string;
  value: number | null;
  digits?: number;
  unit: string;
  max: number;
  target?: [number, number] | null;
  detail?: string;
}

/** Sleep or strain: the pillar's hue marks its dot and meter here and on its own page. */
function Pillar({ to, label, color, value, digits = 0, unit, max, target, detail }: PillarProps) {
  return (
    <Link
      to={to}
      className={`${SURFACE} group block p-5 transition-colors hover:border-stone-300 dark:hover:border-stone-700`}
    >
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2 text-sm font-medium text-stone-700 dark:text-stone-300">
          <span aria-hidden className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
          {label}
        </span>
        <ChevronRight className="h-4 w-4 text-stone-400 transition-transform group-hover:translate-x-0.5" />
      </div>
      <p className="mt-2 text-4xl font-semibold leading-none tracking-tight">
        {value === null ? "—" : <CountUp value={value} digits={digits} />}
        <span className="ml-1 text-base font-normal text-stone-500">{unit}</span>
      </p>
      <div className="mt-3">
        <Meter value={value} max={max} color={color} target={target} label={`${label} out of ${max}`} />
      </div>
      {detail && <p className="mt-2 text-xs text-stone-600 dark:text-stone-400">{detail}</p>}
    </Link>
  );
}

function Flags({ flags }: { flags: string[] }) {
  const described = flags.map((flag) => FLAG_TEXT[flag] ?? flag).join("; ");
  return (
    <section
      aria-labelledby="flags-heading"
      className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 dark:border-amber-800/70 dark:bg-amber-950/60 dark:text-amber-50"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 id="flags-heading" className="flex items-center gap-2 font-semibold">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Worth paying attention to
        </h2>
        <AskLink question={`Today's warnings: ${described}. What could they mean?`} />
      </div>
      <ul className="mt-2 list-disc space-y-0.5 pl-6">
        {flags.map((flag) => (
          <li key={flag}>{FLAG_TEXT[flag] ?? flag}</li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-amber-900 dark:text-amber-200">
        Patterns in your own data, not a diagnosis. See a doctor if you feel unwell.
      </p>
    </section>
  );
}

/** The day in numbers: one hairline grid, not a row of cards. */
function DayStats({ data }: { data: TodayResponse }) {
  const stats: [string, string][] = [
    ...DAY_STATS.map((m): [string, string] => [metricDef(m).label, formatMetric(m, data.metrics[m])]),
    ["Stress", data.stress_avg === null ? "—" : `${formatNumber(data.stress_avg)} /100`],
  ];
  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-stone-200 bg-stone-200 sm:grid-cols-3 lg:grid-cols-6 dark:border-stone-800 dark:bg-stone-800">
      {stats.map(([label, value]) => (
        <div key={label} className="bg-white px-4 py-3 dark:bg-stone-900">
          <dt className="text-xs text-stone-600 dark:text-stone-400">{label}</dt>
          <dd className="mt-0.5 text-lg font-semibold">{value}</dd>
        </div>
      ))}
    </dl>
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

function Breakdown({
  title,
  color,
  components,
}: {
  title: string;
  color: string;
  components?: Record<string, number | null>;
}) {
  const entries = Object.entries(components ?? {}).filter(
    (entry): entry is [string, number] => entry[1] !== null,
  );
  return (
    <section className={`${SURFACE} p-4`}>
      <h3 className="mb-3 text-sm font-semibold">{title}</h3>
      {entries.length === 0 ? (
        <p className="text-sm text-stone-500">Not available for this day.</p>
      ) : (
        <ul className="space-y-2.5">
          {entries.map(([key, value]) => (
            <li key={key} className="grid grid-cols-[minmax(0,9rem)_1fr_2.5rem] items-center gap-3 text-sm">
              <span className="truncate text-stone-600 dark:text-stone-400">{COMPONENT_LABELS[key] ?? key}</span>
              <Meter value={value} color={color} label={`${COMPONENT_LABELS[key] ?? key} score`} />
              <span className="text-right">{formatNumber(value)}</span>
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
    <section className={`${SURFACE} p-4`}>
      <h3 className="mb-2 text-sm font-semibold">Compared with your normal</h3>
      <DataTable data={{ columns: ["Metric", "Today", "Your normal range", "Status"], rows }} />
    </section>
  );
}

export default function TodayPage() {
  const t = useChartTokens();
  const [date] = useSelectedDate();
  const { data, error, isLoading } = useToday(date);

  if (isLoading) return <Loading />;
  if (error) return <LoadError error={error} />;
  if (!data) return null;

  const sleepJson = data.components.sleep;
  const target = data.strain_target;
  return (
    <div className="max-w-6xl">
      <h1 className="mb-4 text-2xl font-semibold tracking-tight">Today</h1>
      <DateNav shownDate={data.date} />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <RecoveryPanel recovery={data.recovery} date={data.date} />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
          <Pillar
            to={`/sleep?date=${data.date}`}
            label="Sleep"
            color={t.sleep}
            value={data.sleep_perf}
            unit="/100"
            max={100}
            detail={sleepJson?.asleep_min ? `${formatMinutes(sleepJson.asleep_min)} asleep` : undefined}
          />
          <Pillar
            to={`/activity?date=${data.date}`}
            label="Strain"
            color={t.strain}
            value={data.strain}
            digits={1}
            unit="/21"
            max={21}
            target={target}
            detail={target ? `Suggested today: ${target[0]}–${target[1]} (shaded)` : undefined}
          />
        </div>
      </div>

      <div className="mt-4 grid gap-4">
        {data.flags.length > 0 && <Flags flags={data.flags} />}
        <BriefCard date={data.date} />
      </div>

      <section aria-labelledby="day-heading" className="mt-10">
        <SectionHeading id="day-heading">Your day</SectionHeading>
        <DayStats data={data} />
      </section>

      <section aria-labelledby="behind-heading" className="mt-10">
        <SectionHeading id="behind-heading">Behind the scores</SectionHeading>
        <div className="grid gap-4 lg:grid-cols-2">
          <BaselineTable data={data} />
          <div className="grid content-start gap-4">
            <Breakdown
              title="Recovery breakdown"
              color={t["ink-2"]}
              components={data.components.recovery?.components}
            />
            <Breakdown title="Sleep breakdown" color={t.sleep} components={sleepJson?.components} />
          </div>
        </div>
      </section>
    </div>
  );
}
