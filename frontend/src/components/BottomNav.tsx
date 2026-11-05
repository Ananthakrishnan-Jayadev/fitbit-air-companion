import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { NavLink } from "react-router-dom";
import { FAST } from "../motion.ts";

const PRIMARY = [
  { path: "/", label: "Today" },
  { path: "/sleep", label: "Sleep" },
  { path: "/activity", label: "Activity" },
  { path: "/coach", label: "Coach" },
];
const MORE = [
  { path: "/heart", label: "Heart" },
  { path: "/body", label: "Body" },
  { path: "/trends", label: "Trends" },
  { path: "/journal", label: "Journal" },
  { path: "/settings", label: "Settings" },
];

function tabClass({ isActive }: { isActive: boolean }): string {
  return `relative flex min-h-12 flex-1 flex-col items-center justify-center text-xs font-medium ${
    isActive ? "font-semibold text-stone-900 dark:text-white" : "text-stone-600 dark:text-stone-400"
  }`;
}

/** Mobile navigation (below the md breakpoint, where the sidebar is hidden). */
export default function BottomNav() {
  const [moreOpen, setMoreOpen] = useState(false);
  const close = () => setMoreOpen(false);

  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-stone-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden dark:border-stone-800 dark:bg-stone-950/95"
    >
      <AnimatePresence>
        {moreOpen && (
          <motion.ul
            className="absolute bottom-full right-2 mb-2 w-44 overflow-hidden rounded-lg border border-stone-200 bg-white py-1 shadow-lg dark:border-stone-800 dark:bg-stone-900"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={FAST}
          >
            {MORE.map((item) => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  onClick={close}
                  className="block px-4 py-2 text-sm hover:bg-stone-100 dark:hover:bg-stone-800"
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
      <div className="flex">
        {PRIMARY.map((item) => (
          <NavLink key={item.path} to={item.path} end={item.path === "/"} className={tabClass} onClick={close}>
            {({ isActive }) => (
              <>
                {isActive && (
                  // A bar above the active tab that slides to the next one.
                  <motion.span
                    layoutId="tab-active"
                    transition={FAST}
                    aria-hidden
                    className="absolute inset-x-3 top-0 h-[3px] bg-cobalt"
                  />
                )}
                {item.label}
              </>
            )}
          </NavLink>
        ))}
        <button
          type="button"
          className="flex min-h-12 flex-1 flex-col items-center justify-center text-xs font-medium text-stone-500 dark:text-stone-400"
          aria-expanded={moreOpen}
          onClick={() => setMoreOpen((open) => !open)}
        >
          More
        </button>
      </div>
    </nav>
  );
}
