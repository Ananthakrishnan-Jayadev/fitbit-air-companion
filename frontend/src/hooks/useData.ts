import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  fetchActivity,
  fetchBody,
  fetchDaily,
  fetchHeart,
  fetchSleep,
  fetchSleepRange,
  fetchToday,
  fetchTrend,
} from "../api/data.ts";

// keepPreviousData: when switching days, keep showing the last day instead of flashing empty.

export function useToday(date: string | undefined) {
  return useQuery({
    queryKey: ["today", date ?? "latest"],
    queryFn: ({ signal }) => fetchToday(date, signal),
    placeholderData: keepPreviousData,
    retry: false,
  });
}

export function useTrend(metric: string, days: number, end?: string) {
  return useQuery({
    queryKey: ["trend", metric, days, end ?? "latest"],
    queryFn: ({ signal }) => fetchTrend(metric, days, end, signal),
    placeholderData: keepPreviousData,
  });
}

export function useHeart(date: string | undefined) {
  return useQuery({
    queryKey: ["heart", date ?? "latest"],
    queryFn: ({ signal }) => fetchHeart(date, signal),
    placeholderData: keepPreviousData,
    retry: false,
  });
}

export function useSleep(date: string | undefined) {
  return useQuery({
    queryKey: ["sleep", date ?? "latest"],
    queryFn: ({ signal }) => fetchSleep(date, signal),
    placeholderData: keepPreviousData,
    retry: false,
  });
}

export function useSleepRange(start: string | undefined, end: string | undefined) {
  return useQuery({
    queryKey: ["sleep-range", start, end],
    queryFn: ({ signal }) => fetchSleepRange(start ?? "", end ?? "", signal),
    enabled: Boolean(start && end),
  });
}

export function useActivity(date: string | undefined) {
  return useQuery({
    queryKey: ["activity", date ?? "latest"],
    queryFn: ({ signal }) => fetchActivity(date, signal),
    placeholderData: keepPreviousData,
    retry: false,
  });
}

export function useDaily(start: string, end: string) {
  return useQuery({
    queryKey: ["daily", start, end],
    queryFn: ({ signal }) => fetchDaily(start, end, signal),
    placeholderData: keepPreviousData,
  });
}

export function useBody(days: number) {
  return useQuery({
    queryKey: ["body", days],
    queryFn: ({ signal }) => fetchBody(days, signal),
    placeholderData: keepPreviousData,
  });
}
