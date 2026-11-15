import type { Metadata } from "next";
import { fontVariables } from "./fonts";
import "./globals.css";
import { Providers } from "@/components/providers";
import { TestSiteBanner } from "@/components/TestSiteBanner";

export const metadata: Metadata = {
  title: "BhojanGo Admin",
  description: "BhojanGo operations console",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${fontVariables} bg-porcelain font-sans text-kohl antialiased`}>
        <TestSiteBanner />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
