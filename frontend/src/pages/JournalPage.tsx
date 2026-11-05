import { useState, type FormEvent } from "react";
import type { JournalEntry, Outcome, TagEffect } from "../api/types.ts";
import { DataTable } from "../components/ChartCard.tsx";
import { ChevronLeft, ChevronRight } from "../components/icons.tsx";
import { BUTTON, BUTTON_SECONDARY, INPUT } from "../components/settings/Card.tsx";
import { addDays, formatDayLabel, formatNumber, localTodayIso } from "../format.ts";
import { useCorrelations, useJournal, useSaveJournal, useTags } from "../hooks/useJournal.ts";
import { useSelectedDate } from "../hooks/useSelectedDate.ts";
import { metricDef } from "../metrics.ts";

const OUTCOMES: { key: Outcome; label: string }[] = [
  { key: "recovery", label: "Next-day recovery" },
  { key: "sleep_perf", label: "Sleep score that night" },
  { key: "hrv_rmssd_ms", label: "Next-day HRV" },
  { key: "resting_hr", label: "Next-day resting heart rate" },
  { key: "sleep_min", label: "Time asleep that night" },
];
const HISTORY_DAYS = 14;

function tagLabel(tag: string): string {
  return tag.replaceAll("_", " ");
}

/** Editor for one day; remounted (via key) when the day or saved entry changes. */
function EntryEditor({ date, entry, allTags }: { date: string; entry?: JournalEntry; allTags: string[] }) {
  const save = useSaveJournal();
  const [tags, setTags] = useState<string[]>(entry?.tags ?? []);
  const [note, setNote] = useState(entry?.note ?? "");
  const [custom, setCustom] = useState("");

  const options = [...new Set([...allTags, ...tags])];

  function toggle(tag: string) {
    setTags((current) => (current.includes(tag) ? current.filter((t) => t !== tag) : [...current, tag]));
  }

  function addCustom(event: FormEvent) {
    event.preventDefault();
    const tag = custom.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
    if (tag && !tags.includes(tag)) setTags([...tags, tag]);
    setCustom("");
  }

  return (
    <div className="rounded-lg border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
      <h2 className="font-condensed text-[1.35rem] font-extrabold uppercase leading-none">{formatDayLabel(date)}</h2>
      <p className="mb-3 text-xs text-stone-500">
        Tag what happened this day. It is compared with how you slept that night and recovered the next morning.
      </p>
      <div className="flex flex-wrap gap-2">
        {options.map((tag) => {
          const on = tags.includes(tag);
          return (
            <button
              key={tag}
              type="button"
              aria-pressed={on}
              onClick={() => toggle(tag)}
              className={`rounded-full border px-3 py-1 text-sm ${
                on
                  ? "border-cobalt bg-cobalt text-white"
                  : "border-stone-300 hover:bg-stone-100 dark:border-stone-700 dark:hover:bg-stone-800"
              }`}
            >
              {on ? "✓ " : ""}
              {tagLabel(tag)}
            </button>
          );
        })}
      </div>
      <form onSubmit={addCustom} className="mt-3 flex gap-2">
        <input
          className={INPUT}
          placeholder="Add your own tag"
          value={custom}
          maxLength={30}
          onChange={(e) => setCustom(e.target.value)}
          aria-label="Custom tag"
        />
        <button type="submit" className={BUTTON_SECONDARY} disabled={!custom.trim()}>
          Add
        </button>
      </form>
      <textarea
        className={`${INPUT} mt-3 w-full`}
        rows={3}
        maxLength={2000}
        placeholder="Notes (optional)"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        aria-label="Notes"
      />
      <div className="mt-3 flex items-center gap-3">
        <button
          type="button"
          className={BUTTON}
          disabled={save.isPending}
          onClick={() => save.mutate({ date, tags, note: note.trim() || null })}
        >
          Save
        </button>
        {save.isSuccess && <span className="text-sm text-emerald-600">Saved</span>}
        {save.error && <span className="text-sm text-red-600">{save.error.message}</span>}
      </div>
    </div>
  );
}

