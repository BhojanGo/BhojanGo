import type { Metadata } from "next";
import { headers } from "next/headers";
import { fontVariables } from "./fonts";
import "./globals.css";
import { Providers } from "@/components/providers";
import { TestSiteBanner } from "@/components/TestSiteBanner";

export const metadata: Metadata = {
  title: "BhojanGo Admin",
  description: "BhojanGo operations console",
  robots: { index: false, follow: false },
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Read the request, so every page is rendered for it with the proxy's fresh CSP nonce
  // (R22 S9: a page rendered once at build time would carry no nonce, and its scripts wouldn't run).
  await headers();
  return (
    <html lang="en">
      <body className={`${fontVariables} bg-porcelain font-sans text-kohl antialiased`}>
        <TestSiteBanner />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
