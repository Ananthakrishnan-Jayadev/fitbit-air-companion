import type { ReactNode } from "react";

export type Tone = "ok" | "warn" | "error";

const DOT: Record<Tone, string> = {
  ok: "bg-emerald-500",
  warn: "bg-amber-500",
  error: "bg-red-500",
};

export function StatusDot({ tone }: { tone: Tone }) {
  return <span className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${DOT[tone]}`} aria-hidden />;
}

export function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
      <h2 className="mb-3 font-condensed text-[1.35rem] font-extrabold uppercase leading-none">{title}</h2>
      {children}
    </section>
  );
}

export const BUTTON =
  "rounded-md bg-stone-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-stone-700 disabled:opacity-50 dark:bg-stone-100 dark:text-stone-900 dark:hover:bg-stone-300";

export const BUTTON_SECONDARY =
  "inline-flex items-center justify-center gap-1.5 rounded-md border border-stone-300 px-3 py-1.5 text-sm font-medium hover:bg-stone-100 disabled:opacity-50 dark:border-stone-700 dark:hover:bg-stone-800";

export const INPUT =
  "rounded-md border border-stone-300 bg-white px-2 py-1 text-sm dark:border-stone-700 dark:bg-stone-950";
