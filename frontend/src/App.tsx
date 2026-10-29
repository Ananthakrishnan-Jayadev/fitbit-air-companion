import type { ComponentType } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.tsx";
import PlaceholderPage from "./components/PlaceholderPage.tsx";
import { NAV_ITEMS } from "./navigation.ts";
import ActivityPage from "./pages/ActivityPage.tsx";
import CoachPage from "./pages/CoachPage.tsx";
import HeartPage from "./pages/HeartPage.tsx";
import SettingsPage from "./pages/SettingsPage.tsx";
import SleepPage from "./pages/SleepPage.tsx";
import TodayPage from "./pages/TodayPage.tsx";
import TrendsPage from "./pages/TrendsPage.tsx";

const PAGES: Record<string, ComponentType> = {
  "/": TodayPage,
  "/heart": HeartPage,
  "/sleep": SleepPage,
  "/activity": ActivityPage,
  "/trends": TrendsPage,
  "/coach": CoachPage,
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
              element={Page ? <Page /> : <PlaceholderPage item={item} />}
            />
          );
        })}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
