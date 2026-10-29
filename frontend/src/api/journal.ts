import { apiDelete, apiGet, apiPut } from "./client.ts";
import type { CorrelationsResponse, JournalEntry, Outcome, TagInfo } from "./types.ts";

export function fetchJournal(start: string, end: string, signal?: AbortSignal): Promise<JournalEntry[]> {
  return apiGet<JournalEntry[]>(`/journal?start=${start}&end=${end}`, signal);
}

export function fetchTags(signal?: AbortSignal): Promise<TagInfo[]> {
  return apiGet<TagInfo[]>("/journal/tags", signal);
}

export function saveJournal(date: string, tags: string[], note: string | null): Promise<JournalEntry> {
  return apiPut<JournalEntry>(`/journal/${date}`, { tags, note });
}

export function deleteJournal(date: string): Promise<void> {
  return apiDelete(`/journal/${date}`);
}

export function fetchCorrelations(outcome: Outcome, days: number, signal?: AbortSignal): Promise<CorrelationsResponse> {
  return apiGet<CorrelationsResponse>(`/correlations?outcome=${outcome}&days=${days}`, signal);
}
