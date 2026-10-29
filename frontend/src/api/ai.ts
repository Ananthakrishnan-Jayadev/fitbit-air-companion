import { ApiError, apiGet, apiPost, apiPostStream } from "./client.ts";
import type { AIStatus, ChatMessage, InsightKind, InsightsResponse } from "./types.ts";

export function fetchAIStatus(signal?: AbortSignal): Promise<AIStatus> {
  return apiGet<AIStatus>("/ai/status", signal);
}

export function fetchInsights(date: string | undefined, signal?: AbortSignal): Promise<InsightsResponse> {
  return apiGet<InsightsResponse>(`/ai/insights${date ? `?date=${date}` : ""}`, signal);
}

export function generateInsight(kind: InsightKind, date: string | undefined): Promise<{ started: boolean }> {
  return apiPost<{ started: boolean }>("/ai/generate", { kind, date });
}

export function fetchChatHistory(conversationId: string, signal?: AbortSignal): Promise<ChatMessage[]> {
  return apiGet<ChatMessage[]>(`/ai/chat/${encodeURIComponent(conversationId)}`, signal);
}

interface ChatHandlers {
  onConversation: (id: string) => void;
  onDelta: (text: string) => void;
}

/** POST a chat message and read the server-sent event stream until done. */
export async function streamChat(
  message: string,
  conversationId: string | null,
  handlers: ChatHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await apiPostStream("/ai/chat", { message, conversation_id: conversationId }, signal);
  if (!response.body) throw new ApiError(500, "Empty chat response");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const event = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
      if (!event.startsWith("data: ")) continue;
      const payload = JSON.parse(event.slice(6)) as {
        conversation_id?: string;
        delta?: string;
        done?: boolean;
        error?: string;
      };
      if (payload.conversation_id) handlers.onConversation(payload.conversation_id);
      if (payload.delta) handlers.onDelta(payload.delta);
      if (payload.error) throw new ApiError(503, payload.error);
      if (payload.done) return;
    }
  }
}
