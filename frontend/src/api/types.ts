// Mirrors the pydantic response models in src/fitbit_app/api/.

export interface ComponentStatus {
  ok: boolean;
  detail: string | null;
}

export interface OllamaStatus {
  reachable: boolean;
  model: string;
  model_present: boolean;
  detail: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  database: ComponentStatus;
  ai_enabled: boolean;
  ollama: OllamaStatus | null;
  google: { configured: boolean };
}

export interface AuthStatus {
  configured: boolean;
  secret_key_configured: boolean;
  connected: boolean;
  needs_reauth: boolean;
  health_user_id: string | null;
  missing_scopes: string[];
  expires_at: string | null;
}

export interface TypeStatus {
  key: string;
  kind: "sample" | "interval" | "session" | "daily" | "rollup";
  cursor: string | null;
  synced_from: string | null;
  last_success_at: string | null;
  last_error: string | null;
  last_error_at: string | null;
}

export interface LastRun {
  started_at: string;
  finished_at: string | null;
  ok: string[];
  failed: Record<string, string>;
  points: Record<string, number>;
}

export interface SyncStatus {
  running: boolean;
  last_run: LastRun | null;
  last_error: string | null;
  types: TypeStatus[];
}

export interface SyncRequest {
  types?: string[];
  since?: string; // YYYY-MM-DD
}

export interface Profile {
  age: number | null;
  max_hr: number | null;
  sleep_need_min: number | null;
}
