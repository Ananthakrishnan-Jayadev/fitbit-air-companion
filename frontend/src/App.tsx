import { lazy, Suspense, type ComponentType } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.tsx";
import { Loading } from "./components/PageState.tsx";
import PlaceholderPage from "./components/PlaceholderPage.tsx";
import { NAV_ITEMS } from "./navigation.ts";
import SettingsPage from "./pages/SettingsPage.tsx";
import TodayPage from "./pages/TodayPage.tsx";

// Chart-heavy pages load on first visit, keeping the initial bundle small.
const PAGES: Record<string, ComponentType> = {
  "/": TodayPage,
  "/heart": lazy(() => import("./pages/HeartPage.tsx")),
  "/sleep": lazy(() => import("./pages/SleepPage.tsx")),
  "/activity": lazy(() => import("./pages/ActivityPage.tsx")),
  "/body": lazy(() => import("./pages/BodyPage.tsx")),
  "/trends": lazy(() => import("./pages/TrendsPage.tsx")),
  "/journal": lazy(() => import("./pages/JournalPage.tsx")),
  "/coach": lazy(() => import("./pages/CoachPage.tsx")),
  "/settings": SettingsPage,
};

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {NAV_ITEMS.map((item) => {
          const Page = PAGES[item.path];
          return (
            <Route
              key={item.path}
              path={item.path}
              element={
                Page ? (
                  <Suspense fallback={<Loading />}>
                    <Page />
                  </Suspense>
                ) : (
                  <PlaceholderPage item={item} />
                )
              }
            />
          );
        })}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
