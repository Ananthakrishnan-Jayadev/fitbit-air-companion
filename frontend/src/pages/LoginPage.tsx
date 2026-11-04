import { useState, type FormEvent } from "react";
import { ApiError } from "../api/client.ts";
import { BUTTON } from "../components/settings/Card.tsx";
import { useLogin } from "../hooks/useSession.ts";

function errorText(error: Error): string {
  if (error instanceof ApiError && (error.status === 401 || error.status === 429)) return error.message;
  return "Couldn't reach the app. Is the server running?";
}

/** Shown instead of the app when APP_PASSWORD is set and this browser has no session. */
export default function LoginPage() {
  const [password, setPassword] = useState("");
  const login = useLogin();

  function submit(event: FormEvent) {
    event.preventDefault();
    if (password) login.mutate(password, { onError: () => setPassword("") });
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <h1 className="text-xl font-semibold tracking-tight">Fitbit Air Companion</h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">Enter the app password to continue.</p>

        <label htmlFor="password" className="mt-5 block text-sm font-medium">
          Password
        </label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          autoFocus
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          aria-invalid={login.isError}
          aria-describedby={login.isError ? "login-error" : undefined}
          className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
        />

        {login.isError && (
          <p id="login-error" role="alert" className="mt-2 text-sm text-red-700 dark:text-red-300">
            {errorText(login.error)}
          </p>
        )}

        <button type="submit" className={`${BUTTON} mt-5 w-full py-2`} disabled={login.isPending || !password}>
          {login.isPending ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
