import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          500: "#f97316",
          600: "#ea6c0e",
        },
      },
    },
  },
  plugins: [],
};

export default config;
