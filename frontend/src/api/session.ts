import { apiGet, apiPost } from "./client.ts";
import type { SessionStatus } from "./types.ts";

// Login to this app (APP_PASSWORD). Google sign-in lives in auth.ts.

export function fetchSession(signal?: AbortSignal): Promise<SessionStatus> {
  return apiGet<SessionStatus>("/session", signal);
}

export async function login(password: string): Promise<void> {
  await apiPost<unknown>("/session/login", { password });
}

export async function signOut(): Promise<void> {
  await apiPost<unknown>("/session/logout");
}
