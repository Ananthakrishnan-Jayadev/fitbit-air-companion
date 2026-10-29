import { LOGIN_URL } from "../../api/auth.ts";
import { shortScope } from "../../format.ts";
import { useAuthStatus, useLogout } from "../../hooks/useAuthStatus.ts";
import { BUTTON, BUTTON_SECONDARY, Card, StatusDot } from "./Card.tsx";

function connect() {
  window.location.href = LOGIN_URL;
}

export default function GoogleConnectionCard() {
  const { data, isLoading } = useAuthStatus();
  const logout = useLogout();

  if (isLoading || !data) {
    return (
      <Card title="Google Health">
        <p className="text-sm text-slate-500">Loading…</p>
      </Card>
    );
  }

  if (!data.configured || !data.secret_key_configured) {
    return (
      <Card title="Google Health">
        <div className="flex items-start gap-3 text-sm">
          <span className="mt-1.5">
            <StatusDot tone="warn" />
          </span>
          <div>
            <p className="font-medium">Not configured</p>
            <p className="text-slate-600 dark:text-slate-400">
              Set{" "}
              {[
                !data.configured && "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET",
                !data.secret_key_configured && "FITBIT_SECRET_KEY",
              ]
                .filter(Boolean)
                .join(" and ")}{" "}
              in <code>.env</code>, then restart <code>fitbit serve</code>.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  if (!data.connected || data.needs_reauth) {
    return (
      <Card title="Google Health">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3 text-sm">
            <StatusDot tone={data.needs_reauth ? "error" : "warn"} />
            <span>
              {data.needs_reauth
                ? "Connection expired or was revoked (Testing-mode tokens last 7 days)."
                : "Not connected."}
            </span>
          </div>
          <button type="button" className={BUTTON} onClick={connect}>
            {data.needs_reauth ? "Reconnect Google" : "Connect Google"}
          </button>
        </div>
      </Card>
    );
  }

  return (
    <Card title="Google Health">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 text-sm">
          <StatusDot tone={data.missing_scopes.length ? "warn" : "ok"} />
          <span>Connected</span>
        </div>
        <button
          type="button"
          className={BUTTON_SECONDARY}
          disabled={logout.isPending}
          onClick={() => logout.mutate()}
        >
          Disconnect
        </button>
      </div>
      {data.missing_scopes.length > 0 && (
        <p className="mt-3 text-sm text-amber-700 dark:text-amber-300">
          Some permissions were not granted ({data.missing_scopes.map(shortScope).join(", ")}). Related
          data will not sync.{" "}
          <button type="button" className="underline" onClick={connect}>
            Grant them
          </button>
        </p>
      )}
    </Card>
  );
}
