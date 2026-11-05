import { Link } from "react-router-dom";
import type { TodayResponse } from "../api/types.ts";
import AskLink from "../components/AskLink.tsx";
import BriefCard from "../components/BriefCard.tsx";
import { DataTable } from "../components/ChartCard.tsx";
import DateNav from "../components/DateNav.tsx";
import { AlertTriangle, ArrowRight } from "../components/icons.tsx";
import Meter from "../components/Meter.tsx";
import CountUp from "../components/motion/CountUp.tsx";
import { Page, PANEL } from "../components/PageLayout.tsx";
import { LoadError, Loading } from "../components/PageState.tsx";
import { addDays, formatMinutes, formatNumber, formatWeekday } from "../format.ts";
import { useInsights } from "../hooks/useAI.ts";
import { useDaily, useToday } from "../hooks/useData.ts";
import { useSelectedDate } from "../hooks/useSelectedDate.ts";
import { FLAG_TEXT, formatMetric, metricDef, recoveryBand, type RecoveryTone } from "../metrics.ts";

/*
 * Today as a set of record sleeves (design.md "Blue Note Sleeve"): recovery is the big
 * sleeve, sleep and strain the small ones, the week a shelf of thumbnails. A sleeve is a flat
 * field of its colour with the score at poster scale; every sleeve names its band in words
 * and carries its proof line, so colour is never the only signal.
 */

interface Field {
  bg: string;
  fg: string;
}

const BAND_FIELD: Record<RecoveryTone, Field> = {
  good: { bg: "var(--good)", fg: "var(--on-good)" },
  warning: { bg: "var(--warning)", fg: "var(--on-warning)" },
  critical: { bg: "var(--critical)", fg: "var(--on-critical)" },
};
const SLEEP_FIELD: Field = { bg: "var(--sleep)", fg: "var(--on-sleep)" };
const STRAIN_FIELD: Field = { bg: "var(--strain)", fg: "var(--on-strain)" };
const EMPTY_FIELD: Field = { bg: "var(--grid)", fg: "var(--ink-1)" };

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

const RULE = { borderTop: "1px solid color-mix(in srgb, currentColor 40%, transparent)" };

/** "54 ms · normal 46–58" for the proof line under a score. */
function proof(data: TodayResponse, metric: string): string | null {
  const value = data.metrics[metric];
  if (value === null || value === undefined) return null;
  const band = data.baselines[metric];
  const normal = band ? ` · normal ${formatMetric(metric, band.low)}–${formatMetric(metric, band.high)}` : "";
  return `${formatMetric(metric, value)}${normal}`;
}

function RecoverySleeve({ data }: { data: TodayResponse }) {
  const recovery = data.recovery;
  const verdict = useInsights(data.date).data?.daily_brief?.content.headline;
  const band = recovery === null ? null : recoveryBand(recovery);
  const field = band ? BAND_FIELD[band.tone] : EMPTY_FIELD;
  const asleep = data.metrics.sleep_min;
  const proofs: [string, string | null][] = [
    ["HRV", proof(data, "hrv_rmssd_ms")],
    ["Resting HR", proof(data, "resting_hr")],
    ["Asleep", asleep === null || asleep === undefined ? null : formatMinutes(asleep)],
  ];

  return (
    <section
      aria-labelledby="recovery-heading"
      // A phone's first screen belongs to this sleeve; on wide screens it is a square.
      className="relative flex min-h-[64svh] flex-col overflow-hidden p-6 transition-colors duration-500 sm:p-7 lg:aspect-square lg:min-h-0"
      style={{ backgroundColor: field.bg, color: field.fg }}
    >
      <h2 id="recovery-heading" className="font-condensed text-[2rem] uppercase leading-none">
        <span className="font-black">Recovery</span>{" "}
        <span className="font-light">{band ? band.label : "learning"}</span>
      </h2>

      {recovery === null || band === null ? (
        <p className="mt-auto max-w-sm text-base">
          Not enough history yet. Recovery needs about a week of data to learn your normal.
        </p>
      ) : (
        <>
          <p className="mt-1 font-condensed text-2xl font-light">out of 100</p>
          {/* The score at poster scale, bleeding off the sleeve's right edge. */}
          <p className="-mr-[0.07em] mt-auto self-end font-condensed text-[clamp(9.5rem,52vw,19rem)] font-extrabold leading-[0.76] tracking-[-0.035em]">
            <CountUp value={recovery} />
          </p>
          {verdict && <p className="relative mt-5 max-w-md text-[17px] font-medium leading-snug">{verdict}</p>}
          <div
            className="relative mt-4 flex flex-wrap items-end justify-between gap-x-5 gap-y-2 pt-3 text-[13px]"
            style={RULE}
          >
            <dl className="flex flex-wrap gap-x-5 gap-y-1">
              {proofs
                .filter((entry): entry is [string, string] => entry[1] !== null)
                .map(([label, text]) => (
                  <div key={label} className="flex gap-1.5">
                    <dt className="font-semibold">{label}</dt>
                    <dd>{text}</dd>
                  </div>
                ))}
            </dl>
            <AskLink question={`Why is my recovery ${formatNumber(recovery)} on ${data.date}?`} label="Ask why" onField />
          </div>
        </>
      )}
    </section>
  );
}

