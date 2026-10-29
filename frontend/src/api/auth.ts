import { apiGet, apiPost } from "./client.ts";
import type { AuthStatus } from "./types.ts";

// Full-page navigation: the backend redirects to Google's consent screen.
export const LOGIN_URL = "/api/auth/login";

export function fetchAuthStatus(signal?: AbortSignal): Promise<AuthStatus> {
  return apiGet<AuthStatus>("/auth/status", signal);
}

export function logout(): Promise<void> {
  return apiPost<void>("/auth/logout");
}
