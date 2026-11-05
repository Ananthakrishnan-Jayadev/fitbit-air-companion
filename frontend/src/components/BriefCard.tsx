import { useState, type ReactNode } from "react";
import { formatDateTime } from "../format.ts";
import { useAIStatus, useGenerateInsight, useInsights } from "../hooks/useAI.ts";
import { BUTTON_SECONDARY } from "./settings/Card.tsx";
import { AlertTriangle } from "./icons.tsx";

// Stop fast-polling if a regeneration never shows up (e.g. the model errored).
const MAX_WAIT_MS = 5 * 60 * 1000;

function Muted({ children }: { children: ReactNode }) {
  return <p className="text-sm text-stone-500 dark:text-stone-400">{children}</p>;
}

/** The local model's brief for a day, plus any anomaly note and this week's review. */
export default function BriefCard({ date }: { date: string }) {
  const status = useAIStatus().data;
  const [pending, setPending] = useState<{ from: string; at: number } | null>(null);
  const generate = useGenerateInsight();

  const insights = useInsights(date, pending !== null);
  const data = insights.data;
  const brief = data?.daily_brief ?? null;
  const waiting =
    pending !== null &&
    (brief?.created_at ?? "") === pending.from &&
    Date.now() - pending.at < MAX_WAIT_MS;
  const writing = waiting || Boolean(data?.busy);

  const ready = status?.enabled && status.reachable && status.model_present;

  function regenerate() {
    setPending({ from: brief?.created_at ?? "", at: Date.now() });
    generate.mutate({ kind: "daily_brief", date });
  }

  return (
    <section className="rounded-lg border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-stone-900">
      <header className="mb-3 flex items-start justify-between gap-4">
        <h2 className="text-sm font-semibold">Coach's brief</h2>
        {ready && (
          <button type="button" className={BUTTON_SECONDARY} disabled={writing} onClick={regenerate}>
            {writing ? "Writing…" : brief ? "Regenerate" : "Write it now"}
          </button>
        )}
      </header>

      {status && !status.enabled && <Muted>The AI coach is off (AI_ENABLED=false in .env).</Muted>}
      {status?.enabled && !ready && <Muted>AI coach unavailable: {status.detail ?? "Ollama is not ready."}</Muted>}
      {generate.error && <p className="text-sm text-red-600">{generate.error.message}</p>}

      {writing && !brief && <Muted>Writing your brief on this computer. This can take a minute…</Muted>}
      {!writing && !brief && ready && (
        <Muted>Your brief appears automatically once last night's sleep has synced.</Muted>
      )}

      {brief && (
        <div className={writing ? "opacity-60" : undefined}>
          <p className="font-medium">{brief.content.headline}</p>
          <p className="mt-2 text-sm leading-relaxed text-stone-700 dark:text-stone-300">{brief.content.summary}</p>
          <ul className="mt-3 space-y-2">
            {brief.content.tips.map((tip) => (
              <li key={tip.title} className="text-sm">
                <span className="font-medium">{tip.title}.</span>{" "}
                <span className="text-stone-700 dark:text-stone-300">{tip.detail}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-stone-500">
            Written by {brief.model} on your computer · {formatDateTime(brief.created_at)} · not medical advice
          </p>
        </div>
      )}

      {data?.anomaly && (
        <div className="mt-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
          <p className="flex items-center gap-2 font-medium">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {data.anomaly.content.headline}
          </p>
          <p className="mt-1">{data.anomaly.content.explanation}</p>
          <ul className="mt-2 list-disc pl-5">
            {data.anomaly.content.suggestions.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <p className="mt-2 text-xs">See a doctor if: {data.anomaly.content.see_doctor_if}</p>
        </div>
      )}

      {data?.weekly_review && (
        <details className="mt-4 text-sm">
          <summary className="cursor-pointer font-medium">
            Weekly review: {data.weekly_review.content.headline}
          </summary>
          <p className="mt-2 text-stone-700 dark:text-stone-300">{data.weekly_review.content.summary}</p>
          {data.weekly_review.content.wins.length > 0 && (
            <>
              <p className="mt-2 font-medium">Went well</p>
              <ul className="list-disc pl-5">
                {data.weekly_review.content.wins.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </>
          )}
          {data.weekly_review.content.watch.length > 0 && (
            <>
              <p className="mt-2 font-medium">Keep an eye on</p>
              <ul className="list-disc pl-5">
                {data.weekly_review.content.watch.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </>
          )}
          <p className="mt-2">
            <span className="font-medium">Focus next week:</span> {data.weekly_review.content.focus}
          </p>
        </details>
      )}
    </section>
  );
}
