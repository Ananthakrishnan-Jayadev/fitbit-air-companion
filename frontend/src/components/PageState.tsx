import { Link } from "react-router-dom";
import { ApiError } from "../api/client.ts";

export function Loading() {
  return <p className="py-8 text-sm text-stone-500">Loading…</p>;
}

/** Error or "no data yet" (404) state for a page. */
export function LoadError({ error }: { error: Error }) {
  if (error instanceof ApiError && error.status === 404) {
    return (
      <div className="rounded-lg border border-dashed border-stone-300 p-8 text-center text-sm text-stone-600 dark:border-stone-700 dark:text-stone-400">
        No scored data yet.{" "}
        <Link to="/settings" className="underline">
          Connect Google in Settings
        </Link>{" "}
        and let the first sync finish, or run <code>fitbit analyze</code>.
      </div>
    );
  }
  return <p className="py-8 text-sm text-red-600">{error.message}</p>;
}
