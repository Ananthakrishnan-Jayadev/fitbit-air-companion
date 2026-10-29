import { apiGet, apiPut } from "./client.ts";
import type { Profile } from "./types.ts";

export function fetchProfile(signal?: AbortSignal): Promise<Profile> {
  return apiGet<Profile>("/profile", signal);
}

export function saveProfile(profile: Profile): Promise<Profile> {
  return apiPut<Profile>("/profile", profile);
}
