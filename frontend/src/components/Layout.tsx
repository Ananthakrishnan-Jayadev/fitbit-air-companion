import { NavLink, Outlet } from "react-router-dom";
import { NAV_ITEMS } from "../navigation.ts";
import StatusBanner from "./StatusBanner.tsx";

function navClass({ isActive }: { isActive: boolean }): string {
  const base = "block whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition-colors";
  return isActive
    ? `${base} bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900`
    : `${base} text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-800`;
}

export default function Layout() {
  return (
    <div className="min-h-screen md:flex">
      <aside className="border-b border-slate-200 md:min-h-screen md:w-56 md:shrink-0 md:border-b-0 md:border-r dark:border-slate-800">
        <div className="px-4 py-4 text-lg font-semibold tracking-tight">Air Companion</div>
        <nav className="flex gap-1 overflow-x-auto px-2 pb-3 md:flex-col md:overflow-visible">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.path} to={item.path} end={item.path === "/"} className={navClass}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 px-4 py-6 md:px-8">
        <StatusBanner />
        <Outlet />
      </main>
    </div>
  );
}
