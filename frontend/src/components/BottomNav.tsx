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
  return `flex flex-1 flex-col items-center py-2 text-xs font-medium ${
    isActive ? "text-slate-900 dark:text-white" : "text-slate-500 dark:text-slate-400"
  }`;
}

/** Mobile navigation (below the md breakpoint, where the sidebar is hidden). */
export default function BottomNav() {
  const [moreOpen, setMoreOpen] = useState(false);
  const close = () => setMoreOpen(false);

  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 backdrop-blur md:hidden dark:border-slate-800 dark:bg-slate-950/95"
    >
      <AnimatePresence>
        {moreOpen && (
          <motion.ul
            className="absolute bottom-full right-2 mb-2 w-44 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-800 dark:bg-slate-900"
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
                  className="block px-4 py-2 text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
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
            {item.label}
          </NavLink>
        ))}
        <button
          type="button"
          className="flex flex-1 flex-col items-center py-2 text-xs font-medium text-slate-500 dark:text-slate-400"
          aria-expanded={moreOpen}
          onClick={() => setMoreOpen((open) => !open)}
        >
          More
        </button>
      </div>
    </nav>
  );
}
