import type { Config } from "tailwindcss";

// Tailwind v4 reads most config from CSS via @theme, but this file documents
// the semantic aliases and serves as a content-scan + plugin extension point.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg-base)",
        surface: "var(--surface)",
        border: "var(--border)",
        "text-primary": "var(--text-primary)",
        "text-secondary": "var(--text-secondary)",
        bull: "var(--accent-bull)",
        bear: "var(--accent-bear)",
        critical: "var(--critical-action)",
      },
      borderRadius: {
        card: "var(--radius-card)",
        input: "var(--radius-input)",
      },
      fontFamily: {
        sans: ["Geist", "system-ui", "sans-serif"],
        display: ["Newsreader", "Georgia", "serif"],
      },
    },
  },
} satisfies Config;
