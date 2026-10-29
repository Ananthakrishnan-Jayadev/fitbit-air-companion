import { apiGet, apiPost } from "./client.ts";
import type { SyncRequest, SyncStatus } from "./types.ts";

export function fetchSyncStatus(signal?: AbortSignal): Promise<SyncStatus> {
  return apiGet<SyncStatus>("/sync/status", signal);
}

export function startSync(body: SyncRequest = {}): Promise<{ started: boolean }> {
  return apiPost<{ started: boolean }>("/sync", body);
}
