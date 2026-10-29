import { useSearchParams } from "react-router-dom";
import DataCard from "../components/settings/DataCard.tsx";
import GoogleConnectionCard from "../components/settings/GoogleConnectionCard.tsx";
import ProfileCard from "../components/settings/ProfileCard.tsx";
import SyncCard from "../components/settings/SyncCard.tsx";
import SystemStatusCard from "../components/settings/SystemStatusCard.tsx";

const AUTH_ERRORS: Record<string, string> = {
  access_denied: "Google sign-in was cancelled.",
  invalid_state: "The sign-in link expired or was already used. Try connecting again.",
  account_not_linked:
    "This Google account has no Google Health profile yet. Sign in to the Google Health app on your phone first, then connect again.",
  exchange_failed: "Google sign-in failed while exchanging the code. Check the client ID, secret and redirect URI.",
  api_error: "Connected to Google, but the Google Health API returned an error. Check the server log.",
  secret_key: "FITBIT_SECRET_KEY is missing or invalid, so tokens cannot be stored.",
};

export default function SettingsPage() {
  const [params, setParams] = useSearchParams();
  const authError = params.get("auth_error");
  const connected = params.get("connected") === "1";

  return (
    <section className="max-w-4xl">
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>

      {(authError || connected) && (
        <div
          className={`mt-4 flex items-start justify-between gap-4 rounded-md border px-4 py-2 text-sm ${
            authError
              ? "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200"
              : "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200"
          }`}
        >
          <span>
            {authError
              ? (AUTH_ERRORS[authError] ?? `Google sign-in failed (${authError}).`)
              : "Google connected. The first sync (back to BACKFILL_DAYS) has started and may take several minutes."}
          </span>
          <button type="button" className="underline" onClick={() => setParams({})}>
            Dismiss
          </button>
        </div>
      )}

      <div className="mt-6 grid gap-4">
        <GoogleConnectionCard />
        <SyncCard />
        <ProfileCard />
        <DataCard />
        <SystemStatusCard />
      </div>
    </section>
  );
}
