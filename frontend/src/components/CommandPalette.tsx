import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { askHref } from "../coach.ts";
import { addDays, formatDayLabel, localTodayIso } from "../format.ts";
import { BASE, FAST } from "../motion.ts";
import { NAV_ITEMS } from "../navigation.ts";

interface Command {
  id: string;
  label: string;
  hint: string;
  to: string;
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

function commandsFor(query: string): Command[] {
  const q = query.trim();
  const lower = q.toLowerCase();
  const today = localTodayIso();
  const fixed: Command[] = [
    ...NAV_ITEMS.map((item) => ({ id: item.path, label: item.label, hint: "Page", to: item.path })),
    { id: "today", label: "Today's scores", hint: formatDayLabel(today), to: "/" },
    {
      id: "yesterday",
      label: "Yesterday's scores",
      hint: formatDayLabel(addDays(today, -1)),
      to: `/?date=${addDays(today, -1)}`,
    },
  ];
  const matches = fixed.filter((c) => !lower || c.label.toLowerCase().includes(lower));
  const extra: Command[] = [];
  if (ISO_DATE.test(q)) {
    extra.push({ id: "date", label: `Open ${formatDayLabel(q)}`, hint: "Day", to: `/?date=${q}` });
  }
  if (q) {
    extra.push({ id: "ask", label: `Ask the coach: "${q}"`, hint: "Coach", to: askHref(q) });
  }
  return [...extra, ...matches];
}

/** ⌘K / Ctrl+K: jump to a page or day, or hand a question to the coach. */
export default function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const returnFocus = useRef<Element | null>(null);

  useEffect(() => {
    if (open) {
      returnFocus.current = document.activeElement;
      return;
    }
    if (returnFocus.current instanceof HTMLElement) returnFocus.current.focus();
  }, [open]);

  const commands = commandsFor(query);
  const current = Math.min(active, Math.max(commands.length - 1, 0));

  function close() {
    setQuery("");
    setActive(0);
    onClose();
  }

  function run(command: Command | undefined) {
    if (!command) return;
    close();
    navigate(command.to);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((current + 1) % Math.max(commands.length, 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((current - 1 + commands.length) % Math.max(commands.length, 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      run(commands[current]);
    } else if (event.key === "Escape") {
      event.preventDefault();
      close();
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-start justify-center bg-slate-950/40 px-4 pt-[15vh]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={FAST}
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) close();
          }}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Command palette"
            className="w-full max-w-lg overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-900"
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={BASE}
          >
            <input
              autoFocus
              className="w-full border-b border-slate-200 bg-transparent px-4 py-3 text-sm outline-none dark:border-slate-800"
              placeholder="Go to a page, a date (YYYY-MM-DD), or ask the coach…"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setActive(0);
              }}
              onKeyDown={onKeyDown}
              role="combobox"
              aria-expanded="true"
              aria-controls="command-list"
              aria-activedescendant={commands[current] ? `command-${commands[current].id}` : undefined}
            />
            <ul id="command-list" role="listbox" className="max-h-80 overflow-y-auto py-1">
              {commands.map((command, i) => (
                <li
                  key={command.id}
                  id={`command-${command.id}`}
                  role="option"
                  aria-selected={i === current}
                  className={`flex cursor-pointer items-center justify-between gap-4 px-4 py-2 text-sm ${
                    i === current ? "bg-slate-100 dark:bg-slate-800" : ""
                  }`}
                  onMouseEnter={() => setActive(i)}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    run(command);
                  }}
                >
                  <span className="truncate">{command.label}</span>
                  <span className="shrink-0 text-xs text-slate-500">{command.hint}</span>
                </li>
              ))}
              {commands.length === 0 && (
                <li className="px-4 py-3 text-sm text-slate-500">No matches.</li>
              )}
            </ul>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
