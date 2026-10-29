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