interface PillarProps {
  to: string;
  name: string;
  field: Field;
  color: string;
  value: number | null;
  digits?: number;
  max: number;
  aside?: string;
  target?: [number, number] | null;
  lines: string[];
}

/** A small sleeve (the score on its field) beside its reading: meter, target, detail. */
function Pillar({ to, name, field, color, value, digits = 0, max, aside, target, lines }: PillarProps) {
  const id = `${name.toLowerCase()}-heading`;
  return (
    <section aria-labelledby={id} className="grid grid-cols-[8.5rem_minmax(0,1fr)] gap-5 sm:grid-cols-[11rem_minmax(0,1fr)]">
      <Link
        to={to}
        aria-label={`${name}: ${value === null ? "no score" : `${formatNumber(value, digits)} out of ${max}`}. Open the ${name} page`}
        className="relative flex aspect-square flex-col overflow-hidden p-3 transition-transform duration-150 hover:-translate-y-0.5"
        style={{ backgroundColor: field.bg, color: field.fg }}
      >
        <span className="font-condensed text-lg font-black uppercase leading-none">{name}</span>
        <span className="font-condensed text-sm font-light">/{max}</span>
        <span className="-mr-[0.06em] mt-auto self-end font-condensed text-[4.6rem] font-extrabold leading-[0.78] tracking-[-0.03em] sm:text-[6rem]">
          {value === null ? "—" : <CountUp value={value} digits={digits} />}
        </span>
      </Link>
      <div className="flex min-w-0 flex-col gap-2.5 pt-0.5">
        <h2 id={id} className="font-condensed text-[1.75rem] uppercase leading-none">
          <span className="font-extrabold">{name}</span> {aside && <span className="font-light">{aside}</span>}
        </h2>
        <Meter value={value} max={max} color={color} target={target} label={`${name} out of ${max}`} />
        {lines.map((line) => (
          <p key={line} className="text-sm text-stone-600 dark:text-stone-400">
            {line}
          </p>
        ))}
        <Link to={to} className="mt-auto inline-flex items-center gap-1 self-start text-sm font-semibold hover:underline">
          Open {name.toLowerCase()} <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </section>
  );
}

function strainLines(strain: number | null, target: [number, number] | null): string[] {
  if (!target) return [];
  if (strain === null) return [`Suggested today: ${target[0]}–${target[1]} (bracketed).`];
  if (strain > target[1]) return [`Above today's suggested ${target[0]}–${target[1]}. Easy from here.`];
  const low = Math.max(0, target[0] - strain);
  const high = target[1] - strain;
  return [
    low === 0
      ? `Inside today's suggested ${target[0]}–${target[1]}.`
      : `Room for ${formatNumber(low, 1)}–${formatNumber(high, 1)} more today (bracketed range).`,
  ];
}

function Flags({ flags }: { flags: string[] }) {
  const described = flags.map((flag) => FLAG_TEXT[flag] ?? flag).join("; ");
  return (
    <section
      aria-labelledby="flags-heading"
      className="border-2 border-stone-900 bg-white p-4 text-sm dark:border-stone-100 dark:bg-stone-900"
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
      <p className="mt-2 text-xs text-stone-600 dark:text-stone-400">
        Patterns in your own data, not a diagnosis. See a doctor if you feel unwell.
      </p>
    </section>
  );
}

