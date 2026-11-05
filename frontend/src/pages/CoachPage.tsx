import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchChatHistory, streamChat } from "../api/ai.ts";
import type { ChatMessage } from "../api/types.ts";
import { followUpsFor } from "../coach.ts";
import { Page, Panel, WithAside } from "../components/PageLayout.tsx";
import { BUTTON, BUTTON_SECONDARY } from "../components/settings/Card.tsx";
import { useAIStatus } from "../hooks/useAI.ts";
import { useToday } from "../hooks/useData.ts";
import { formatNumber } from "../format.ts";
import { recoveryBand } from "../metrics.ts";
import { BASE } from "../motion.ts";

const STORAGE_KEY = "coach.conversationId";
const SUGGESTIONS = [
  "How did I sleep last night compared with usual?",
  "Should I train hard today?",
  "Why is my recovery what it is today?",
  "How has my resting heart rate trended this week?",
];

/** Today's three numbers as small sleeves, so the conversation has its context in view. */
function TodayAtAGlance() {
  const today = useToday(undefined).data;
  if (!today) return null;
  const band = today.recovery === null ? null : recoveryBand(today.recovery);
  const cells: { label: string; value: string; detail: string; bg: string; fg: string }[] = [
    {
      label: "Recovery",
      value: formatNumber(today.recovery),
      detail: band?.label ?? "learning",
      bg: band ? `var(--${band.tone})` : "var(--grid)",
      fg: band ? `var(--on-${band.tone})` : "var(--ink-1)",
    },
    { label: "Sleep", value: formatNumber(today.sleep_perf), detail: "/100", bg: "var(--sleep)", fg: "var(--on-sleep)" },
    { label: "Strain", value: formatNumber(today.strain, 1), detail: "/21", bg: "var(--strain)", fg: "var(--on-strain)" },
  ];
  return (
    <Panel title={`Latest day · ${today.date}`}>
      <ul className="grid grid-cols-3 gap-2">
        {cells.map((c) => (
          <li
            key={c.label}
            className="flex aspect-square flex-col p-2 text-xs font-semibold"
            style={{ backgroundColor: c.bg, color: c.fg }}
          >
            {c.label}
            <span className="font-normal">{c.detail}</span>
            <span className="mt-auto self-end font-condensed text-4xl font-extrabold leading-[0.8]">{c.value}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function loadConversationId(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function saveConversationId(id: string | null) {
  try {
    if (id) localStorage.setItem(STORAGE_KEY, id);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage unavailable (private window): the chat still works, it just isn't remembered.
  }
}

export default function CoachPage() {
  const status = useAIStatus().data;
  const [conversationId, setConversationId] = useState<string | null>(loadConversationId);
  const [messages, setMessages] = useState<ChatMessage[] | null>(null);
  const [params, setParams] = useSearchParams();
  // "Ask about this" links arrive with ?q=: prefill it, but let the user decide to send.
  const [input, setInput] = useState(() => params.get("q") ?? "");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Screen readers hear each finished reply once, not every streamed chunk.
  const [announcement, setAnnouncement] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!params.has("q")) return;
    textarea.current?.focus();
    setParams({}, { replace: true });
  }, [params, setParams]);

  const history = useQuery({
    queryKey: ["chat-history", conversationId],
    queryFn: ({ signal }) => fetchChatHistory(conversationId ?? "", signal),
    enabled: conversationId !== null && messages === null,
  });
  // Until the user sends something, show the stored conversation.
  const shown = messages ?? history.data ?? [];
  const lastContent = shown[shown.length - 1]?.content;

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [shown.length, lastContent]);

  const ready = status?.enabled && status.reachable && status.model_present;
  const last = shown[shown.length - 1];
  const lastQuestion = [...shown].reverse().find((m) => m.role === "user")?.content;
  const followUps =
    !sending && last?.role === "assistant" && last.content && lastQuestion
      ? followUpsFor(lastQuestion)
      : [];

  async function send(text: string) {
    const message = text.trim();
    if (!message || sending) return;
    setError(null);
    setInput("");
    setSending(true);
    const base = [...shown, { role: "user" as const, content: message }];
    setMessages([...base, { role: "assistant", content: "" }]);
    let reply = "";
    try {
      await streamChat(message, conversationId, {
        onConversation: (id) => {
          setConversationId(id);
          saveConversationId(id);
        },
        onDelta: (delta) => {
          reply += delta;
          setMessages((current) => {
            if (!current) return current;
            const last = current[current.length - 1];
            if (!last || last.role !== "assistant") return current;
            return [...current.slice(0, -1), { ...last, content: last.content + delta }];
          });
        },
      });
      setAnnouncement(`Coach replied: ${reply}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed");
      setMessages((current) => (current ?? []).filter((m) => m.content !== ""));
    } finally {
      setSending(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(input);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(input);
    }
  }

  function newChat() {
    setConversationId(null);
    saveConversationId(null);
    setMessages([]);
    setError(null);
  }

  const aside = (
    <>
      <TodayAtAGlance />
      <Panel title="Ask about">
        <ul className="grid gap-2">
          {SUGGESTIONS.map((q) => (
            <li key={q}>
              <button
                type="button"
                className={`${BUTTON_SECONDARY} w-full !justify-start text-left`}
                disabled={!ready || sending}
                onClick={() => void send(q)}
              >
                {q}
              </button>
            </li>
          ))}
        </ul>
      </Panel>
      <Panel title="What the coach sees">
        <p className="text-sm leading-relaxed text-stone-700 dark:text-stone-300">
          Runs on your own computer{status ? ` with ${status.model}` : ""}. It reads your scores, daily
          summaries and journal tags, never raw heart-rate or sleep data, and nothing leaves your
          machines. Informational only, not medical advice.
        </p>
      </Panel>
    </>
  );

  return (
    <Page>
      <div className="mb-5 flex items-center justify-between gap-4">
        <h1 className="page-title !mb-0">Coach</h1>
        <button type="button" className={BUTTON_SECONDARY} onClick={newChat} disabled={sending}>
          New chat
        </button>
      </div>

      <WithAside label="Coach context" aside={aside}>
        {status && !ready && (
          <p className="mb-4 border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
            {status.enabled ? (status.detail ?? "Ollama is not ready.") : "The AI coach is off (AI_ENABLED=false)."}
          </p>
        )}

        <div className="min-h-[24rem] space-y-3 border border-stone-200 bg-white p-4 xl:min-h-[calc(100svh-20rem)] dark:border-stone-800 dark:bg-stone-900">
          {shown.length === 0 && (
            <p className="max-w-prose text-sm text-stone-600 dark:text-stone-400">
              Ask about your sleep, recovery or training, or pick a question from “Ask about”.
            </p>
          )}
          <AnimatePresence initial={false}>
            {shown.map((m, i) => (
              <motion.div
                key={i}
                className={m.role === "user" ? "flex justify-end" : "flex justify-start"}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={BASE}
              >
                <div
                  className={`max-w-[min(85%,68ch)] whitespace-pre-wrap px-3.5 py-2.5 text-[15px] leading-relaxed ${
                    m.role === "user"
                      ? "bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900"
                      : "bg-stone-100 text-stone-900 dark:bg-stone-800 dark:text-stone-100"
                  }`}
                >
                  {m.content || (sending && i === shown.length - 1 ? "Thinking…" : "")}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
          {followUps.length > 0 && (
            <motion.div
              className="flex flex-wrap gap-2 pt-1"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={BASE}
            >
              {followUps.map((q) => (
                <button key={q} type="button" className={BUTTON_SECONDARY} disabled={!ready} onClick={() => void send(q)}>
                  {q}
                </button>
              ))}
            </motion.div>
          )}
          <div ref={bottom} />
        </div>
        <div className="sr-only" aria-live="polite">
          {announcement}
        </div>

        {error && <p className="mt-2 text-sm text-red-700 dark:text-red-300">{error}</p>}

        <form onSubmit={onSubmit} className="mt-3 flex items-end gap-2">
          <textarea
            ref={textarea}
            className="min-h-[2.75rem] flex-1 resize-y border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-950"
            rows={2}
            maxLength={2000}
            placeholder={ready ? "Ask about your sleep, recovery, training…" : "Coach unavailable"}
            value={input}
            disabled={!ready}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            aria-label="Message"
          />
          <button type="submit" className={BUTTON} disabled={!ready || sending || !input.trim()}>
            {sending ? "…" : "Send"}
          </button>
        </form>
      </WithAside>
    </Page>
  );
}
