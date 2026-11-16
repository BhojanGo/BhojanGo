import "@fontsource-variable/inter/wght.css";
import {
  Noto_Sans_Bengali,
  Noto_Sans_Devanagari,
  Noto_Sans_Kannada,
  Noto_Sans_Tamil,
  Noto_Sans_Telugu,
} from "next/font/google";

// The type scale's fonts (packages/ui tokens). Inter for every role: self-hosted
// from @fontsource-variable/inter (OFL; the CSS above is bundled with the site, one
// variable face per subset, each with its unicode-range, so a page loads only the
// subsets it uses: latin, and latin-ext for ₹). Indian scripts fall back to Noto
// Sans <script>: not preloaded, and each face carries its script's unicode-range,
// so a browser downloads one only when the page has text in that script.
const deva = Noto_Sans_Devanagari({ subsets: ["devanagari"], weight: ["400", "600", "700"], display: "swap", preload: false, variable: "--font-deva" });
const telu = Noto_Sans_Telugu({ subsets: ["telugu"], weight: ["400", "600", "700"], display: "swap", preload: false, variable: "--font-telu" });
const taml = Noto_Sans_Tamil({ subsets: ["tamil"], weight: ["400", "600", "700"], display: "swap", preload: false, variable: "--font-taml" });
const knda = Noto_Sans_Kannada({ subsets: ["kannada"], weight: ["400", "600", "700"], display: "swap", preload: false, variable: "--font-knda" });
const beng = Noto_Sans_Bengali({ subsets: ["bengali"], weight: ["400", "600", "700"], display: "swap", preload: false, variable: "--font-beng" });

/** Put on <body>: defines the font variables the Tailwind preset's stacks read. */
export const fontVariables = [deva, telu, taml, knda, beng].map((f) => f.variable).join(" ");
