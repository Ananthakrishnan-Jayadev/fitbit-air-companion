import { useState, type FormEvent } from "react";
import type { Profile } from "../../api/types.ts";
import { useProfile, useSaveProfile } from "../../hooks/useProfile.ts";
import { BUTTON, Card, INPUT } from "./Card.tsx";

function toNumber(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
}

function ProfileForm({ initial }: { initial: Profile }) {
  const save = useSaveProfile();
  const [age, setAge] = useState(initial.age?.toString() ?? "");
  const [maxHr, setMaxHr] = useState(initial.max_hr?.toString() ?? "");
  const [sleepHours, setSleepHours] = useState(
    initial.sleep_need_min ? (initial.sleep_need_min / 60).toString() : "",
  );

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const hours = toNumber(sleepHours);
    save.mutate({
      age: toNumber(age),
      max_hr: toNumber(maxHr),
      sleep_need_min: hours === null ? null : Math.round(hours * 60),
    });
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-3 sm:grid-cols-3">
      <label className="flex flex-col gap-1 text-sm">
        Age
        <input className={INPUT} type="number" min={10} max={110} value={age} onChange={(e) => setAge(e.target.value)} />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Max heart rate (bpm)
        <input
          className={INPUT}
          type="number"
          min={100}
          max={230}
          placeholder="auto from age"
          value={maxHr}
          onChange={(e) => setMaxHr(e.target.value)}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Sleep need (hours)
        <input
          className={INPUT}
          type="number"
          min={4}
          max={12}
          step={0.25}
          value={sleepHours}
          onChange={(e) => setSleepHours(e.target.value)}
        />
      </label>
      <div className="flex items-center gap-3 sm:col-span-3">
        <button type="submit" className={BUTTON} disabled={save.isPending}>
          Save profile
        </button>
        {save.isSuccess && <span className="text-sm text-emerald-600">Saved</span>}
        {save.error && <span className="text-sm text-red-600">{save.error.message}</span>}
      </div>
    </form>
  );
}

export default function ProfileCard() {
  const { data } = useProfile();
  return (
    <Card title="Profile">
      <p className="mb-3 text-sm text-slate-600 dark:text-slate-400">
        Used for strain and sleep scoring (Phase 3). Leave max heart rate empty to estimate it from age.
      </p>
      {data ? <ProfileForm initial={data} /> : <p className="text-sm text-slate-500">Loading…</p>}
    </Card>
  );
}
