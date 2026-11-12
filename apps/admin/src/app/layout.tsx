import type { Metadata } from "next";
import { Familjen_Grotesk, Hanken_Grotesk } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";

// Design system fonts (P16): display for headings and big numbers, text for everything else.
const display = Familjen_Grotesk({ subsets: ["latin"], weight: ["500", "600", "700"], variable: "--font-display" });
const text = Hanken_Grotesk({ subsets: ["latin"], weight: ["400", "500", "600", "700", "800"], variable: "--font-text" });

export const metadata: Metadata = {
  title: "BhojanGo Admin",
  description: "BhojanGo operations console",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${display.variable} ${text.variable} bg-porcelain font-sans text-kohl antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
