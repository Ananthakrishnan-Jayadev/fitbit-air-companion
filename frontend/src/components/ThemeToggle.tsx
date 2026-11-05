import type { ThemeChoice } from "../theme.ts";

const OPTIONS: { value: ThemeChoice; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "Auto" },
];

/** Controlled: the theme state lives in Layout so every toggle instance stays in sync. */
export default function ThemeToggle({
  theme,
  onChange,
}: {
  theme: ThemeChoice;
  onChange: (choice: ThemeChoice) => void;
}) {
  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className="inline-flex rounded-md border border-stone-300 p-0.5 text-xs dark:border-stone-700"
    >
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={theme === option.value}
          onClick={() => onChange(option.value)}
          className={`rounded px-2 py-1 transition-colors ${
            theme === option.value
              ? "bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900"
              : "text-stone-600 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
