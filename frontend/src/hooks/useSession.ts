import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchSession, login, signOut } from "../api/session.ts";

export const SESSION_KEY = ["session"] as const;

export function useSession() {
  return useQuery({
    queryKey: SESSION_KEY,
    queryFn: ({ signal }) => fetchSession(signal),
    retry: false,
    staleTime: 5 * 60_000,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: login,
    // Refetch everything, including queries that failed with 401 before login.
    onSuccess: () => queryClient.invalidateQueries(),
  });
}

export function useSignOut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: signOut,
    // Drop cached health data from memory, then refetch the session (shows the login form).
    onSuccess: () => queryClient.resetQueries(),
  });
}
