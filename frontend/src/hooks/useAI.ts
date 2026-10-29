import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchAIStatus, fetchInsights, generateInsight } from "../api/ai.ts";
import type { InsightKind } from "../api/types.ts";

export function useAIStatus() {
  return useQuery({ queryKey: ["ai-status"], queryFn: ({ signal }) => fetchAIStatus(signal), refetchInterval: 30_000 });
}

/** `waiting`: the user just asked for a regeneration, so poll quickly until it lands. */
export function useInsights(date: string | undefined, waiting = false) {
  return useQuery({
    queryKey: ["insights", date ?? "latest"],
    queryFn: ({ signal }) => fetchInsights(date, signal),
    refetchInterval: (query) => (waiting || query.state.data?.busy ? 4_000 : 60_000),
  });
}

export function useGenerateInsight() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ kind, date }: { kind: InsightKind; date: string | undefined }) => generateInsight(kind, date),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["insights"] }),
  });
}
