import type { Config } from "tailwindcss";
import preset from "@bhojango/ui/tailwind-preset";

const config: Config = {
  presets: [preset],
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
    "../../packages/ui/src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
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
      },
      fontFamily: {
      },
      animation: {
        "fade-in": "fadeIn 0.2s ease-in-out",
        "slide-up": "slideUp 0.3s ease-out",
      },
      keyframes: {
        fadeIn: { from: { opacity: "0" }, to: { opacity: "1" } },
        slideUp: { from: { transform: "translateY(10px)", opacity: "0" }, to: { transform: "translateY(0)", opacity: "1" } },
      },
    },
  },
  plugins: [],
};

export default config;
