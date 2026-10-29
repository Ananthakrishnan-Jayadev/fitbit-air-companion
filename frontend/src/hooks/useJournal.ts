import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchCorrelations, fetchJournal, fetchTags, saveJournal } from "../api/journal.ts";
import type { Outcome } from "../api/types.ts";

export function useJournal(start: string, end: string) {
  return useQuery({
    queryKey: ["journal", start, end],
    queryFn: ({ signal }) => fetchJournal(start, end, signal),
  });
}

export function useTags() {
  return useQuery({ queryKey: ["journal-tags"], queryFn: ({ signal }) => fetchTags(signal) });
}

export function useSaveJournal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ date, tags, note }: { date: string; tags: string[]; note: string | null }) =>
      saveJournal(date, tags, note),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["journal"] });
      void queryClient.invalidateQueries({ queryKey: ["journal-tags"] });
      void queryClient.invalidateQueries({ queryKey: ["correlations"] });
    },
  });
}

export function useCorrelations(outcome: Outcome, days: number) {
  return useQuery({
    queryKey: ["correlations", outcome, days],
    queryFn: ({ signal }) => fetchCorrelations(outcome, days, signal),
  });
}
