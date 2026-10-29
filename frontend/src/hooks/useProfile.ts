import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchProfile, saveProfile } from "../api/profile.ts";

export function useProfile() {
  return useQuery({ queryKey: ["profile"], queryFn: ({ signal }) => fetchProfile(signal) });
}

export function useSaveProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: saveProfile,
    onSuccess: (profile) => queryClient.setQueryData(["profile"], profile),
  });
}
