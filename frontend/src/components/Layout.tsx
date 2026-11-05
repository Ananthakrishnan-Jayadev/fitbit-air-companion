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

// The rail is the cobalt shell; the current page is the one item cut out in white.
function navClass({ isActive }: { isActive: boolean }): string {
  const base = "relative flex items-center gap-2 whitespace-nowrap px-3 py-2 text-[15px] transition-colors duration-150";
  return isActive ? `${base} font-semibold text-cobalt` : `${base} text-white/85 hover:bg-white/10 hover:text-white`;
}

// Pillar dots, lightened so they read on cobalt.
const TONE_DOT: Record<string, string> = { sleep: "bg-[#b9adff]", strain: "bg-strain" };

function Brand({ className = "" }: { className?: string }) {
  return (
    <span className={`font-condensed text-[1.9rem] font-black uppercase leading-[0.85] ${className}`}>
      Air
      <span className="block font-light">Companion</span>
    </span>
  );
}

const IS_MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
const SHORTCUT = IS_MAC ? "⌘K" : "Ctrl K";

function SearchButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center justify-between border border-white/50 px-3 py-2 text-sm text-white/85 hover:bg-white/10"
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

      <aside className="hidden bg-cobalt text-white md:sticky md:top-0 md:flex md:h-screen md:w-56 md:shrink-0 md:flex-col md:gap-4 md:overflow-y-auto md:px-4 md:py-6">
        <Brand className="px-1" />
        <div className="mt-2">
          <SearchButton onClick={() => setPaletteOpen(true)} />
        </div>
        <nav aria-label="Main" className="-mx-1 flex flex-col gap-0.5">
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
                      className="absolute inset-0 bg-white"
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
        <div className="mt-auto">
          <ThemeToggle theme={theme} onChange={setTheme} />
        </div>
      </aside>

      <header className="flex items-center justify-between gap-3 bg-cobalt px-4 py-3 text-white md:hidden">
        <Brand className="!text-[1.35rem]" />
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="min-h-8 border border-white/50 px-2.5 text-xs font-medium hover:bg-white/15"
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
