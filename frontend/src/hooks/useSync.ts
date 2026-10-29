import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchSyncStatus, startSync } from "../api/sync.ts";
import type { SyncRequest } from "../api/types.ts";

export function useSyncStatus() {
  return useQuery({
    queryKey: ["sync"],
    queryFn: ({ signal }) => fetchSyncStatus(signal),
    // Poll quickly while a sync runs, slowly otherwise.
    refetchInterval: (query) => (query.state.data?.running ? 3_000 : 30_000),
  });
}

export function useStartSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SyncRequest) => startSync(body),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["sync"] }),
  });
}
