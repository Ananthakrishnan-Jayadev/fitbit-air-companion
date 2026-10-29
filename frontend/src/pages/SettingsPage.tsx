import { useHealth } from "../hooks/useHealth.ts";

type Tone = "ok" | "warn" | "error";

const DOT: Record<Tone, string> = {
  ok: "bg-emerald-500",
  warn: "bg-amber-500",
  error: "bg-red-500",
};

function StatusRow({ label, tone, detail }: { label: string; tone: Tone; detail: string }) {
  return (
    <li className="flex items-start gap-3 py-3">
      <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${DOT[tone]}`} aria-hidden />
      <div>
        <div className="font-medium">{label}</div>
        <div className="text-sm text-slate-600 dark:text-slate-400">{detail}</div>
      </div>
    </li>
  );
}

export default function SettingsPage() {
  const { data, isLoading } = useHealth();

  return (
    <section>
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
      <p className="mt-1 text-slate-600 dark:text-slate-400">
        System status. Google connection, sync and profile arrive in Phase 2.
      </p>

      <div className="mt-6 max-w-xl rounded-lg border border-slate-200 bg-white px-4 dark:border-slate-800 dark:bg-slate-900">
        {isLoading || !data ? (
          <p className="py-4 text-sm text-slate-500">Loading status…</p>
        ) : (
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            <StatusRow
              label="Database"
              tone={data.database.ok ? "ok" : "error"}
              detail={data.database.ok ? "Ready" : (data.database.detail ?? "Unavailable")}
            />
            <StatusRow
              label="Local AI (Ollama)"
              tone={!data.ollama ? "warn" : data.ollama.reachable && data.ollama.model_present ? "ok" : "warn"}
              detail={
                !data.ollama
                  ? "Disabled (AI_ENABLED=false)"
                  : (data.ollama.detail ?? `Model ${data.ollama.model} ready`)
              }
            />
            <StatusRow
              label="Google Health API"
              tone={data.google.configured ? "ok" : "warn"}
              detail={
                data.google.configured
                  ? "OAuth client configured (connect in Phase 2)"
                  : "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env"
              }
            />
            <StatusRow label="App version" tone="ok" detail={data.version} />
          </ul>
        )}
      </div>
    </section>
  );
}
