import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";

import { Providers } from "@/components/providers";
import Navbar from "@/components/layout/Navbar";
import MobileBottomNav from "@/components/layout/MobileBottomNav";
import Footer from "@/components/layout/Footer";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

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
      <body className={`${inter.variable} font-sans antialiased bg-gray-50 dark:bg-gray-950`}>
        <NextIntlClientProvider messages={messages}>
          <Providers>
            <Navbar />
            <div className="min-h-screen pb-16 sm:pb-0">{children}</div>
            <MobileBottomNav />
            <Footer />
          </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
