import type { Config } from "tailwindcss";

export default {
  // Dark mode follows the `dark` class on <html>, set from the Light/Dark/System toggle.
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
} satisfies Config;
