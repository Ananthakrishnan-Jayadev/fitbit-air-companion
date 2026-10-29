// Small pure display helpers.

export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Last path segment of an OAuth scope URL, e.g. "sleep.readonly". */
export function shortScope(scope: string): string {
  return scope.split("googlehealth.").pop() ?? scope;
}
