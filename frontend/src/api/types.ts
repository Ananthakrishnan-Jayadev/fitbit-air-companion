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

// --- Phase 3: scores and details -------------------------------------------------------

/** [epoch milliseconds, value] */
export type Point = [number, number];

export interface BaselineBand {
  typical: number;
  low: number;
  high: number;
}

export interface TodayResponse {
  date: string;
  first_date: string | null;
  last_date: string | null;
  recovery: number | null;
  sleep_perf: number | null;
  strain: number | null;
  strain_target: [number, number] | null;
  stress_avg: number | null;
  illness_risk: number | null;
  flags: string[];
  acwr: number | null;
  components: {
    sleep?: { components?: Record<string, number | null>; asleep_min?: number } | null;
    recovery?: { components?: Record<string, number | null>; penalties?: Record<string, number> };
    strain?: { trimp?: number; max_hr?: number; max_hr_method?: string } | null;
  };
  z: Record<string, number | null>;
  metrics: Record<string, number | null>;
  baselines: Record<string, BaselineBand>;
}

export interface TrendResponse {
  metric: string;
  points: { date: string; value: number | null; baseline: BaselineBand | null }[];
}

export interface HeartResponse {
  date: string;
  utc_offset_min: number;
  samples: Point[];
  sample_count: number;
  resting_hr: number | null;
  hrv_rmssd_ms: number | null;
  min_bpm: number | null;
  max_bpm: number | null;
  zones: { zone: string; min_bpm: number | null; max_bpm: number | null }[];
}

export interface SleepStageOut {
  start: string;
  end: string;
  stage: string;
}

export interface SleepResponse {
  date: string;
  utc_offset_min: number;
  night: {
    start: string;
    end: string;
    duration_min: number;
    efficiency: number | null;
    is_main: boolean;
  } | null;
  stages: SleepStageOut[];
  stage_minutes: Record<string, number>;
  score: number | null;
  components: { components?: Record<string, number | null>; asleep_min?: number };
  spo2: Point[];
  hrv: Point[];
  skin_temp_delta_c: number | null;
  respiratory_rate: number | null;
  spo2_avg: number | null;
}

export interface NightSummary {
  date: string;
  start: string;
  end: string;
  bedtime_local: string;
  wake_local: string;
  duration_min: number;
  asleep_min: number | null;
  stage_minutes: Record<string, number>;
  score: number | null;
}

export interface Workout {
  date: string;
  start: string;
  end: string;
  activity_type: string;
  duration_min: number;
  calories: number | null;
  avg_hr: number | null;
  max_hr: number | null;
  distance_m: number | null;
  zones: Record<string, number | null> | null;
}

export interface ActivityResponse {
  date: string;
  utc_offset_min: number;
  hourly: { start: number; steps: number; calories: number }[];
  level_minutes: Record<string, number>;
  stress: Point[];
  stress_avg: number | null;
  totals: Record<string, number | null>;
  workouts: Workout[];
}

// --- Phase 4: AI coach -----------------------------------------------------------------

export interface AIStatus {
  enabled: boolean;
  reachable: boolean;
  model: string;
  model_present: boolean;
  busy: boolean;
  detail: string | null;
}

export interface DailyBriefContent {
  headline: string;
  summary: string;
  tips: { title: string; detail: string; category: string }[];
}

export interface WeeklyReviewContent {
  headline: string;
  summary: string;
  wins: string[];
  watch: string[];
  focus: string;
}

export interface AnomalyContent {
  headline: string;
  explanation: string;
  suggestions: string[];
  see_doctor_if: string;
}

export interface InsightOut<T> {
  kind: string;
  date: string;
  model: string;
  created_at: string;
  content: T;
}

export interface InsightsResponse {
  date: string | null;
  busy: boolean;
  daily_brief: InsightOut<DailyBriefContent> | null;
  anomaly: InsightOut<AnomalyContent> | null;
  weekly_review: InsightOut<WeeklyReviewContent> | null;
}

export type InsightKind = "daily_brief" | "weekly_review" | "anomaly";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  created_at?: string;
}

// --- Phase 5: journal, correlations ----------------------------------------------------

export interface JournalEntry {
  date: string;
  tags: string[];
  note: string | null;
}

export interface TagInfo {
  tag: string;
  count: number;
  preset: boolean;
}

export type Outcome = "recovery" | "sleep_perf" | "hrv_rmssd_ms" | "resting_hr" | "sleep_min";

export interface TagEffect {
  tag: string;
  n_with: number;
  n_without: number;
  mean_with: number;
  mean_without: number;
  difference: number;
  ci_low: number;
  ci_high: number;
  confident: boolean;
}

export interface CorrelationsResponse {
  outcome: Outcome;
  start: string;
  end: string;
  logged_days: number;
  effects: TagEffect[];
}

export interface DayRow {
  date: string;
  scores: Record<string, number | null>;
  metrics: Record<string, number | null>;
}

export interface BodyResponse {
  latest_date: string | null;
  weight_kg: number | null;
  body_fat_pct: number | null;
  fat_mass_kg: number | null;
  lean_mass_kg: number | null;
  weight_change_7d: number | null;
  weight_change_30d: number | null;
  body_fat_change_30d: number | null;
  points: { date: string; weight_kg: number | null; body_fat_pct: number | null }[];
}
