import type { Metadata } from "next";
import { Familjen_Grotesk, Hanken_Grotesk } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";

import { Providers } from "@/components/providers";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import "./globals.css";

// Design system fonts (P16): display for headings and big numbers, text for everything else.
const display = Familjen_Grotesk({ subsets: ["latin"], weight: ["500", "600", "700"], variable: "--font-display" });
const text = Hanken_Grotesk({ subsets: ["latin"], weight: ["400", "500", "600", "700", "800"], variable: "--font-text" });

export const metadata: Metadata = {
  title: { default: "BhojanGo — Order Food Online", template: "%s | BhojanGo" },
  description: "Order from the best restaurants near you. Fast delivery, great food.",
  keywords: ["food delivery", "order food online", "restaurants", "BhojanGo"],
  openGraph: {
    type: "website",
    locale: "en_US",
    url: process.env.NEXT_PUBLIC_APP_URL,
    siteName: "BhojanGo",
    title: "BhojanGo — Order Food Online",
    description: "Order from the best restaurants near you.",
  },
  robots: { index: true, follow: true },
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale} suppressHydrationWarning>
      <body className={`${display.variable} ${text.variable} font-sans antialiased bg-porcelain text-kohl`}>
        <NextIntlClientProvider messages={messages}>
          <Providers>
            <Navbar />
            <div className="min-h-screen">{children}</div>
            <Footer />
          </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
