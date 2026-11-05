import type { ThemeChoice } from "../theme.ts";

const OPTIONS: { value: ThemeChoice; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "Auto" },
];

/** Controlled: the theme state lives in Layout so every toggle instance stays in sync.
 * Sits on the cobalt shell (rail and mobile header), so it is drawn in white. */
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
      className="inline-flex border border-white/50 p-0.5 text-xs text-white"
    >
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={theme === option.value}
          onClick={() => onChange(option.value)}
          className={`min-h-8 px-2.5 py-1 font-medium transition-colors ${
            theme === option.value ? "bg-white text-cobalt" : "hover:bg-white/15"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
