import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { BASE } from "../motion.ts";
import { useTheme } from "../theme.ts";
import { NAV_ITEMS } from "../navigation.ts";
import BottomNav from "./BottomNav.tsx";
import CommandPalette from "./CommandPalette.tsx";
import StatusBanner from "./StatusBanner.tsx";
import ThemeToggle from "./ThemeToggle.tsx";

function navClass({ isActive }: { isActive: boolean }): string {
  const base = "block whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition-colors";
  return isActive
    ? `${base} bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900`
    : `${base} text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-800`;
}

const IS_MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
const SHORTCUT = IS_MAC ? "⌘K" : "Ctrl K";

function SearchButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center justify-between rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-500 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
    >
      <span>Search…</span>
      <kbd className="text-xs">{SHORTCUT}</kbd>
    </button>
  );
}

export default function Layout() {
  const location = useLocation();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [theme, setTheme] = useTheme();

  useEffect(() => {
    function onKeyDown(event: globalThis.KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <div className="min-h-screen md:flex">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:shadow dark:focus:bg-slate-900"
      >
        Skip to content
      </a>

      <aside className="hidden border-r border-slate-200 md:flex md:min-h-screen md:w-56 md:shrink-0 md:flex-col md:gap-3 md:px-2 md:py-4 dark:border-slate-800">
        <div className="px-2 text-lg font-semibold tracking-tight">Air Companion</div>
        <div className="px-1">
          <SearchButton onClick={() => setPaletteOpen(true)} />
        </div>
        <nav aria-label="Main" className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.path} to={item.path} end={item.path === "/"} className={navClass}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto px-1">
          <ThemeToggle theme={theme} onChange={setTheme} />
        </div>
      </aside>

      <header className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 md:hidden dark:border-slate-800">
        <span className="font-semibold tracking-tight">Air Companion</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700"
          >
            Search
          </button>
          <ThemeToggle theme={theme} onChange={setTheme} />
        </div>
      </header>

      <main id="main" tabIndex={-1} className="flex-1 px-4 py-6 pb-24 outline-none md:px-8 md:pb-6">
        <StatusBanner />
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={BASE}
        >
          <Outlet />
        </motion.div>
      </main>

      <BottomNav />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
