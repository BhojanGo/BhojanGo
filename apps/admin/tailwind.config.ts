import type { Config } from "tailwindcss";
import preset from "@bhojango/ui/tailwind-preset";

const config: Config = {
  presets: [preset],
  content: ["./src/**/*.{ts,tsx}", "../../packages/ui/src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        body: ["var(--font-text)", "system-ui", "sans-serif"],
      },
      colors: {
        // Older pages still say brand/accent: they map onto Peacock and Kesar
        // until P20/P21 rebuild them on the design system.
        brand: {
          50: "#EFF6F6",
          100: "#DDEBEC",
          200: "#B9D6D9",
          300: "#86B9BE",
          400: "#3E8B93",
          500: "#0B5D66",
          600: "#0B5D66",
          700: "#083F46",
          800: "#083F46",
          900: "#062F34",
        },
        accent: {
          50: "#FBF4E6",
          100: "#F7EBD3",
          200: "#F2D9A8",
          300: "#ECC37A",
          400: "#E8A93C",
          500: "#D4932A",
          600: "#B87A1D",
          700: "#5C4100",
          800: "#5C4100",
          900: "#3D2B00",
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
