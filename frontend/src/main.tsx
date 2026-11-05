import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "motion/react";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { isUnauthorized } from "./api/client.ts";
import App from "./App.tsx";
// Bundled locally by Vite (no font CDN): Archivo with weight and width axes.
import "@fontsource-variable/archivo/standard.css";
import "./index.css";
import { applyTheme, storedTheme } from "./theme.ts";

// Before the first render, so the page never flashes the wrong theme.
applyTheme(storedTheme());

// Any 401 means the login session expired: re-check it so the app shows the login form.
function onError(error: unknown) {
  if (isUnauthorized(error)) void queryClient.invalidateQueries({ queryKey: ["session"] });
}

const queryClient: QueryClient = new QueryClient({
  queryCache: new QueryCache({ onError }),
  mutationCache: new MutationCache({ onError }),
  defaultOptions: {
    queries: { staleTime: 30_000, retry: (count, error) => !isUnauthorized(error) && count < 1 },
  },
});

const root = document.getElementById("root");
if (!root) throw new Error("#root element missing");

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {/* "user": honour the OS reduce-motion setting everywhere. */}
        <MotionConfig reducedMotion="user">
          <App />
        </MotionConfig>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
