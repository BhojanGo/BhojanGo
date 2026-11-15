import type { Metadata, Viewport } from "next";
import { Familjen_Grotesk, Hanken_Grotesk } from "next/font/google";

import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { I18nProvider } from "@/lib/i18n";
import { getContext } from "@/lib/prefs";
import { INDEXABLE, SITE } from "@/lib/server";
import "./globals.css";

// Design system fonts: display for headings and big numbers, text for everything else.
const display = Familjen_Grotesk({ subsets: ["latin"], weight: ["500", "600", "700"], variable: "--font-display" });
const text = Hanken_Grotesk({ subsets: ["latin"], weight: ["400", "500", "600", "700", "800"], variable: "--font-text" });

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return {
    metadataBase: new URL(SITE),
    title: { default: `${t("common.brand")} — ${t("common.tagline")}`, template: `%s · ${t("common.brand")}` },
    description: t("meta.description"),
    openGraph: { type: "website", siteName: t("common.brand") },
    // Only production is for search engines (QA and staging: noindex, also in robots.txt and a header).
    robots: INDEXABLE ? { index: true, follow: true } : { index: false, follow: false },
  };
}

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0B5D66" };

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const ctx = await getContext();
  const country = ctx.country
    ? {
        code: ctx.country.code,
        name: ctx.country.name,
        currency: ctx.country.currency,
        timezone: ctx.country.timezone,
        distance_unit: ctx.country.distance_unit,
        phone_code: ctx.country.phone_code,
      }
    : null;
  return (
    <html lang={ctx.language}>
      <body className={`${display.variable} ${text.variable} bg-white font-sans text-[#111418] antialiased`}>
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[100] focus:rounded-full focus:bg-white focus:px-4 focus:py-2">
          {ctx.t("common.skip_to_content")}
        </a>
        <I18nProvider
          value={{
            language: ctx.language,
            languages: ctx.languages,
            formatLocale: ctx.formatLocale,
            country,
            messages: ctx.messages,
            fallback: ctx.fallback,
          }}
        >
          <SiteHeader />
          <main id="main" className="min-h-[60vh]">
            {children}
          </main>
          <SiteFooter />
        </I18nProvider>
      </body>
    </html>
  );
}
