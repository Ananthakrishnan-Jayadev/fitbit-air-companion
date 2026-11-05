import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { FAST } from "../motion.ts";
import { useTheme } from "../theme.ts";
import { NAV_ITEMS } from "../navigation.ts";
import BottomNav from "./BottomNav.tsx";
import CommandPalette from "./CommandPalette.tsx";
import StatusBanner from "./StatusBanner.tsx";
import ThemeToggle from "./ThemeToggle.tsx";

function navClass({ isActive }: { isActive: boolean }): string {
  const base =
    "relative flex items-center gap-2 whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition-colors duration-150";
  return isActive
    ? `${base} text-stone-950 dark:text-white`
    : `${base} text-stone-600 hover:bg-stone-200/70 hover:text-stone-900 dark:text-stone-400 dark:hover:bg-stone-800/70 dark:hover:text-stone-100`;
}

const TONE_DOT: Record<string, string> = { sleep: "bg-sleep", strain: "bg-strain" };

const IS_MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
const SHORTCUT = IS_MAC ? "⌘K" : "Ctrl K";

function SearchButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center justify-between rounded-md border border-stone-300 px-3 py-1.5 text-sm text-stone-500 hover:bg-stone-100 dark:border-stone-700 dark:hover:bg-stone-800"
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
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:shadow dark:focus:bg-stone-900"
      >
        Skip to content
      </a>

      <aside className="hidden border-r border-stone-200 bg-stone-100/70 md:sticky md:top-0 md:flex md:h-screen md:w-56 md:shrink-0 md:flex-col md:gap-3 md:overflow-y-auto md:px-2 md:py-4 dark:border-stone-800 dark:bg-stone-900/40">
        <div className="px-2 text-lg font-semibold tracking-tight">Air Companion</div>
        <div className="px-1">
          <SearchButton onClick={() => setPaletteOpen(true)} />
        </div>
        <nav aria-label="Main" className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.path} to={item.path} end={item.path === "/"} className={navClass}>
              {({ isActive }) => (
                <>
                  {isActive && (
                    // The highlight slides from the old page's item to the new one.
                    <motion.span
                      layoutId="nav-active"
                      transition={FAST}
                      aria-hidden
                      className="absolute inset-0 rounded-md bg-white shadow-sm ring-1 ring-stone-900/10 dark:bg-stone-800 dark:ring-white/10"
                    />
                  )}
                  <span className="relative">{item.label}</span>
                  {item.tone && (
                    <span aria-hidden className={`relative ml-auto h-1.5 w-1.5 rounded-full ${TONE_DOT[item.tone]}`} />
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto px-1">
          <ThemeToggle theme={theme} onChange={setTheme} />
        </div>
      </aside>

      <header className="flex items-center justify-between gap-3 border-b border-stone-200 px-4 py-3 md:hidden dark:border-stone-800">
        <span className="font-semibold tracking-tight">Air Companion</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="rounded-md border border-stone-300 px-2 py-1 text-xs dark:border-stone-700"
          >
            Search
          </button>
          <ThemeToggle theme={theme} onChange={setTheme} />
        </div>
      </header>

      <main id="main" tabIndex={-1} className="min-w-0 flex-1 px-4 py-6 pb-24 outline-none md:px-8 md:pb-10 lg:px-10">
        <StatusBanner />
        {/* A brief cross-fade marks the page change; no choreography on every visit. */}
        <motion.div key={location.pathname} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={FAST}>
          <Outlet />
        </motion.div>
      </main>

      <BottomNav />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
