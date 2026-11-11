import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        body: ["var(--font-body)", "system-ui", "sans-serif"],
      },
      colors: {
        brand: {
          50: "#ecfdf5",
          100: "#d1fae5",
          500: "#10b981",
          600: "#059669",
          700: "#047857",
          900: "#064e3b",
        },
        accent: {
          500: "#f59e0b",
          600: "#d97706",
        },
        // Design board tokens (new console pages; P16 moves them to packages/ui)
        peacock: { DEFAULT: "#0B5D66", dark: "#083F46", tint: "#DDEBEC", wash: "#EFF6F6", mid: "#5BA3AA" },
        kohl: "#111418",
        kesar: { DEFAULT: "#D4932A", tint: "#F7EBD3", ink: "#5C4100" },
        porcelain: "#F4F6F6",
        muted: "#4C5A5E",
        line: { DEFAULT: "#E2E7E8", soft: "#EEF1F1" },
        danger: { DEFAULT: "#B3261E", tint: "#FCE8E6", ink: "#8C1D18" },
      },
    },
  },
  plugins: [],
};

export default config;
