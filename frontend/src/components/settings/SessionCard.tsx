import { useSession, useSignOut } from "../../hooks/useSession.ts";
import { BUTTON_SECONDARY, Card, StatusDot } from "./Card.tsx";

/** App login (APP_PASSWORD). Hidden when no password is configured. */
export default function SessionCard() {
  const { data } = useSession();
  const signOut = useSignOut();
  if (!data?.required) return null;

  return (
    <Card title="App login">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 text-sm">
          <StatusDot tone="ok" />
          <span>Signed in on this device. To sign out every device, change APP_PASSWORD.</span>
        </div>
        <button
          type="button"
          className={BUTTON_SECONDARY}
          disabled={signOut.isPending}
          onClick={() => signOut.mutate()}
        >
          Sign out
        </button>
      </div>
    </Card>
  );
}
