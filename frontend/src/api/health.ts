import { apiGet } from "./client.ts";
import type { HealthResponse } from "./types.ts";

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiGet<HealthResponse>("/health", signal);
}
