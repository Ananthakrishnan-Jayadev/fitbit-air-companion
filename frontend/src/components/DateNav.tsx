import { addDays, formatDayLabel } from "../format.ts";
import { useSelectedDate } from "../hooks/useSelectedDate.ts";
import { useToday } from "../hooks/useData.ts";
import { ChevronLeft, ChevronRight } from "./icons.tsx";

const BUTTON =
  "inline-flex items-center rounded-md border border-stone-300 px-2.5 py-1 text-sm hover:bg-stone-100 disabled:opacity-40 dark:border-stone-700 dark:hover:bg-stone-800";

/** Day picker shown above every chart on a day page (one filter row for the whole page). */
export default function DateNav({ shownDate }: { shownDate: string | undefined }) {
  const [, setDate] = useSelectedDate();
  const latest = useToday(undefined).data;
  const first = latest?.first_date ?? undefined;
  const last = latest?.last_date ?? undefined;
  const current = shownDate ?? last;

  if (!current) return null;
  return (
    <div className="mb-6 flex flex-wrap items-center gap-2">
      <button
        type="button"
        className={BUTTON}
        disabled={!first || current <= first}
        onClick={() => setDate(addDays(current, -1))}
        aria-label="Previous day"
      >
        <ChevronLeft />
      </button>
      <input
        type="date"
        className="rounded-md border border-stone-300 bg-white px-2 py-1 text-sm dark:border-stone-700 dark:bg-stone-950"
        value={current}
        min={first}
        max={last}
        onChange={(e) => e.target.value && setDate(e.target.value)}
        aria-label="Day"
      />
      <button
        type="button"
        className={BUTTON}
        disabled={!last || current >= last}
        onClick={() => setDate(addDays(current, 1))}
        aria-label="Next day"
      >
        <ChevronRight />
      </button>
      {last && current !== last && (
        <button type="button" className={BUTTON} onClick={() => setDate(last)}>
          Latest
        </button>
      )}
      <span className="ml-2 text-sm text-stone-500">{formatDayLabel(current)}</span>
    </div>
  );
}
