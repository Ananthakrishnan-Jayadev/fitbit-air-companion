import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.tsx";
import PlaceholderPage from "./components/PlaceholderPage.tsx";
import { NAV_ITEMS } from "./navigation.ts";
import SettingsPage from "./pages/SettingsPage.tsx";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {NAV_ITEMS.filter((item) => item.path !== "/settings").map((item) => (
          <Route key={item.path} path={item.path} element={<PlaceholderPage item={item} />} />
        ))}
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
