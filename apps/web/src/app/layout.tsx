import type { Metadata, Viewport } from "next";

import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { TabBar } from "@/components/TabBar";
import { TestSiteBanner } from "@/components/TestSiteBanner";
import { UpdatedTermsNotice } from "@/components/legal/UpdatedTermsNotice";
import { I18nProvider } from "@/lib/i18n";
import { getContext } from "@/lib/prefs";
import { INDEXABLE, SITE } from "@/lib/server";
import { fontVariables } from "./fonts";
import "./globals.css";


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

// viewport-fit=cover: the phone tab bar pads itself for the home indicator (safe area).
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0B5D66", viewportFit: "cover" };

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
        legal: ctx.country.legal ?? {},  // R15: who operates BhojanGo here (Markets)
      }
    : null;
  return (
    <html lang={ctx.language}>
      <body className={`${fontVariables} bg-white font-sans text-[#111418] antialiased`}>
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
          <TestSiteBanner text={ctx.t("common.test_site_banner")} />
          <SiteHeader />
          <UpdatedTermsNotice />
          <main id="main" className="min-h-[60vh]">
            {children}
          </main>
          <SiteFooter />
          <TabBar cityPath={ctx.place && ctx.place.served !== false ? (ctx.place.city_path ?? null) : null} />
        </I18nProvider>
      </body>
    </html>
  );
}
