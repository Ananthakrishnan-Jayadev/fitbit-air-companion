import { useHealth } from "../../hooks/useHealth.ts";
import { Card, StatusDot, type Tone } from "./Card.tsx";

function Row({ label, tone, detail }: { label: string; tone: Tone; detail: string }) {
  return (
    <li className="flex items-start gap-3 py-2">
      <span className="mt-1.5">
        <StatusDot tone={tone} />
      </span>
      <div>
        <div className="text-sm font-medium">{label}</div>
        <div className="text-sm text-slate-600 dark:text-slate-400">{detail}</div>
      </div>
    </li>
  );
}

export default function SystemStatusCard() {
  const { data } = useHealth();

  return (
    <Card title="System">
      {!data ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : (
        <ul className="divide-y divide-slate-200 dark:divide-slate-800">
          <Row
            label="Database"
            tone={data.database.ok ? "ok" : "error"}
            detail={data.database.ok ? "Ready" : (data.database.detail ?? "Unavailable")}
          />
          <Row
            label="Local AI (Ollama)"
            tone={data.ollama?.reachable && data.ollama.model_present ? "ok" : "warn"}
            detail={
              !data.ollama
                ? "Disabled (AI_ENABLED=false)"
                : (data.ollama.detail ?? `Model ${data.ollama.model} ready`)
            }
          />
          <Row label="App version" tone="ok" detail={data.version} />
        </ul>
      )}
    </Card>
  );
}