/** The last 7 days as a shelf of thumbnail sleeves; the open day is outlined in cobalt. */
function WeekShelf({ date }: { date: string }) {
  const start = addDays(date, -6);
  const { data } = useDaily(start, date);
  const recoveryByDay = new Map((data ?? []).map((row) => [row.date, row.scores.recovery ?? null]));
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));

  return (
    <nav aria-labelledby="week-heading">
      <h2 id="week-heading" className="section-title">
        Last 7 days
      </h2>
      <ul className="grid grid-cols-7 gap-1.5 sm:gap-2">
        {days.map((day) => {
          const value = recoveryByDay.get(day) ?? null;
          const band = value === null ? null : recoveryBand(value);
          const field = band ? BAND_FIELD[band.tone] : EMPTY_FIELD;
          const selected = day === date;
          return (
            <li key={day}>
              <Link
                to={`/?date=${day}`}
                aria-current={selected ? "date" : undefined}
                aria-label={`${formatWeekday(day)} ${day}: recovery ${value === null ? "not available" : `${formatNumber(value)}, ${band?.label}`}`}
                className={`relative flex aspect-square flex-col overflow-hidden p-1.5 text-[11px] font-semibold transition-transform duration-150 hover:-translate-y-0.5 sm:p-2 sm:text-xs ${
                  selected ? "outline outline-[3px] outline-offset-2 outline-cobalt" : ""
                }`}
                style={{ backgroundColor: field.bg, color: field.fg }}
              >
                {formatWeekday(day)}
                <span className="-mr-[0.05em] mt-auto self-end font-condensed text-2xl font-extrabold leading-[0.8] sm:text-4xl">
                  {formatNumber(value)}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** The day in numbers: figures in the condensed voice under one ruled heading. */
function DayStats({ data }: { data: TodayResponse }) {
  const stats: [string, string][] = [
    ...DAY_STATS.map((m): [string, string] => [metricDef(m).label, formatMetric(m, data.metrics[m])]),
    ["Stress", data.stress_avg === null ? "—" : `${formatNumber(data.stress_avg)} /100`],
  ];
  return (
    <section aria-labelledby="day-heading">
      <h2 id="day-heading" className="section-title">
        Your day
      </h2>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 2xl:grid-cols-6">
        {stats.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-stone-600 dark:text-stone-400">{label}</dt>
            <dd className="font-condensed text-[1.9rem] font-extrabold leading-tight">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function zWords(z: number | null | undefined): string {
  if (z === null || z === undefined) return "—";
  if (z >= 2) return "Well above";
  if (z >= 1) return "Above";
  if (z <= -2) return "Well below";
  if (z <= -1) return "Below";
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
    <section className={PANEL}>
      <h3 className="mb-3 text-sm font-semibold">{title}</h3>
      {entries.length === 0 ? (
        <p className="text-sm text-stone-600 dark:text-stone-400">Not available for this day.</p>
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
    <section className={PANEL}>
      <h3 className="mb-2 text-sm font-semibold">Compared with your normal</h3>
      <DataTable data={{ columns: ["Metric", "Today", "Your normal range", "Status"], rows }} />
    </section>
  );
}

// Laptop: sleeve | pillars, with the brief below. Monitor (2xl): a third column for the brief
// and warnings, so the space beside the sleeves holds the coach's reading of the day.
const TOP_ROW =
  "grid gap-8 lg:grid-cols-[minmax(0,30rem)_minmax(0,1fr)] xl:grid-cols-[minmax(0,32.5rem)_minmax(0,1fr)] 2xl:grid-cols-[minmax(0,32.5rem)_minmax(0,1fr)_minmax(0,1fr)]";
const SECOND_ROW =
  "grid gap-8 lg:grid-cols-[minmax(0,30rem)_minmax(0,1fr)] xl:grid-cols-[minmax(0,32.5rem)_minmax(0,1fr)]";

export default function TodayPage() {
  const [date] = useSelectedDate();
  const { data, error, isLoading } = useToday(date);

  if (isLoading) return <Loading />;
  if (error) return <LoadError error={error} />;
  if (!data) return null;

  const sleepJson = data.components.sleep;
  const target = data.strain_target;
  const asleep = proof(data, "sleep_min");

  return (
    <Page>
      <h1 className="page-title">Today</h1>
      <DateNav shownDate={data.date} />

      <div className={TOP_ROW}>
        <RecoverySleeve data={data} />
        <div className="grid content-start gap-7">
          <Pillar
            to={`/sleep?date=${data.date}`}
            name="Sleep"
            field={SLEEP_FIELD}
            color="var(--sleep)"
            value={data.sleep_perf}
            max={100}
            aside={sleepJson?.asleep_min ? `${formatMinutes(sleepJson.asleep_min)} asleep` : undefined}
            lines={[asleep ? `Time asleep ${asleep}` : "No sleep recorded for last night."]}
          />
          <Pillar
            to={`/activity?date=${data.date}`}
            name="Strain"
            field={STRAIN_FIELD}
            color="var(--strain)"
            value={data.strain}
            digits={1}
            max={21}
            aside={target ? `suggested ${target[0]}–${target[1]}` : undefined}
            target={target}
            lines={strainLines(data.strain, target)}
          />
        </div>
        <div className="grid content-start gap-6 lg:col-span-2 2xl:col-span-1">
          {data.flags.length > 0 && <Flags flags={data.flags} />}
          <BriefCard date={data.date} />
        </div>
      </div>

      <div className={`mt-12 ${SECOND_ROW}`}>
        <WeekShelf date={data.date} />
        <DayStats data={data} />
      </div>

      <section aria-labelledby="behind-heading" className="mt-12">
        <h2 id="behind-heading" className="section-title">
          Behind the scores
        </h2>
        <div className="grid items-start gap-6 lg:grid-cols-2 2xl:grid-cols-3">
          <BaselineTable data={data} />
          <Breakdown
            title="Recovery breakdown"
            color="var(--series-1)"
            components={data.components.recovery?.components}
          />
          <Breakdown title="Sleep breakdown" color="var(--sleep)" components={sleepJson?.components} />
        </div>
      </section>
    </Page>
  );
}
