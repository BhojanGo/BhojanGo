import {
  Familjen_Grotesk,
  Hanken_Grotesk,
  Noto_Sans_Bengali,
  Noto_Sans_Devanagari,
  Noto_Sans_Kannada,
  Noto_Sans_Tamil,
  Noto_Sans_Telugu,
} from "next/font/google";

// The type scale's fonts (packages/ui tokens): Familjen Grotesk for display, h1
// and h2; Hanken Grotesk for everything else. Indian scripts fall back to Noto
// Sans <script>: not preloaded, and each face carries its script's unicode-range,
// so a browser downloads one only when the page has text in that script.
const display = Familjen_Grotesk({ subsets: ["latin"], weight: ["600", "700"], display: "swap", variable: "--font-display" });
const text = Hanken_Grotesk({ subsets: ["latin"], weight: ["400", "600", "700"], display: "swap", variable: "--font-text" });
const deva = Noto_Sans_Devanagari({ subsets: ["devanagari"], weight: ["400", "600", "700"], display: "swap", preload: false, variable: "--font-deva" });
const telu = Noto_Sans_Telugu({ subsets: ["telugu"], weight: ["400", "600", "700"], display: "swap", preload: false, variable: "--font-telu" });
const taml = Noto_Sans_Tamil({ subsets: ["tamil"], weight: ["400", "600", "700"], display: "swap", preload: false, variable: "--font-taml" });
const knda = Noto_Sans_Kannada({ subsets: ["kannada"], weight: ["400", "600", "700"], display: "swap", preload: false, variable: "--font-knda" });
const beng = Noto_Sans_Bengali({ subsets: ["bengali"], weight: ["400", "600", "700"], display: "swap", preload: false, variable: "--font-beng" });

/** Put on <body>: defines the font variables the Tailwind preset's stacks read. */
export const fontVariables = [display, text, deva, telu, taml, knda, beng].map((f) => f.variable).join(" ");
