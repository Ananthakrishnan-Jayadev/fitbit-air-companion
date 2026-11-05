import type { Config } from "tailwindcss";
import defaultTheme from "tailwindcss/defaultTheme";

/*
 * Visual world: Blue Note Sleeve (design.md). Flat ink fields, square corners, one grotesque
 * with a width axis (Archivo, bundled locally). `stone` is remapped to the world's neutral
 * ramp (paper -> ink) so every existing surface class inherits it.
 */
export default {
  // Dark mode follows the `dark` class on <html>, set from the Light/Dark/System toggle.
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Archivo Variable"', ...defaultTheme.fontFamily.sans],
      },
      // Sleeves are cut square: corners at most a hairline round. Dots stay `rounded-full`.
      borderRadius: {
        sm: "1px",
        DEFAULT: "2px",
        md: "2px",
        lg: "2px",
        xl: "3px",
      },
      colors: {
        // Neutral ramp: paper white to near-black ink, very slightly cool.
        stone: {
          50: "#f6f6f3",
          100: "#ecebe6",
          200: "#dcdbd4",
          300: "#c3c2ba",
          400: "#9a9992",
          500: "#6f6e68",
          600: "#55544f",
          700: "#3d3c39",
          800: "#2a2a2c",
          900: "#18181b",
          950: "#0e0e10",
        },
        cobalt: "var(--cobalt)",
        "cobalt-ink": "var(--cobalt-ink)",
        // Pillar and status hues from index.css (fields and marks; text only on their fields).
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
