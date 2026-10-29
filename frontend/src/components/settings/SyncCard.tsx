import { useState } from "react";
import { formatDate, formatDateTime, todayIso } from "../../format.ts";
import { useAuthStatus } from "../../hooks/useAuthStatus.ts";
import { useStartSync, useSyncStatus } from "../../hooks/useSync.ts";
import { BUTTON, BUTTON_SECONDARY, Card, INPUT, StatusDot } from "./Card.tsx";

export default function SyncCard() {
  const auth = useAuthStatus();
  const { data } = useSyncStatus();
  const start = useStartSync();
  const [since, setSince] = useState("");

  const connected = Boolean(auth.data?.connected && !auth.data.needs_reauth);
  const busy = Boolean(data?.running) || start.isPending;

  return (
    <Card title="Sync">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className={BUTTON}
          disabled={!connected || busy}
          onClick={() => start.mutate({})}
        >
          {data?.running ? "Syncing…" : "Sync now"}
        </button>
        <span className="mx-1 text-sm text-slate-400">or backfill from</span>
        <input
          type="date"
          className={INPUT}
          max={todayIso()}
          value={since}
          onChange={(e) => setSince(e.target.value)}
          aria-label="Backfill start date"
        />
        <button
          type="button"
          className={BUTTON_SECONDARY}
          disabled={!connected || busy || !since}
          onClick={() => start.mutate({ since })}
        >
          Backfill
        </button>
      </div>

      {start.error && <p className="mt-2 text-sm text-red-600">{start.error.message}</p>}
      {data?.last_error && <p className="mt-2 text-sm text-red-600">{data.last_error}</p>}
      {data?.last_run && (
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
          Last run {formatDateTime(data.last_run.finished_at ?? data.last_run.started_at)}:{" "}
          {data.last_run.ok.length} types ok
          {Object.keys(data.last_run.failed).length > 0 &&
            `, ${Object.keys(data.last_run.failed).length} failed`}
          , {Object.values(data.last_run.points).reduce((a, b) => a + b, 0).toLocaleString()} points.
        </p>
      )}

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[36rem] text-left text-sm">
          <thead className="text-xs uppercase text-slate-500">
            <tr>
              <th className="py-1 pr-3 font-medium">Data type</th>
              <th className="py-1 pr-3 font-medium">Synced from</th>
              <th className="py-1 pr-3 font-medium">Last success</th>
              <th className="py-1 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
            {data?.types.map((t) => (
              <tr key={t.key}>
                <td className="py-1.5 pr-3 font-mono text-xs">{t.key}</td>
                <td className="py-1.5 pr-3">{formatDate(t.synced_from)}</td>
                <td className="py-1.5 pr-3">{formatDateTime(t.last_success_at)}</td>
                <td className="py-1.5">
                  <span className="flex items-center gap-2" title={t.last_error ?? undefined}>
                    <StatusDot tone={t.last_error ? "error" : t.last_success_at ? "ok" : "warn"} />
                    <span className="truncate">
                      {t.last_error ? "Error" : t.last_success_at ? "OK" : "Never synced"}
                    </span>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
