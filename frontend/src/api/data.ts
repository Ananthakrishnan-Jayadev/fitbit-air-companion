import { apiGet } from "./client.ts";
import type {
  ActivityResponse,
  HeartResponse,
  NightSummary,
  SleepResponse,
  TodayResponse,
  TrendResponse,
  Workout,
} from "./types.ts";

function dateQuery(date: string | undefined): string {
  return date ? `?date=${encodeURIComponent(date)}` : "";
}

export function fetchToday(date: string | undefined, signal?: AbortSignal): Promise<TodayResponse> {
  return apiGet<TodayResponse>(`/today${dateQuery(date)}`, signal);
}

export function fetchTrend(
  metric: string,
  days: number,
  end: string | undefined,
  signal?: AbortSignal,
): Promise<TrendResponse> {
  const endPart = end ? `&end=${encodeURIComponent(end)}` : "";
  return apiGet<TrendResponse>(`/trends?metric=${metric}&days=${days}${endPart}`, signal);
}

export function fetchHeart(date: string | undefined, signal?: AbortSignal): Promise<HeartResponse> {
  return apiGet<HeartResponse>(`/heart${dateQuery(date)}`, signal);
}

export function fetchSleep(date: string | undefined, signal?: AbortSignal): Promise<SleepResponse> {
  return apiGet<SleepResponse>(`/sleep${dateQuery(date)}`, signal);
}

export function fetchSleepRange(start: string, end: string, signal?: AbortSignal): Promise<NightSummary[]> {
  return apiGet<NightSummary[]>(`/sleep/range?start=${start}&end=${end}`, signal);
}

export function fetchActivity(date: string | undefined, signal?: AbortSignal): Promise<ActivityResponse> {
  return apiGet<ActivityResponse>(`/activity${dateQuery(date)}`, signal);
}

export function fetchExercise(start: string, end: string, signal?: AbortSignal): Promise<Workout[]> {
  return apiGet<Workout[]>(`/exercise?start=${start}&end=${end}`, signal);
}
