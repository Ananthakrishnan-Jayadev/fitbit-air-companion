import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchChatHistory, streamChat } from "../api/ai.ts";
import type { ChatMessage } from "../api/types.ts";
import { followUpsFor } from "../coach.ts";
import { BUTTON, BUTTON_SECONDARY } from "../components/settings/Card.tsx";
import { useAIStatus } from "../hooks/useAI.ts";
import { BASE } from "../motion.ts";

const STORAGE_KEY = "coach.conversationId";
const SUGGESTIONS = [
  "How did I sleep last night compared with usual?",
  "Should I train hard today?",
  "Why is my recovery what it is today?",
  "How has my resting heart rate trended this week?",
];

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

  return (
    <section className="flex max-w-3xl flex-col">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h1 className="page-title !mb-0">Coach</h1>
        <button type="button" className={BUTTON_SECONDARY} onClick={newChat} disabled={sending}>
          New chat
        </button>
      </div>
      <p className="mb-4 text-sm text-stone-500">
        Runs on this computer{status ? ` with ${status.model}` : ""}. It sees your scores and daily
        summaries, not raw data. Not medical advice.
      </p>

      {status && !ready && (
        <p className="mb-4 rounded-md border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          {status.enabled ? (status.detail ?? "Ollama is not ready.") : "The AI coach is off (AI_ENABLED=false)."}
        </p>
      )}

      <div className="min-h-[16rem] space-y-3 rounded-lg border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
        {shown.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                className={BUTTON_SECONDARY}
                disabled={!ready || sending}
                onClick={() => void send(s)}
              >
                {s}
              </button>
            ))}
          </div>
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
                className={`max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${
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
              <button
                key={q}
                type="button"
                className={BUTTON_SECONDARY}
                disabled={!ready}
                onClick={() => void send(q)}
              >
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

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      <form onSubmit={onSubmit} className="mt-3 flex items-end gap-2">
        <textarea
          ref={textarea}
          className="min-h-[2.75rem] flex-1 resize-y rounded-md border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-950"
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
    </section>
  );
}
