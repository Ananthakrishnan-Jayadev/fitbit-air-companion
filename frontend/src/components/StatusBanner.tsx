import type { ReactNode } from "react";
import { useHealth } from "../hooks/useHealth.ts";

function Banner({ tone, children }: { tone: "error" | "warn"; children: ReactNode }) {
  const colors =
    tone === "error"
      ? "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200"
      : "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200";
  return <div className={`mb-4 rounded-md border px-4 py-2 text-sm ${colors}`}>{children}</div>;
}

export default function StatusBanner() {
  const { data, isError } = useHealth();

  if (isError) {
    return <Banner tone="error">Cannot reach the app server. Is `fitbit serve` running?</Banner>;
  }
  if (!data) return null;

  const messages: { tone: "error" | "warn"; text: string }[] = [];
  if (!data.database.ok) {
    messages.push({ tone: "error", text: data.database.detail ?? "Database unavailable." });
  }
  if (data.ollama && !(data.ollama.reachable && data.ollama.model_present)) {
    messages.push({
      tone: "warn",
      text: `AI features unavailable: ${data.ollama.detail ?? "Ollama not ready."}`,
    });
  }

  return (
    <>
      {messages.map((m) => (
        <Banner key={m.text} tone={m.tone}>
          {m.text}
        </Banner>
      ))}
    </>
  );
}