function effectText(outcome: Outcome, effect: TagEffect): string {
  const def = metricDef(outcome);
  const sign = effect.difference > 0 ? "+" : "";
  const value = def.minutes
    ? `${sign}${formatNumber(effect.difference)} min`
    : `${sign}${formatNumber(effect.difference, def.digits)}${def.unit && !def.unit.startsWith("/") ? ` ${def.unit}` : ""}`;
  return value;
}

function WhatAffectsYou() {
  const [outcome, setOutcome] = useState<Outcome>("recovery");
  const { data } = useCorrelations(outcome, 180);
  const effects = data?.effects ?? [];

  return (
    <section className="rounded-lg border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-condensed text-[1.35rem] font-extrabold uppercase leading-none">What affects you</h2>
        <select
          className={INPUT}
          value={outcome}
          onChange={(e) => setOutcome(e.target.value as Outcome)}
          aria-label="Outcome"
        >
          {OUTCOMES.map((o) => (
            <option key={o.key} value={o.key}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <p className="mb-3 text-xs text-stone-500">
        Average difference on days after a tag vs. logged days without it (last 180 days). A tag
        needs at least 5 days with and 5 without. "Clear" means the 95% range doesn't cross zero.
        Patterns, not proof of cause.
      </p>
      {effects.length === 0 ? (
        <p className="text-sm text-stone-500">
          Not enough journal data yet ({data?.logged_days ?? 0} days logged). Keep tagging your days.
        </p>
      ) : (
        <DataTable
          data={{
            columns: ["Tag", "Days tagged", "Difference", "95% range", "Signal"],
            rows: effects.map((e) => [
              tagLabel(e.tag),
              e.n_with,
              effectText(outcome, e),
              `${formatNumber(e.ci_low, 1)} to ${formatNumber(e.ci_high, 1)}`,
              e.confident ? "Clear" : "Not clear yet",
            ]),
          }}
        />
      )}
    </section>
  );
}

export default function JournalPage() {
  const [selected, setDate] = useSelectedDate();
  const today = localTodayIso();
  const date = selected ?? today;
  const historyStart = addDays(date, -(HISTORY_DAYS - 1));
  const journal = useJournal(historyStart, date);
  const tags = useTags();

  const entries = journal.data ?? [];
  const entry = entries.find((e) => e.date === date);
  const allTags = (tags.data ?? []).map((t) => t.tag);

  return (
    <section className="max-w-4xl">
      <h1 className="page-title">Journal</h1>
      <div className="mb-6 flex flex-wrap items-center gap-2">
        <button type="button" className={BUTTON_SECONDARY} onClick={() => setDate(addDays(date, -1))} aria-label="Previous day">
          <ChevronLeft />
        </button>
        <input
          type="date"
          className={INPUT}
          value={date}
          max={today}
          onChange={(e) => e.target.value && setDate(e.target.value)}
          aria-label="Day"
        />
        <button
          type="button"
          className={BUTTON_SECONDARY}
          disabled={date >= today}
          onClick={() => setDate(addDays(date, 1))}
          aria-label="Next day"
        >
          <ChevronRight />
        </button>
      </div>

      {journal.isLoading || tags.isLoading ? (
        <p className="text-sm text-stone-500">Loading…</p>
      ) : (
        <EntryEditor key={`${date}:${entry?.tags.join(",") ?? ""}:${entry?.note ?? ""}`} date={date} entry={entry} allTags={allTags} />
      )}

      <div className="mt-4">
        <WhatAffectsYou />
      </div>

      <section className="mt-4 rounded-lg border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
        <h2 className="mb-3 font-condensed text-[1.35rem] font-extrabold uppercase leading-none">Last {HISTORY_DAYS} days</h2>
        {entries.length === 0 ? (
          <p className="text-sm text-stone-500">No entries yet.</p>
        ) : (
          <DataTable
            data={{
              columns: ["Day", "Tags", "Note"],
              rows: [...entries].reverse().map((e) => [e.date, e.tags.map(tagLabel).join(", "), e.note ?? ""]),
            }}
          />
        )}
      </section>
    </section>
  );
}
