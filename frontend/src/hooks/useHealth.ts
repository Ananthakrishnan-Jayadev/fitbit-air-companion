import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "../api/health.ts";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: 30_000,
  });
}
