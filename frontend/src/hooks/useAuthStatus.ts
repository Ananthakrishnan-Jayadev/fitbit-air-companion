import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchAuthStatus, logout } from "../api/auth.ts";

export function useAuthStatus() {
  return useQuery({ queryKey: ["auth"], queryFn: ({ signal }) => fetchAuthStatus(signal) });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logout,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["auth"] }),
  });
}
