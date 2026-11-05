import type { Config } from "tailwindcss";

export default {
  // Dark mode follows the `dark` class on <html>, set from the Light/Dark/System toggle.
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Pillar and status hues from index.css, for marks only (dots, bars, tints).
      colors: {
        sleep: "var(--sleep)",
        strain: "var(--strain)",
        good: "var(--good)",
        warning: "var(--warning)",
        critical: "var(--critical)",
      },
    },
  },
  plugins: [],
} satisfies Config;
